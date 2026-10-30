from collections import defaultdict
from datetime import timedelta
from math import isfinite

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

PAGES = {
    "overview": ("Financial overview", "account.move"), "heads": ("Fee heads", "product.template"),
    "structures": ("Fee structures", "op.fees.terms"), "accounts": ("Student fee accounts", "op.student.fees.details"),
    "assign": ("Assign fee structure", "campus.fee.assignment.wizard"), "invoices": ("Invoices & dues", "account.move"),
    "followup": ("Overdue follow-up", "account.move"), "receipts": ("Receipts", "account.payment"),
}
QUOTAS = [("gq", "Government Quota (GQ)"), ("mq", "Management Quota (MQ)")]
SOURCES = {"heads": "mvp_fee_heads", "structures": "mvp_structures", "accounts": "mvp_fees", "assign": "mvp_assign_fees",
    "invoices": "mvp_invoices", "followup": "mvp_overdue_invoices", "receipts": "mvp_receipts"}


class OwnerFeesNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        return [(key, label, icon, [(label, "action_owner_fees_" + page) for page, (label, _model) in PAGES.items()])
                if key == "fees" else (key, label, icon, entries)
                for key, label, icon, entries in super()._owner_modules()]

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{"action_owner_fees_" + key: value[1] for key, value in PAGES.items()})

    @api.model
    def get_overview(self):
        data = super().get_overview()
        for module in data.get("faculty_modules", []):
            if module["key"] == "fees" and data.get("is_owner_workspace"):
                for item in module["items"]:
                    page = item.get("action", "").removeprefix("ideastone_erp.action_owner_fees_")
                    if page in SOURCES:
                        item["source_action"] = "ideastone_erp." + SOURCES[page]
        return data


class OwnerFeeHead(models.Model):
    _inherit = "product.template"

    campus_fee_category = fields.Selection([("academic", "Academic"), ("facilities", "Facilities"), ("services", "Services"), ("student_services", "Student services")], default="academic")
    campus_fee_frequency = fields.Selection([("semester", "Semester"), ("annual", "Annual"), ("monthly", "Monthly"),
        ("once", "One-time"), ("exam", "Per exam"), ("term", "Term")], default="semester")
    campus_fee_optional = fields.Boolean("Optional fee")


class OwnerFeeEnrolment(models.Model):
    _inherit = "op.student.course"

    campus_fee_quota = fields.Selection(QUOTAS, string="Admission fee quota")


class OwnerFeePlan(models.Model):
    _name = "op.fees.terms"
    _inherit = ["op.fees.terms", "campus.mvp.mixin"]

    campus_card_managed = fields.Boolean(default=False, copy=False)
    campus_quota = fields.Selection(QUOTAS)
    campus_study_year = fields.Integer("Year of study", default=1)
    campus_plan_state = fields.Selection([("draft", "Draft"), ("review", "Needs review"), ("published", "Published")], default="draft", copy=False)
    campus_version = fields.Integer("Version", default=1)
    campus_effective_date = fields.Date("Effective from")
    campus_plan_approver = fields.Many2one("res.users", readonly=True, copy=False)
    campus_plan_approved_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("campus_plan_state", "draft") != "draft" or v.get("campus_plan_approver") or v.get("campus_plan_approved_on") for v in vals_list):
            raise AccessError(_("Publish the draft fee structure through its approval action."))
        return super().create(vals_list)

    def write(self, vals):
        if {"campus_plan_state", "campus_plan_approver", "campus_plan_approved_on"}.intersection(vals):
            raise AccessError(_("Use the fee structure review and publication actions."))
        if self.filtered(lambda r: r.campus_card_managed and r.campus_plan_state == "published") and set(vals) - {"message_follower_ids"}:
            raise ValidationError(_("Published structures are retained unchanged. Create a new version instead."))
        return super().write(vals)

    def action_campus_plan_review(self):
        self._mvp_require("ideastone_erp.group_mvp_accountant")
        if any(not p.campus_card_managed or p.campus_plan_state != "draft" for p in self):
            raise ValidationError(_("Submit a draft department fee structure for review."))
        super().write({"campus_plan_state": "review"})

    def action_campus_plan_publish(self):
        self._mvp_require("ideastone_erp.group_mvp_owner")
        self._mvp_lock()
        for plan in self:
            plan._mvp_company("campus_course_id", "campus_year_id", "campus_term_id")
            if not plan.campus_card_managed or plan.campus_plan_state != "review" or not plan.line_ids or not plan.campus_quota or not plan.campus_course_id or not plan.campus_year_id:
                raise ValidationError(_("Review a complete department structure before publishing it."))
            if not 1 <= plan.campus_study_year <= 4 or sum(plan.line_ids.mapped("campus_amount")) <= 0 or any(not line.campus_product_id or not line.campus_product_id.campus_fee_head or line.campus_product_id.company_id not in (plan.company_id, self.env["res.company"]) for line in plan.line_ids):
                raise ValidationError(_("Choose a valid study year, college fee heads and a positive annual total."))
        super().write({"campus_plan_state": "published", "campus_plan_approver": self.env.uid, "campus_plan_approved_on": fields.Datetime.now()})
        self._mvp_log("Department fee structure published")


class OwnerFeePlanLine(models.Model):
    _inherit = "op.fees.terms.line"

    def _check_editable_plan(self):
        if self.fees_id.filtered(lambda p: p.campus_card_managed and p.campus_plan_state == "published"):
            raise ValidationError(_("Published fee installments cannot be changed. Create a new version."))

    @api.model_create_multi
    def create(self, vals_list):
        plans = self.env["op.fees.terms"].browse([v["fees_id"] for v in vals_list if v.get("fees_id")])
        if plans.filtered(lambda p: p.campus_card_managed and p.campus_plan_state == "published"):
            raise ValidationError(_("Published fee installments cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_editable_plan()
        if vals.get("fees_id") and self.env["op.fees.terms"].browse(vals["fees_id"]).filtered(lambda p: p.campus_card_managed and p.campus_plan_state == "published"):
            raise ValidationError(_("Published fee installments cannot be changed."))
        return super().write(vals)

    def unlink(self):
        self._check_editable_plan()
        return super().unlink()


class OwnerFeeAssignment(models.TransientModel):
    _inherit = "campus.fee.assignment.wizard"

    def action_assign(self):
        for wizard in self:
            plan, enrolment = wizard.structure_id, wizard.enrolment_id
            if plan.campus_card_managed:
                year = (enrolment.academic_term_id.campus_sequence + 1) // 2
                if plan.campus_plan_state != "published" or enrolment.campus_fee_quota != plan.campus_quota or year != plan.campus_study_year:
                    raise ValidationError(_("Choose a published structure matching the enrolment's admission quota and study year."))
                other = self.env["op.student.fees.details"].search_count([("student_id", "=", enrolment.student_id.id),
                    ("company_id", "=", plan.company_id.id), ("campus_year_id", "=", plan.campus_year_id.id),
                    ("fees_line_id.fees_id.campus_card_managed", "=", True), ("fees_line_id.fees_id.campus_study_year", "=", plan.campus_study_year),
                    ("fees_line_id.fees_id", "!=", plan.id)])
                if other:
                    raise ValidationError(_("This student already has another structure version for this study year. Retain the existing assessments."))
        return super().action_assign()


class OwnerFeeContact(models.Model):
    _name = "campus.fee.contact"
    _description = "Internal fee follow-up log"
    _order = "contacted_on desc, id desc"

    invoice_id = fields.Many2one("account.move", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="invoice_id.company_id", store=True, index=True)
    contacted_on = fields.Datetime(readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", readonly=True, default=lambda self: self.env.user)
    channel = fields.Selection([("phone", "Phone"), ("in_person", "In person"), ("email", "Email already sent"), ("other", "Other")], required=True)
    outcome = fields.Text(required=True)
    next_action = fields.Char(required=True)
    next_date = fields.Date(required=True)
    promise = fields.Boolean("Promise to pay recorded")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
            raise AccessError(_("Fee accountant permission is required."))
        rows = super().create([dict(v, user_id=self.env.uid, contacted_on=fields.Datetime.now()) for v in vals_list])
        for row in rows:
            row.invoice_id.check_access_rule("read")
            if row.company_id != self.env.company or not row.invoice_id.campus_student_id or row.invoice_id.state != "posted" or not (row.outcome or "").strip() or not (row.next_action or "").strip():
                raise ValidationError(_("Log a contact against a posted student invoice in the active college."))
        return rows

    def write(self, vals):
        raise ValidationError(_("Contact logs are retained unchanged. Add a new follow-up entry."))

    def unlink(self):
        raise ValidationError(_("Contact logs must be retained for the audit trail."))


class OwnerFeePaymentNote(models.Model):
    _inherit = "account.payment"

    campus_fee_note = fields.Text("Collection notes")


class OwnerFeePaymentDraft(models.TransientModel):
    _inherit = "campus.fee.payment.wizard"

    campus_note = fields.Text("Collection notes")


class OwnerFeesWorkspace(models.AbstractModel):
    _name = "campus.owner.fees"
    _description = "Owner fees and payment workspace"

    def _check(self, write=False):
        roles = ["accountant", "owner"] if write else ["accountant", "owner", "readonly"]
        if not self.env.su and not any(self.env.user.has_group("ideastone_erp.group_mvp_" + r) for r in roles):
            raise AccessError(_("College finance workspace permission is required."))

    def _records(self, model, domain=None):
        return self.env["campus.dashboard"].with_context(active_test=False)._mvp_records(model,
            [("company_id", "=", self.env.company.id)] + (domain or []))

    def _record(self, model, record_id):
        if type(record_id) is not int or record_id <= 0:
            raise ValidationError(_("Choose a valid college record."))
        rec = self._records(model, [("id", "=", record_id)])
        if not rec:
            raise AccessError(_("This record is outside the active college or your permissions."))
        return rec

    def _number(self, value):
        if type(value) not in (int, float) or not isfinite(value) or value < 0:
            raise ValidationError(_("Enter a finite, non-negative amount."))
        return value

    def _year(self, year_id):
        years = self._records("op.academic.year").sorted("start_date", reverse=True)
        year = self._record("op.academic.year", year_id) if year_id else (years.filtered("campus_current") or years.filtered(lambda y: y.start_date <= fields.Date.context_today(self) <= y.end_date) or years)[:1]
        return years, year

    @api.model
    def get_workspace(self, year_id=0):
        self._check()
        years, year = self._year(year_id)
        today = fields.Date.context_today(self)
        first = year.start_date if year else today.replace(month=1, day=1)
        last = year.end_date if year else today.replace(month=12, day=31)
        students = self._records("op.student", [("active", "=", True)])
        enrolments = self._records("op.student.course", [("academic_years_id", "=", year.id), ("state", "=", "running")]) if year else self.env["op.student.course"]
        fees = self._records("op.student.fees.details", [("campus_managed", "=", True), ("campus_year_id", "=", year.id)])
        invoices = self._records("account.move", [("campus_student_id", "!=", False), ("move_type", "=", "out_invoice"), ("campus_year_id", "=", year.id)])
        receipts = self._records("account.payment", [("campus_receipt_number", "!=", False), "|", "&", ("date", ">=", first), ("date", "<=", last), "&", ("campus_reversal_id.date", ">=", first), ("campus_reversal_id.date", "<=", last)])
        expenses = self._records("account.payment", [("payment_type", "=", "outbound"), ("partner_type", "=", "supplier"), ("state", "=", "posted"), ("is_internal_transfer", "=", False),
            "|", "&", ("date", ">=", first), ("date", "<=", last), "&", ("move_id.reversal_move_id.date", ">=", first), ("move_id.reversal_move_id.date", "<=", last)])
        heads = self.env["product.product"].with_context(active_test=False).search([("campus_fee_head", "=", True), ("company_id", "in", [False, self.env.company.id])])
        plans = self._records("op.fees.terms", [("campus_managed", "=", True), ("campus_year_id", "=", year.id)])
        contacts = self._records("campus.fee.contact", [("invoice_id", "in", invoices.ids)])
        posted = invoices.filtered(lambda i: i.state == "posted")
        overdue = posted.filtered(lambda i: i.amount_residual > 0 and i.invoice_date_due and i.invoice_date_due < today)
        contact_map = {}
        for c in contacts.sorted(lambda c: (c.contacted_on, c.id), reverse=True):
            contact_map.setdefault(c.invoice_id.id, c)
        monthly = {}
        day = first.replace(day=1)
        while day <= last:
            monthly[day.strftime("%Y-%m")] = {"key": day.strftime("%Y-%m"), "date": str(day), "income": 0, "expense": 0, "scheduled": 0}
            day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        for p in receipts:
            if p.date.strftime("%Y-%m") in monthly and p.state == "posted":
                monthly[p.date.strftime("%Y-%m")]["income"] += p.amount
            if p.campus_reversal_id and p.campus_reversal_id.date.strftime("%Y-%m") in monthly:
                monthly[p.campus_reversal_id.date.strftime("%Y-%m")]["income"] -= p.amount
        for payment in expenses:
            amount = payment.currency_id._convert(payment.amount, self.env.company.currency_id, self.env.company, payment.date)
            if first <= payment.date <= last:
                monthly[payment.date.strftime("%Y-%m")]["expense"] += amount
            for reversal in payment.move_id.reversal_move_id.filtered(lambda r: r.state == "posted" and first <= r.date <= last):
                monthly[reversal.date.strftime("%Y-%m")]["expense"] -= amount
        for fee in fees:
            if fee.date and fee.date.strftime("%Y-%m") in monthly:
                monthly[fee.date.strftime("%Y-%m")]["scheduled"] += fee.amount - (fee.campus_concession if fee.campus_approved_by else 0)
        fee_map = defaultdict(list)
        for fee in fees:
            fee_map[fee.student_id.id].append(fee)
        invoice_map = defaultdict(list)
        for invoice in posted:
            invoice_map[invoice.campus_student_id.id].append(invoice)
        enrolment_map = {e.student_id.id: e for e in reversed(enrolments)}
        accounts = []
        scoped_students = (enrolments.student_id | fees.student_id | invoices.campus_student_id) & students
        for student in scoped_students:
            charges = fee_map[student.id]
            student_invoices = invoice_map[student.id]
            unbilled = [f for f in charges if not f.invoice_id or f.invoice_id.state == "draft"]
            unbilled_net = sum(f.amount - (f.campus_concession if f.campus_approved_by else 0) for f in unbilled)
            assessed = sum(i.amount_total for i in student_invoices) + unbilled_net
            balance = sum(i.amount_residual for i in student_invoices) + unbilled_net
            enrolment = enrolment_map.get(student.id, self.env["op.student.course"])
            accounts.append({"id": student.id, "name": student.name, "register": student.gr_no or "—", "course_id": enrolment.course_id.id,
                "course": enrolment.course_id.name or "Not recorded", "assessed": assessed, "concession": sum(f.campus_concession for f in charges if f.campus_approved_by),
                "paid": max(0, assessed - balance), "balance": balance, "status": "Unassigned" if not charges else "Paid" if balance <= 0 else "Partial" if assessed > balance else "Unpaid"})
        invoice_rows = [{"id": i.id, "name": i.name or "Draft invoice", "student": i.campus_student_id.name, "register": i.campus_student_id.gr_no,
            "course_id": i.campus_course_id.id, "fee": ", ".join(i.invoice_line_ids.product_id.mapped("name")), "date": str(i.invoice_date or ""),
            "due": str(i.invoice_date_due or ""), "amount": i.amount_total, "balance": i.amount_residual, "state": i.state,
            "status": "Cancelled" if i.state == "cancel" else "Draft" if i.state == "draft" else "Paid" if i.amount_residual <= 0 else "Overdue" if i in overdue else "Partial" if i.amount_residual < i.amount_total else "Open"} for i in invoices]
        followups = []
        for i in overdue.sorted(lambda i: (i.invoice_date_due, -i.amount_residual)):
            c = contact_map.get(i.id)
            followups.append({"id": i.id, "student": i.campus_student_id.name, "register": i.campus_student_id.gr_no, "balance": i.amount_residual,
                "days": (today - i.invoice_date_due).days, "contact": str(c.contacted_on.date()) if c else "", "next": c.next_action if c else "Review account",
                "next_date": str(c.next_date) if c else "", "owner": c.user_id.name if c else "Unassigned", "status": "Promise to pay" if c and c.promise else "In progress" if c else "Pending"})
        plan_rows = [{"id": p.id, "name": p.name, "course_id": p.campus_course_id.id, "course": p.campus_course_id.name,
            "department_id": p.campus_course_id.department_id.id, "quota": p.campus_quota or "", "study_year": p.campus_study_year,
            "state": p.campus_plan_state if p.campus_card_managed else "configured", "version": p.campus_version,
            "effective": str(p.campus_effective_date or ""), "approver": p.campus_plan_approver.name or "Not recorded", "approved": str(p.campus_plan_approved_on or ""),
            "total": sum(p.line_ids.mapped("campus_amount")), "term_id": p.campus_term_id.id, "active": p.active,
            "lines": [{"id": line.id, "product_id": line.campus_product_id.id, "name": line.campus_product_id.name or "Configure fee head", "amount": line.campus_amount, "date": str(line.due_date or ""), "days": line.due_days} for line in p.line_ids]} for p in plans]
        monthly_rows = list(monthly.values())
        journals = self._records("account.journal", [("type", "in", ["cash", "bank"])])
        return {"company": self.env.company.name, "currency": self.env.company.currency_id.name, "symbol": self.env.company.currency_id.symbol,
            "today": str(today), "demo": self.env.company.campus_demo, "year_id": year.id,
            "years": [{"id": y.id, "name": y.name, "start": str(y.start_date), "end": str(y.end_date)} for y in years],
            "departments": [{"id": d.id, "name": d.name, "code": d.code} for d in self._records("op.department", [("active", "=", True)]).sorted("id")],
            "courses": [{"id": c.id, "name": c.name, "code": c.code, "department_id": c.department_id.id, "level": c.campus_level, "award": c.campus_award or ""} for c in self._records("op.course", [("active", "=", True)])],
            "batches": [{"id": b.id, "name": b.name, "course_id": b.course_id.id, "term_id": b.campus_term_id.id} for b in self._records("op.batch", [("campus_year_id", "=", year.id), ("active", "=", True)])],
            "terms": [{"id": t.id, "name": t.name, "course_id": t.campus_course_id.id} for t in self._records("op.academic.term", [("academic_year_id", "=", year.id)])],
            "enrolments": [{"id": e.id, "name": e.student_id.name + " · " + (e.student_id.gr_no or ""), "course_id": e.course_id.id} for e in enrolments],
            "heads": [{"id": h.id, "name": h.name, "code": h.default_code or "—", "category": h.campus_fee_category,
                "frequency": h.campus_fee_frequency, "optional": h.campus_fee_optional, "active": h.active, "tax": ", ".join(h.taxes_id.mapped("name")) or "No tax configured",
                "owned": h.company_id == self.env.company, "account_id": h.property_account_income_id.id, "tax_id": h.taxes_id[:1].id} for h in heads],
            "plans": plan_rows, "accounts": accounts, "invoices": invoice_rows, "followups": followups, "monthly": monthly_rows,
            "receipts": [{"id": p.id, "name": p.campus_receipt_number, "date": str(p.date), "student": p.campus_invoice_id.campus_student_id.name,
                "register": p.campus_invoice_id.campus_student_id.gr_no, "method": dict(p._fields["campus_method"].selection).get(p.campus_method, "Other"),
                "reference": p.campus_reference or "—", "amount": p.amount, "status": "Reversed" if p.campus_reversal_id else "Recorded" if p.campus_method == "cash" else "Settled" if p.is_matched else "Awaiting settlement"} for p in receipts],
            "journals": [{"id": j.id, "name": j.name, "type": j.type} for j in journals],
            "income_accounts": [{"id": a.id, "name": a.code + " · " + a.name} for a in self._records("account.account", [("account_type", "in", ["income", "income_other"])])],
            "taxes": [{"id": t.id, "name": t.name} for t in self._records("account.tax", [("type_tax_use", "=", "sale"), ("active", "=", True)])],
            "can_write": self.env.user.has_group("ideastone_erp.group_mvp_accountant"), "can_publish": self.env.user.has_group("ideastone_erp.group_mvp_owner"),
            "summary": {"income": sum(r["income"] for r in monthly_rows), "expense": sum(r["expense"] for r in monthly_rows),
                "dues": sum(posted.mapped("amount_residual")), "billed": sum(posted.mapped("amount_total")), "overdue": sum(overdue.mapped("amount_residual")),
                "due_soon": sum(i.amount_residual for i in posted if i.invoice_date_due and today <= i.invoice_date_due <= today + timedelta(days=14)),
                "unassigned": len([a for a in accounts if a["status"] == "Unassigned"]), "contacted": len(contacts.filtered(lambda c: c.contacted_on.date() >= today - timedelta(days=today.weekday()))),
                "promises": len([r for r in followups if r["status"] == "Promise to pay"]),
                "pending_expenses": len(self._records("account.move", [("move_type", "=", "in_invoice"), ("state", "=", "draft"), ("invoice_date", ">=", first), ("invoice_date", "<=", last)]))}}

    @api.model
    def save_head(self, values, record_id=0):
        self._check(write=True)
        allowed = {"name", "default_code", "campus_fee_category", "campus_fee_frequency", "campus_fee_optional", "property_account_income_id", "tax_id"}
        if not isinstance(values, dict) or set(values) - allowed or not isinstance(values.get("name"), str) or not values["name"].strip() or len(values["name"]) > 200:
            raise ValidationError(_("Enter a valid fee head name and supported fields."))
        vals = dict(values)
        tax_id = vals.pop("tax_id", False)
        if tax_id:
            self._record("account.tax", tax_id)
        if vals.get("property_account_income_id"):
            account = self._record("account.account", vals["property_account_income_id"])
            if account.account_type not in {"income", "income_other"}:
                raise ValidationError(_("Choose an income account for this fee head."))
        vals["taxes_id"] = [(6, 0, [tax_id] if tax_id else [])]
        if record_id:
            head = self._record("product.product", record_id)
            if not head.campus_fee_head:
                raise ValidationError(_("Choose a college fee head."))
            head.write(vals)
        else:
            head = self.env["product.product"].create(dict(vals, company_id=self.env.company.id, campus_fee_head=True, type="service"))
        return head.id

    @api.model
    def save_plan(self, values):
        self._check(write=True)
        if not isinstance(values, dict) or set(values) - {"name", "year_id", "course_id", "term_id", "quota", "study_year", "effective", "lines"} or not isinstance(values.get("name"), str) or not values["name"].strip() or len(values["name"]) > 200:
            raise ValidationError(_("Enter a valid structure name and its fee installments."))
        _years, year = self._year(values.get("year_id") or 0)
        course = self._record("op.course", values.get("course_id"))
        term = self._record("op.academic.term", values["term_id"]) if values.get("term_id") else self.env["op.academic.term"]
        if not year or values.get("quota") not in dict(QUOTAS) or type(values.get("study_year")) is not int or not 1 <= values["study_year"] <= 4 or term and (term.academic_year_id != year or term.campus_course_id and term.campus_course_id != course):
            raise ValidationError(_("Choose the current academic year, programme, quota and study year consistently."))
        lines = values.get("lines")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
            raise ValidationError(_("Add between one and fifty fee installments."))
        commands = []
        for line in lines:
            if not isinstance(line, dict) or set(line) - {"product_id", "amount", "date", "days"}:
                raise ValidationError(_("Enter a valid fee installment."))
            head = self.env["product.product"].search([("id", "=", line.get("product_id")), ("campus_fee_head", "=", True), ("company_id", "in", [False, self.env.company.id])])
            if not head or type(line.get("days", 0)) is not int or not 0 <= line.get("days", 0) <= 3650:
                raise ValidationError(_("Select a college fee head and valid due-day offset."))
            commands.append((0, 0, {"campus_product_id": head.id, "campus_amount": self._number(line.get("amount")), "due_date": fields.Date.to_date(line.get("date")) or False, "due_days": line.get("days", 0)}))
        if sum(c[2]["campus_amount"] for c in commands) <= 0:
            raise ValidationError(_("The fee structure must have a positive total."))
        version = max(self._records("op.fees.terms", [("campus_course_id", "=", course.id), ("campus_year_id", "=", year.id), ("campus_quota", "=", values["quota"]), ("campus_study_year", "=", values["study_year"])]).mapped("campus_version"), default=0) + 1
        plan = self.env["op.fees.terms"].create({"name": values["name"].strip(), "campus_managed": True, "campus_card_managed": True,
            "campus_course_id": course.id, "campus_year_id": year.id, "campus_term_id": term.id, "campus_quota": values["quota"],
            "campus_study_year": values["study_year"], "campus_version": version, "campus_effective_date": fields.Date.to_date(values.get("effective")) or False, "line_ids": commands})
        return plan.id

    @api.model
    def plan_action(self, record_id, action):
        self._check(write=True)
        plan = self._record("op.fees.terms", record_id)
        if action == "review":
            plan.action_campus_plan_review()
        elif action == "publish":
            plan.action_campus_plan_publish()
        else:
            raise ValidationError(_("Choose review or publication."))
        return True

    def _assignment(self, values):
        self._check(write=True)
        if not isinstance(values, dict) or set(values) - {"plan_id", "batch_id", "term_id", "date"}:
            raise ValidationError(_("Choose a fee plan and cohort."))
        plan = self._record("op.fees.terms", values.get("plan_id"))
        if not plan.campus_card_managed or plan.campus_plan_state != "published" or not plan.active:
            raise ValidationError(_("Select a published, active department structure."))
        domain = [("academic_years_id", "=", plan.campus_year_id.id), ("course_id", "=", plan.campus_course_id.id),
            ("campus_fee_quota", "=", plan.campus_quota), ("state", "=", "running"), ("student_id.active", "=", True)]
        for key, field in [("batch_id", "batch_id"), ("term_id", "academic_term_id")]:
            if values.get(key):
                self._record("op.batch" if key == "batch_id" else "op.academic.term", values[key])
                domain.append((field, "=", values[key]))
        if plan.campus_term_id:
            domain.append(("academic_term_id", "=", plan.campus_term_id.id))
        enrolments = self._records("op.student.course", domain).filtered(lambda e: (e.academic_term_id.campus_sequence + 1) // 2 == plan.campus_study_year)
        if len(enrolments) > 500:
            raise ValidationError(_("Select a smaller batch (maximum 500 enrolments per assignment)."))
        existing = self._records("op.student.fees.details", [("fees_line_id", "in", plan.line_ids.ids), ("campus_year_id", "=", plan.campus_year_id.id), ("student_id", "in", enrolments.student_id.ids)])
        assigned = {(r.student_id.id, r.fees_line_id.id) for r in existing}
        missing = [(e, line) for e in enrolments for line in plan.line_ids if (e.student_id.id, line.id) not in assigned]
        return plan, enrolments, existing, missing

    @api.model
    def preview_assignment(self, values):
        _plan, enrolments, existing, missing = self._assignment(values)
        return {"eligible": len(enrolments), "assigned": len(existing.student_id), "new": len({e.id for e, _line in missing}),
            "amount": sum(line.campus_amount for _e, line in missing), "duplicates": len(existing), "installments": len(missing)}

    @api.model
    def commit_assignment(self, values):
        plan, enrolments, _existing, _missing = self._assignment(values)
        date = fields.Date.to_date(values.get("date"))
        if not date:
            raise ValidationError(_("Choose a base due date."))
        for enrolment in enrolments.sorted("id"):
            self.env["campus.fee.assignment.wizard"].create({"enrolment_id": enrolment.id, "structure_id": plan.id, "date_from": date}).action_assign()
        return self.preview_assignment(values)

    @api.model
    def prepare_payment(self, values):
        self._check(write=True)
        if not isinstance(values, dict) or set(values) - {"invoice_id", "amount", "method", "reference", "journal_id", "note"}:
            raise ValidationError(_("Enter the supported payment details."))
        invoice = self._record("account.move", values.get("invoice_id"))
        self._record("account.journal", values.get("journal_id"))
        amount = self._number(values.get("amount"))
        if not invoice.campus_student_id or invoice.state != "posted" or amount <= 0 or amount > invoice.amount_residual:
            raise ValidationError(_("Select a posted student invoice and an amount within its unpaid balance."))
        draft = self.env["campus.fee.payment.wizard"].create({"invoice_id": invoice.id, "journal_id": values["journal_id"], "amount": amount,
            "method": values.get("method"), "reference": values.get("reference") or "", "campus_note": values.get("note") or ""})
        return draft.id

    @api.model
    def post_payment(self, wizard_id):
        self._check(write=True)
        draft = self._record("campus.fee.payment.wizard", wizard_id)
        if draft.create_uid != self.env.user:
            raise AccessError(_("This payment request belongs to another user."))
        result = draft.action_pay()
        if draft.campus_note and not draft.payment_id.campus_fee_note:
            draft.payment_id.write({"campus_fee_note": draft.campus_note})
        return result

    @api.model
    def log_contact(self, values):
        self._check(write=True)
        if not isinstance(values, dict) or set(values) - {"invoice_id", "channel", "outcome", "next_action", "next_date", "promise"}:
            raise ValidationError(_("Enter the contact outcome and next action."))
        self._record("account.move", values.get("invoice_id"))
        return self.env["campus.fee.contact"].create(values).id

    @api.model
    def open_record(self, kind, record_id):
        self._check()
        models_map = {"student": "op.student", "invoice": "account.move", "receipt": "account.payment", "fee": "op.student.fees.details"}
        if kind not in models_map:
            raise ValidationError(_("Choose a supported finance record."))
        record = self._record(models_map[kind], record_id)
        if kind == "receipt":
            return record.action_campus_receipt()
        if kind == "student":
            action = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp.mvp_fees")
            return dict(action, target="new", domain=[("company_id", "=", self.env.company.id), ("student_id", "=", record.id), ("campus_managed", "=", True)],
                context=dict(self.env.context, campus_module="fees", default_student_id=record.id, default_company_id=self.env.company.id))
        if kind == "invoice" and not record.campus_student_id:
            raise AccessError(_("Select a student fee invoice."))
        return {"type": "ir.actions.act_window", "res_model": models_map[kind], "res_id": record.id, "views": [(False, "form")], "target": "new", "context": dict(self.env.context, campus_module="fees")}

    @api.model
    def source_action(self, kind):
        self._check()
        sources = {"heads": "mvp_fee_heads", "invoices": "mvp_fees", "accounts": "mvp_fees"}
        if kind not in sources:
            raise ValidationError(_("Choose a supported finance register."))
        action = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp." + sources[kind])
        action["domain"] = [("company_id", "=", self.env.company.id), ("campus_fee_head" if kind == "heads" else "campus_managed", "=", True)]
        action["context"] = dict(self.env.context, campus_module="fees")
        return action

    @api.model
    def create_invoice(self, values):
        self._check(write=True)
        if not isinstance(values, dict) or set(values) - {"enrolment_id", "product_id", "amount", "date"}:
            raise ValidationError(_("Enter the student, fee head, amount and due date."))
        enrolment = self._record("op.student.course", values.get("enrolment_id"))
        head = self.env["product.product"].search([("id", "=", values.get("product_id")), ("campus_fee_head", "=", True), ("company_id", "in", [False, self.env.company.id])])
        amount = self._number(values.get("amount"))
        if not head or amount <= 0 or enrolment.state != "running":
            raise ValidationError(_("Choose an active enrolment, college fee head and positive amount."))
        fee = self.env["op.student.fees.details"].create({"student_id": enrolment.student_id.id, "course_id": enrolment.course_id.id,
            "batch_id": enrolment.batch_id.id, "campus_year_id": enrolment.academic_years_id.id, "product_id": head.id,
            "amount": amount, "date": fields.Date.to_date(values.get("date")), "campus_managed": True, "state": "draft"})
        fee.get_invoice()
        return fee.invoice_id.id
