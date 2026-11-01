from collections import defaultdict
from datetime import date

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

ACCOUNTANT_MODULES = [
    ("home", "Dashboard", "home", [("Accounts overview", "accountant-overview")]),
    ("students", "Students & dues", "graduation-cap", [
        ("Student fee directory", "accountant_students"),
        ("Pending fee students", "accountant_pending"),
        ("Student fee accounts", "mvp_fees"),
    ]),
    ("collections", "Collections", "inr", [
        ("Fee structures", "mvp_structures"),
        ("Assign fee structure", "mvp_assign_fees"),
        ("Invoices", "mvp_invoices"),
        ("Receipts", "mvp_receipts"),
        ("Collection report", "mvp_report_collection"),
        ("Dues report", "mvp_report_dues"),
    ]),
    ("transport", "Transport billing", "bus", [
        ("Transport fee bills", "accountant_transport"),
    ]),
    ("spending", "Spending", "credit-card", [
        ("Event & maintenance bills", "accountant_expenses"),
    ]),
    ("communication", "Fee circulars", "bullhorn", [
        ("Fee related circulars", "accountant_notices"),
    ]),
]


def _current_enrolment(student, year_id=0):
    return student.course_detail_ids.filtered(lambda e: e.state == "running" and
        (not year_id or e.academic_years_id.id == year_id)).sorted(
            key=lambda e: e.academic_term_id.term_start_date or e.academic_years_id.start_date or date.min,
            reverse=True)[:1]


class AccountantDashboard(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _accountant_only(self):
        user = self.env.user
        return user.has_group("ideastone_erp.group_mvp_accountant") and not (
            user.has_group("ideastone_erp.group_mvp_owner")
            or user.has_group("ideastone_erp.group_mvp_registrar")
            or user.has_group("ideastone_erp.group_manager")
        )

    def _accountant_access(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
            raise AccessError(_("College accountant permission is required."))

    def _owner_modules(self):
        modules = super()._owner_modules()
        if self._accountant_only():
            return ACCOUNTANT_MODULES
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
            return modules
        owner_accounts = [("Accounts summary", "accountant-overview"), ("Student fee directory", "accountant_students"),
            ("Pending fee students", "accountant_pending"), ("Transport fee bills", "accountant_transport"),
            ("Event & maintenance bills", "accountant_expenses"), ("Fee circulars", "accountant_notices")]
        return modules + [("accounts", "Accounts", "ledger", owner_accounts)]

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self._accountant_only():
            data.update(workspace_role="Accountant", is_accountant_workspace=True, report_allowed=False)
        return data

    @api.model
    def get_accountant_metrics(self, filters=None):
        self._accountant_access()
        f = self._mvp_filters(filters)
        company = [("company_id", "=", self.env.company.id)]
        departments = self.env["op.department"].search(
            ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)], order="name")
        department_id = f["department_id"]
        if department_id and department_id not in departments.ids:
            raise AccessError(_("Select a department in the active college."))
        sale_types = {"out_invoice", "out_refund"}
        vendor_types = {"in_invoice", "in_refund"}

        def in_department(move):
            if not department_id:
                return True
            if move.move_type in sale_types:
                return move.campus_course_id.department_id.id == department_id
            return move.campus_spend_department_id.id == department_id

        def receipt_in_department(payment):
            return not department_id or payment.campus_invoice_id.campus_course_id.department_id.id == department_id

        period = [("invoice_date", ">=", f["date_from"]), ("invoice_date", "<=", f["date_to"])]
        moves = self._mvp_records("account.move", company + period + [("state", "=", "posted"),
            ("move_type", "in", list(sale_types | vendor_types))]).filtered(in_department)
        paid = self._mvp_records(*self._mvp_source("collection", f)).filtered(receipt_in_department)
        collections = sum(p.amount for p in paid if f["date_from"] <= p.date <= f["date_to"])
        collections -= sum(p.amount for p in paid if p.campus_reversal_id and f["date_from"] <= p.campus_reversal_id.date <= f["date_to"])
        income = sum(m.amount_total * (1 if m.move_type == "out_invoice" else -1)
                     for m in moves if m.move_type in sale_types)
        outgoing = sum(m.amount_total * (1 if m.move_type == "in_invoice" else -1)
                       for m in moves if m.move_type in vendor_types)
        bills = moves.filtered(lambda m: m.move_type in vendor_types)
        spend = defaultdict(float)
        for bill in bills:
            spend[bill.campus_spend_category or "unclassified"] += bill.amount_total * (1 if bill.move_type == "in_invoice" else -1)

        due_model, due_domain = self._mvp_source("dues", f)
        due_moves = self._mvp_records(due_model, due_domain).filtered(in_department)
        due_rows = self._mvp_report_rows("dues", f, due_moves)
        pending = defaultdict(lambda: {"amount": 0.0, "overdue": 0, "invoices": 0})
        for row in due_rows:
            # The report row already applies the selected as-of date and reversals.
            invoice = self.env["account.move"].browse(row["id"])
            item = pending[invoice.campus_student_id.id]
            item["amount"] += row["balance"]
            item["overdue"] += int(row["days_overdue"] > 0)
            item["invoices"] += 1
        students = self.env["op.student"].browse(list(pending))
        student_rows = []
        for student in students:
            enrolment = _current_enrolment(student, f["year_id"])
            amount = pending[student.id]
            student_rows.append({"id": student.id, "name": student.name, "number": student.gr_no or student.register_no or "",
                "department": enrolment.course_id.department_id.name or "", "semester": enrolment.academic_term_id.name or "",
                "pending": amount["amount"], "overdue": amount["overdue"], "invoices": amount["invoices"]})
        student_rows.sort(key=lambda row: (-row["pending"], row["name"]))

        allocations = self._mvp_records("campus.transport.allocation", company + [("state", "=", "approved")], limit=50000)
        if department_id:
            allocations = allocations.filtered(lambda a: _current_enrolment(a.student_id).course_id.department_id.id == department_id)
        transport = [{"id": a.id, "student": a.student_id.name, "route": a.route_id.name,
                      "fee": a.stop_id.fee, "invoice": a.invoice_id.name or "",
                      "pending": a.invoice_id.amount_residual if a.invoice_id.state == "posted" else 0,
                      "status": "Not billed" if not a.invoice_id else "Draft" if a.invoice_id.state == "draft"
                          else "Paid" if a.invoice_id.amount_residual <= 0 else "Pending"}
                     for a in allocations if not f["year_id"] or a.year_id.id == f["year_id"]]
        notices = self.env["campus.circular"].search(company + [("campus_category", "=", "Fees")], order="date_from desc", limit=6)
        all_bills = self._mvp_records("account.move", company + period + [
            ("move_type", "in", list(vendor_types)), ("state", "!=", "cancel")]).filtered(in_department)
        draft_bills = all_bills.filtered(lambda bill: bill.state == "draft")

        # A fixed 12-month window lets the selector change the chart without a second RPC.
        trend_start = fields.Date.subtract(f["date_to"].replace(day=1), months=11)
        trend_filters = dict(f, date_from=trend_start)
        trend_receipts = self._mvp_records(*self._mvp_source("collection", trend_filters)).filtered(receipt_in_department)
        trend_invoices = self._mvp_records("account.move", company + [
            ("invoice_date", ">=", trend_start), ("invoice_date", "<=", f["date_to"]),
            ("state", "=", "posted"), ("move_type", "in", list(sale_types))]).filtered(in_department)
        trend = [{"month": fields.Date.add(trend_start, months=i).strftime("%Y-%m"),
                  "label": fields.Date.add(trend_start, months=i).strftime("%b"),
                  "collections": 0.0, "income": 0.0} for i in range(12)]
        by_month = {row["month"]: row for row in trend}
        for payment in trend_receipts:
            if trend_start <= payment.date <= f["date_to"]:
                by_month[payment.date.strftime("%Y-%m")]["collections"] += payment.amount
            reversal = payment.campus_reversal_id
            if reversal and trend_start <= reversal.date <= f["date_to"]:
                by_month[reversal.date.strftime("%Y-%m")]["collections"] -= payment.amount
        for invoice in trend_invoices:
            by_month[invoice.invoice_date.strftime("%Y-%m")]["income"] += invoice.amount_total * (
                1 if invoice.move_type == "out_invoice" else -1)

        pending_total = sum(row["balance"] for row in due_rows)
        overdue_total = sum(row["balance"] for row in due_rows if row["days_overdue"] > 0)
        billed_total = sum(move.amount_total for move in due_moves)
        overdue_30 = len({self.env["account.move"].browse(row["id"]).campus_student_id.id
                          for row in due_rows if row["days_overdue"] > 30})
        activity = []
        for payment in paid:
            if f["date_from"] <= payment.date <= f["date_to"]:
                activity.append({"id": f"receipt-{payment.id}", "reference": payment.campus_receipt_number,
                    "name": "Student fee receipt", "detail": payment.campus_invoice_id.campus_student_id.name or "Fee collection",
                    "amount": payment.amount, "date": str(payment.date), "status": "Posted"})
            reversal = payment.campus_reversal_id
            if reversal and f["date_from"] <= reversal.date <= f["date_to"]:
                activity.append({"id": f"reversal-{payment.id}", "reference": payment.campus_receipt_number,
                    "name": "Receipt reversal", "detail": payment.campus_invoice_id.campus_student_id.name or "Fee collection",
                    "amount": -payment.amount, "date": str(reversal.date), "status": "Reversed"})
        for bill in all_bills:
            activity.append({"id": f"bill-{bill.id}", "reference": bill.name if bill.name != "/" else bill.ref or "Draft bill",
                "name": bill.ref or bill.partner_id.name or "Vendor bill", "detail": bill.partner_id.name or "Vendor invoice",
                "amount": bill.amount_total * (1 if bill.move_type == "in_invoice" else -1),
                "date": str(bill.invoice_date or bill.date),
                "status": "Draft" if bill.state == "draft" else "Paid" if bill.payment_state == "paid" else "Posted"})
        activity.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
        return {
            "currency": self.env.company.currency_id.symbol,
            "period": {"from": str(f["date_from"]), "to": str(f["date_to"])},
            "departments": [{"id": department.id, "name": department.name} for department in departments],
            "selected_department": department_id,
            "cards": [
                {"key": "collections", "label": "Fee collections", "value": collections, "detail": "Receipts less reversals in period", "pill": "This period"},
                {"key": "income", "label": "Billed income", "value": income, "detail": "Posted invoices less credits", "pill": "This period"},
                {"key": "dues", "label": "Outstanding dues", "value": pending_total, "detail": f"{len(student_rows)} student accounts pending", "pill": "Due now" if pending_total else "Clear"},
                {"key": "spending", "label": "Recorded spending", "value": outgoing, "detail": f"Across {len(bills)} posted vendor bills", "pill": "Recorded"},
            ],
            "trend": trend,
            "collection_status": {"collected": max(0.0, billed_total - pending_total),
                "pending": max(0.0, pending_total - overdue_total), "overdue": overdue_total,
                "total": billed_total, "overdue_30": overdue_30},
            "activity": activity[:6],
            "queue": [
                {"key": "dues", "title": "Outstanding student dues", "count": len(student_rows),
                 "detail": f"{len(student_rows)} student accounts · {self._mvp_money(pending_total)} remaining",
                 "hint": "Prioritize overdue balances", "action": "accountant_pending"},
                {"key": "bills", "title": "Draft vendor bills to review", "count": len(draft_bills),
                 "detail": f"{len(draft_bills)} bills · {self._mvp_money(sum(b.amount_total for b in draft_bills))} total",
                 "hint": "Check evidence and category", "action": "accountant_expenses"},
                {"key": "transport", "title": "Transport allocations to bill", "count": sum(1 for row in transport if not row["invoice"]),
                 "detail": f"{sum(1 for row in transport if not row['invoice'])} approved allocations not billed",
                 "hint": "Create linked fee invoices", "action": "accountant_transport"},
                {"key": "circulars", "title": "Fee circulars in draft", "count": self.env["campus.circular"].search_count(
                    company + [("campus_category", "=", "Fees"), ("campus_status", "=", "draft")]),
                 "detail": "Review fee notices before publishing", "hint": "Open circular records", "action": "accountant_notices"},
            ],
            "pending_count": len(student_rows),
            "pending": student_rows[:10],
            "transport_unbilled": sum(1 for row in transport if not row["invoice"]),
            "transport": transport[:8],
            "spending": [{"label": key.title(), "value": spend[key]} for key in ("event", "maintenance", "other", "unclassified")],
            "recent_bills": [{"id": m.id, "name": m.name, "vendor": m.partner_id.name, "date": str(m.invoice_date),
                              "category": (m.campus_spend_category or "unclassified").title(), "amount": m.amount_total}
                             for m in bills.sorted("invoice_date", reverse=True)[:8]],
            "notices": [{"id": n.id, "name": n.name, "date": str(n.date_from), "status": n.campus_status} for n in notices],
        }


class AccountantExpense(models.Model):
    _inherit = "account.move"

    campus_spend_department_id = fields.Many2one("op.department", string="Spending department", index=True)
    campus_spend_category = fields.Selection([
        ("event", "College event"), ("maintenance", "Maintenance"), ("other", "Other"),
    ], string="College spending category", index=True)

    @api.constrains("campus_spend_category", "move_type")
    def _check_spend_category(self):
        if any(m.campus_spend_category and m.move_type not in {"in_invoice", "in_refund"} for m in self):
            raise ValidationError(_("Classify spending on vendor bills or vendor credits only."))


class AccountantStudent(models.Model):
    _inherit = "op.student"

    campus_fee_currency_id = fields.Many2one("res.currency", compute="_compute_accountant_directory")
    campus_fee_pending = fields.Monetary(compute="_compute_accountant_directory", search="_search_campus_fee_pending",
        currency_field="campus_fee_currency_id")
    campus_fee_status = fields.Char(compute="_compute_accountant_directory")
    campus_current_department = fields.Char(compute="_compute_accountant_directory")
    campus_current_semester = fields.Char(compute="_compute_accountant_directory")

    def _compute_accountant_directory(self):
        invoices = self.env["account.move"].search([("campus_student_id", "in", self.ids),
            ("company_id", "=", self.env.company.id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("amount_residual", ">", 0)])
        balances = defaultdict(float)
        overdue = set()
        today = fields.Date.context_today(self)
        for invoice in invoices:
            balances[invoice.campus_student_id.id] += invoice.amount_residual
            if (invoice.invoice_date_due or invoice.invoice_date or invoice.date) < today:
                overdue.add(invoice.campus_student_id.id)
        for student in self:
            enrolment = _current_enrolment(student)
            student.campus_fee_currency_id = self.env.company.currency_id
            student.campus_fee_pending = balances[student.id]
            student.campus_fee_status = "Overdue" if student.id in overdue else "Pending" if balances[student.id] else "Clear"
            student.campus_current_department = enrolment.course_id.department_id.name or ""
            student.campus_current_semester = enrolment.academic_term_id.name or ""

    def _search_campus_fee_pending(self, operator, value):
        if operator != ">" or value != 0:
            raise ValidationError(_("Filter pending fees using an amount greater than zero."))
        invoices = self.env["account.move"].search([("campus_student_id", "!=", False),
            ("company_id", "=", self.env.company.id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("amount_residual", ">", 0)])
        return [("id", "in", invoices.campus_student_id.ids)]


class AccountantTransport(models.Model):
    _inherit = "campus.transport.allocation"

    def write(self, vals):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not (
            self.env.user.has_group("ideastone_erp.group_manager") or
            self.env.user.has_group("ideastone_erp.group_mvp_owner") or
            self.env.user.has_group("ideastone_erp.group_services")
        ):
            raise AccessError(_("The accountant may bill approved transport allocations, but may not edit them."))
        return super().write(vals)

    def action_invoice(self):
        if not (self.env.user.has_group("ideastone_erp.group_mvp_accountant") or
                self.env.user.has_group("ideastone_erp.group_manager")):
            raise AccessError(_("Transport billing requires accountant permission."))
        return super().action_invoice()


class AccountantTransportStop(models.Model):
    _inherit = "campus.transport.stop"

    fee_product_id = fields.Many2one("product.product", string="Transport fee product",
        domain="[('campus_fee_head','=',True)]", check_company=True)


class AccountantNotice(models.Model):
    _inherit = "campus.circular"

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            for vals in vals_list:
                vals.setdefault("campus_category", "Fees")
                vals.setdefault("campus_managed", True)
                if (vals.get("campus_category") != "Fees" or not vals.get("campus_managed")
                        or vals.get("company_id", self.env.company.id) != self.env.company.id
                        or vals.get("audience", "student") not in {"student", "parent", "all"}
                        or any(vals.get(key) for key in ("campus_course_id", "campus_batch_id", "campus_group_id"))):
                    raise AccessError(_("Accountants may create fee circulars in the active college only."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            if (any(n.campus_category != "Fees" or n.company_id != self.env.company for n in self)
                    or vals.get("campus_category", "Fees") != "Fees"
                    or vals.get("company_id", self.env.company.id) != self.env.company.id
                    or vals.get("audience", "student") not in {"student", "parent", "all"}
                    or any(vals.get(key) for key in ("campus_course_id", "campus_batch_id", "campus_group_id"))):
                raise AccessError(_("Accountants may edit fee circulars only."))
        return super().write(vals)

    def action_campus_publish(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant") or self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            return super().action_campus_publish()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.company_id != self.env.company or rec.campus_category != "Fees" or rec.campus_status != "draft" or rec.date_to and rec.date_to < today:
                raise ValidationError(_("Publish an unexpired draft fee circular in the active college."))
            rec._lock()
            future = rec.date_from > today
            rec._set_system_values({"campus_status": "scheduled" if future else "published",
                "state": "submitted" if future else "approved", "approved_by": self.env.uid,
                "approved_on": fields.Datetime.now()})
            self.env["campus.mvp.audit"]._log(rec, "Fee circular scheduled" if future else "Fee circular published")
        return True

    def action_campus_archive(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant") or self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            return super().action_campus_archive()
        for rec in self:
            if rec.company_id != self.env.company or rec.campus_category != "Fees":
                raise AccessError(_("Accountants may archive fee circulars in the active college only."))
            rec._lock()
            rec._set_system_values({"campus_status": "archived", "state": "done"})
            self.env["campus.mvp.audit"]._log(rec, "Fee circular archived")
        return True
