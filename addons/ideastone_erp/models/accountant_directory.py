from odoo import api, fields, models


class AccountantDirectory(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _client_action_models(self):
        actions = super()._client_action_models()
        actions.update({"accountant_directory_" + mode: "op.student" for mode in ("students", "pending", "accounts")})
        return actions

    @api.model
    def get_accountant_directory(self):
        self._accountant_access()
        company = self.env.company
        enrolments = self.env["op.student.course"].search([
            ("company_id", "=", company.id), ("state", "=", "running"),
            ("student_id.active", "=", True)], order="id desc")
        invoices = self.env["account.move"].search([
            ("company_id", "=", company.id), ("campus_student_id", "in", enrolments.student_id.ids),
            ("state", "=", "posted"), ("move_type", "=", "out_invoice")])
        today = fields.Date.context_today(self)
        rows, seen = [], set()
        for enrolment in enrolments:
            student = enrolment.student_id
            if student.id in seen:
                continue
            seen.add(student.id)
            bills = invoices.filtered(lambda m, student=student: m.campus_student_id == student)
            due = bills.filtered(lambda m: m.amount_residual > 0)
            department = enrolment.course_id.department_id
            payments = bills._get_reconciled_payments().filtered(lambda p: p.state == "posted")
            ledger = [{"id": "payment-%s" % p.id, "record_id": p.id, "model": "account.payment", "date": str(p.date),
                "name": p.name, "description": p.ref or "Student fee payment", "mode": p.payment_method_line_id.name,
                "total": p.amount, "paid": p.amount, "pending": 0, "status": "Paid"} for p in payments]
            ledger += [{"id": "invoice-%s" % m.id, "record_id": m.id, "model": "account.move", "date": str(m.invoice_date_due or m.date),
                "name": m.name, "description": m.ref or "Remaining student fees", "mode": "—", "total": m.amount_residual,
                "paid": 0, "pending": m.amount_residual, "status": "Pending"} for m in due]
            rows.append({"id": student.id, "number": student.gr_no or str(student.id), "name": student.name,
                "phone": student.partner_id.phone or "", "department_id": department.id,
                "department": department.name or "Unassigned", "code": department.code or "—",
                "year": enrolment.academic_years_id.name or "Unassigned", "section": enrolment.batch_id.name or "Unassigned",
                "semester": enrolment.academic_term_id.name or "—", "total": sum(bills.mapped("amount_total")),
                "paid": sum(m.amount_total - m.amount_residual for m in bills), "pending": sum(bills.mapped("amount_residual")),
                "due": str(min(due.mapped("invoice_date_due"))) if due and all(due.mapped("invoice_date_due")) else "—",
                "overdue": any((m.invoice_date_due or m.date) < today for m in due),
                "ledger": ledger})
        return {"rows": rows, "currency": company.currency_id.symbol}
