from collections import defaultdict

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

CATEGORIES = [("fee", "Transport fee"), ("fuel", "Diesel / Fuel"), ("maintenance", "Maintenance"),
              ("salary", "Driver salary"), ("insurance", "Insurance & permits"), ("other", "Other")]


class TransportFleet(models.Model):
    _inherit = "campus.transport.route"

    fleet_status = fields.Selection([("operational", "Operational"), ("delayed", "Delayed"),
                                    ("breakdown", "Breakdown"), ("maintenance", "Maintenance"),
                                    ("reserve", "Inactive / reserve")], required=True, default="operational")
    staff_riders = fields.Integer(default=0)
    service_due = fields.Date()
    driver_code = fields.Char(string="Driver employee ID")
    driver_partner_id = fields.Many2one("res.partner", string="Driver payee", check_company=True)
    maintenance_reserve = fields.Monetary(string="Maintenance budget allocation")

    _sql_constraints = [
        ("staff_riders_positive", "check(staff_riders >= 0)", "Staff riders cannot be negative."),
        ("reserve_positive", "check(maintenance_reserve >= 0)", "Maintenance budget cannot be negative."),
    ]

    @api.constrains("staff_riders", "capacity")
    def _check_rider_capacity(self):
        for route in self:
            route._lock()
            students = self.env["campus.transport.allocation"].sudo().search_count([
                ("route_id", "=", route.id), ("state", "=", "approved")])
            if students + route.staff_riders > route.capacity:
                raise ValidationError(_("Assigned students and staff exceed the bus capacity."))

    def write(self, vals):
        if {"year_id", "company_id"} & vals.keys():
            for route in self:
                if any(vals.get(key, route[key].id) != route[key].id for key in ("year_id", "company_id")) and (
                    self.env["campus.transport.allocation"].sudo().search_count([("route_id", "=", route.id)])
                    or self.env["account.move"].sudo().search_count([("campus_transport_route_id", "=", route.id)])):
                    raise ValidationError(_("Retain the college and academic year of a route with linked records. Create a route for the new year."))
        return super().write(vals)


class TransportInvoice(models.Model):
    _inherit = "account.move"

    campus_transport_route_id = fields.Many2one("campus.transport.route", string="Bus / Route", check_company=True, index=True)
    campus_transport_category = fields.Selection(CATEGORIES, string="Transport category", index=True)

    def write(self, vals):
        if {"campus_transport_route_id", "campus_transport_category"} & vals.keys() and self.filtered(
                lambda move: move.campus_student_id and move.state == "posted"):
            raise ValidationError(_("The transport classification of a posted student invoice is retained unchanged."))
        return super().write(vals)

    @api.constrains("campus_transport_route_id", "campus_transport_category", "move_type")
    def _check_transport_type(self):
        for move in self.filtered("campus_transport_category"):
            if not move.campus_transport_route_id:
                raise ValidationError(_("Select a bus / route for transport entries."))
            allowed = {"out_invoice", "out_refund"} if move.campus_transport_category == "fee" else {"in_invoice", "in_refund"}
            if move.move_type not in allowed:
                raise ValidationError(_("Use a student invoice for fees and a vendor bill for transport expenses."))


class TransportPayroll(models.Model):
    _name = "campus.transport.payroll"
    _description = "Monthly driver salary record"
    _inherit = "campus.record"
    _order = "month desc, id desc"

    name = fields.Char(default="Driver salary", required=True)
    route_id = fields.Many2one("campus.transport.route", required=True, check_company=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", string="Driver payee", required=True, check_company=True, ondelete="restrict")
    month = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    base = fields.Monetary(string="Base salary", required=True)
    allowance = fields.Monetary()
    deductions = fields.Monetary()
    net = fields.Monetary(compute="_compute_net", store=True)
    expense_account_id = fields.Many2one("account.account", required=True, check_company=True,
                                       domain="[('account_type','=','expense'),('company_id','=',company_id)]")
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False, check_company=True, ondelete="restrict")
    payment_status = fields.Selection([("pending", "Pending"), ("processing", "Processing"), ("paid", "Paid"),
                                      ("cancelled", "Cancelled")], compute="_compute_status")

    _sql_constraints = [
        ("driver_month", "unique(company_id, partner_id, month)", "A salary record already exists for this driver and month."),
        ("valid_salary", "check(base >= 0 AND allowance >= 0 AND deductions >= 0 AND base + allowance > deductions)",
         "Enter nonnegative amounts and a positive net salary."),
    ]

    @api.depends("base", "allowance", "deductions")
    def _compute_net(self):
        for rec in self:
            rec.net = rec.base + rec.allowance - rec.deductions

    @api.depends("invoice_id.state", "invoice_id.payment_state")
    def _compute_status(self):
        for rec in self:
            rec.payment_status = "cancelled" if rec.invoice_id.state == "cancel" else (
                "paid" if rec.invoice_id.payment_state == "paid" else "processing" if rec.invoice_id.state == "posted" else "pending")

    @api.constrains("month", "route_id", "company_id")
    def _check_month(self):
        for rec in self:
            if rec.month.day != 1:
                raise ValidationError(_("Select the first day of the salary month."))
            if not rec.route_id.year_id.start_date.replace(day=1) <= rec.month <= rec.route_id.year_id.end_date:
                raise ValidationError(_("Salary month must fall in the route's academic year."))

    @api.onchange("route_id")
    def _onchange_route(self):
        if self.route_id:
            self.partner_id = self.route_id.driver_partner_id
            self.name = f"Driver salary · {self.route_id.driver or self.route_id.name}"

    def write(self, vals):
        if any(rec.invoice_id for rec in self) and set(vals) & {
            "company_id", "route_id", "partner_id", "month", "base", "allowance", "deductions", "expense_account_id", "invoice_id",
        }:
            raise ValidationError(_("A billed salary record is retained unchanged. Correct its vendor bill through the accounting workflow."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("invoice_id") for vals in vals_list):
            raise AccessError(_("The bill is linked by the salary billing workflow."))
        return super().create(vals_list)

    def unlink(self):
        if any(rec.invoice_id for rec in self):
            raise ValidationError(_("Retain salary records linked to vendor bills."))
        return super().unlink()

    def action_bill(self):
        self.ensure_one()
        self._lock()
        if not self.invoice_id:
            bill = self.env["account.move"].create({
                "move_type": "in_invoice", "company_id": self.company_id.id, "partner_id": self.partner_id.id,
                "invoice_date": self.month, "ref": f"{self.name} / {self.month:%Y-%m}",
                "campus_transport_route_id": self.route_id.id, "campus_transport_category": "salary",
                "campus_spend_category": "other",
                "invoice_line_ids": [(0, 0, {"name": self.name, "quantity": 1, "price_unit": self.net,
                                            "account_id": self.expense_account_id.id, "tax_ids": [(5, 0, 0)]})],
            })
            super().write({"invoice_id": bill.id})
        return {"type": "ir.actions.act_window", "name": _("Driver salary bill"), "res_model": "account.move",
                "res_id": self.invoice_id.id, "views": [(False, "form")], "target": "current"}


class TransportWorkspace(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _client_action_models(self):
        return dict(super()._client_action_models(), accountant_transport_dashboard="campus.transport.route")

    @api.model
    def get_transport_data(self, year_id=False):
        self._accountant_access()
        today = fields.Date.context_today(self)
        company = [("company_id", "=", self.env.company.id)]
        years = self.env["op.academic.year"].search(company, order="start_date desc")
        try:
            year = years.filtered(lambda y: y.id == int(year_id)) if year_id else (
                years.filtered(lambda y: y.start_date <= today <= y.end_date)[:1] or years[:1])
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid academic year.")) from exc
        if year_id and not year:
            raise AccessError(_("Select an academic year in the active college."))
        domain = company + [("year_id", "=", year.id or False)]
        routes = self.with_context(active_test=False)._mvp_records("campus.transport.route", domain)
        allocations = self._mvp_records("campus.transport.allocation", domain + [("state", "=", "approved")])
        billed_allocations = self.with_context(active_test=False)._mvp_records(
            "campus.transport.allocation", domain + [("invoice_id", "!=", False)])
        transport_invoices = self._mvp_records("account.move", company + [
            ("campus_transport_route_id", "in", routes.ids), ("campus_transport_category", "=", "fee")]) if routes else self.env["account.move"]
        invoice_routes = {a.invoice_id.id: a.route_id for a in billed_allocations}
        invoice_routes.update({invoice.id: invoice.campus_transport_route_id for invoice in transport_invoices})
        rider_counts = defaultdict(int)
        for allocation in allocations:
            rider_counts[allocation.route_id.id] += 1
        invoices = billed_allocations.invoice_id | transport_invoices
        receipt_domain = company + [("campus_receipt_number", "!=", False), ("campus_invoice_id", "in", invoices.ids)]
        receipts = self._mvp_records("account.payment", receipt_domain) if invoices else self.env["account.payment"]
        transactions = []
        for payment in receipts:
            route = invoice_routes[payment.campus_invoice_id.id]
            transactions.append({"id": f"receipt-{payment.id}", "record_id": payment.id, "kind": "receipt",
                "date": str(payment.date), "reference": payment.campus_receipt_number, "name": "Transport fee collection",
                "route": route.name, "category": "Transport fee", "category_key": "fee", "income": payment.amount,
                "expense": 0, "status": "Recorded"})
            if payment.campus_reversal_id:
                transactions.append({"id": f"reversal-{payment.id}", "record_id": payment.id, "kind": "receipt",
                    "date": str(payment.campus_reversal_id.date), "reference": payment.campus_receipt_number,
                    "name": "Transport receipt reversal", "route": route.name, "category": "Transport fee",
                    "category_key": "fee", "income": -payment.amount, "expense": 0, "status": "Reversed"})
        bills = self._mvp_records("account.move", company + [
            ("campus_transport_route_id", "in", routes.ids), ("campus_transport_category", "!=", False),
            ("move_type", "in", ["in_invoice", "in_refund"]), ("state", "!=", "cancel")]) if routes else self.env["account.move"]
        categories = dict(CATEGORIES)
        for bill in bills:
            amount = -bill.amount_total_signed
            transactions.append({"id": f"bill-{bill.id}", "record_id": bill.id, "kind": "bill",
                "date": str(bill.invoice_date or bill.date), "reference": bill.name if bill.name != "/" else bill.ref or "Draft bill",
                "name": bill.ref or bill.partner_id.name, "route": bill.campus_transport_route_id.vehicle_registration,
                "category": categories[bill.campus_transport_category], "category_key": bill.campus_transport_category,
                "income": 0, "expense": amount, "status": "Draft" if bill.state == "draft" else
                "Paid" if bill.payment_state == "paid" else "Posted"})
        # Fiscal figures follow the selected academic year, not lifetime route receipts.
        transactions = [row for row in transactions if year and str(year.start_date) <= row["date"] <= str(year.end_date)]
        transactions.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
        expenses = {key: sum(t["expense"] for t in transactions if t["category_key"] == key and t["status"] != "Draft")
                    for key, label in CATEGORIES if key != "fee"}
        revenue = sum(t["income"] for t in transactions)
        payroll = self._mvp_records("campus.transport.payroll", company + [("route_id", "in", routes.ids)]) if routes else self.env["campus.transport.payroll"]
        return {
            "currency": self.env.company.currency_id.symbol, "today": str(today), "year_id": year.id or False,
            "year": year.name or "No academic year", "years": [{"id": y.id, "name": y.name} for y in years],
            "routes": [{"id": r.id, "name": r.name, "registration": r.vehicle_registration, "driver": r.driver or "",
                "driver_code": r.driver_code or "", "students": rider_counts[r.id],
                "staff": r.staff_riders, "capacity": r.capacity, "status": r.fleet_status if r.active else "reserve",
                "service_due": str(r.service_due) if r.service_due else ""} for r in routes],
            "revenue": revenue, "expenses": expenses, "reserve": sum(routes.mapped("maintenance_reserve")),
            "transactions": transactions, "payroll": [{"id": p.id, "employee": p.route_id.driver_code or "—",
                "driver": p.partner_id.name, "bus": p.route_id.vehicle_registration, "month": str(p.month)[:7],
                "base": p.base, "allowance": p.allowance, "deductions": p.deductions, "net": p.net,
                "status": p.payment_status} for p in payroll],
        }

    @api.model
    def get_transport_action(self, kind, record_id=False):
        self._accountant_access()
        actions = {
            "fleet": ("campus.transport.route", "transport_fleet_form"),
            "payroll": ("campus.transport.payroll", "transport_payroll_form"),
            "bill": ("account.move", "account.view_move_form"),
            "receipt": ("account.payment", "account.view_account_payment_form"),
            "allocations": ("campus.transport.allocation", False),
        }
        if kind not in actions:
            raise ValidationError(_("Unknown transport action."))
        model, view = actions[kind]
        context = {"default_company_id": self.env.company.id}
        if kind == "bill":
            context.update(default_move_type="in_invoice", default_campus_transport_category="fuel", default_campus_spend_category="maintenance")
        if record_id:
            record = self.env[model].browse(record_id).exists()
            record.check_access_rights("read")
            record.check_access_rule("read")
            if not record or record.company_id != self.env.company:
                raise AccessError(_("Select a record in the active college."))
            if kind == "bill" and not record.campus_transport_category:
                raise AccessError(_("Select a transport bill."))
            if kind == "receipt" and not record.campus_receipt_number:
                raise AccessError(_("Select a college receipt."))
        else:
            self.env[model].check_access_rights("create" if kind != "allocations" else "read")
        if kind == "allocations":
            result = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp.accountant_transport")
            return dict(result, domain=[("company_id", "=", self.env.company.id), ("state", "=", "approved")])
        view_id = self.env.ref(view if "." in view else f"ideastone_erp.{view}").id
        return {"type": "ir.actions.act_window", "name": dict(fleet="Bus / Route", payroll="Driver salary record",
                bill="Transport expense", receipt="Transport receipt")[kind], "res_model": model,
                "res_id": record_id or False, "views": [(view_id, "form")], "target": "new", "context": context}
