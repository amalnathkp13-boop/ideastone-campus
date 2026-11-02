import math

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class AccountantSpending(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _client_action_models(self):
        actions = super()._client_action_models()
        actions.update({"accountant_spending_" + mode: "account.move" for mode in ("events", "maintenance")})
        return actions

    @api.model
    def get_accountant_spending(self):
        self._accountant_access()
        company = self.env.company
        bills = self.env["account.move"].search([("company_id", "=", company.id),
            ("move_type", "in", ["in_invoice", "in_refund"]), ("state", "!=", "cancel"),
            ("campus_spend_category", "in", ["event", "maintenance"])], order="invoice_date desc, id desc")
        departments = self.env["op.department"].search([("company_id", "in", [False, company.id])], order="name")
        vendors = self.env["res.partner"].search([("company_id", "in", [False, company.id]),
            "|", ("supplier_rank", ">", 0), ("id", "in", bills.partner_id.ids)], order="name")

        def amount(bill, value):
            return bill.currency_id._convert(value, company.currency_id, company, bill.invoice_date or bill.date) * (
                -1 if bill.move_type == "in_refund" else 1)

        return {"today": str(fields.Date.context_today(self)), "currency": company.currency_id.symbol,
            "departments": [{"id": d.id, "name": d.name} for d in departments],
            "vendors": [{"id": v.id, "name": v.name} for v in vendors],
            "rows": [{"id": m.id, "name": m.name if m.state == "posted" else "—", "partner": m.partner_id.name,
                "date": str(m.invoice_date or m.date), "reference": m.ref or "—", "category": m.campus_spend_category,
                "department_id": m.campus_spend_department_id.id, "department": m.campus_spend_department_id.name or _("Unassigned"),
                "total": amount(m, m.amount_total),
                "due": amount(m, m.amount_residual if m.state == "posted" else m.amount_total),
                "state": m.state, "status": "Paid" if m.payment_state in ("paid", "reversed") else
                    "Partially Paid" if m.payment_state == "partial" else "Not Paid"} for m in bills]}

    @api.model
    def create_accountant_spending(self, values):
        self._accountant_access()
        allowed = {"vendor_id", "department_id", "category", "amount", "date", "reference"}
        if not isinstance(values, dict) or set(values) - allowed:
            raise ValidationError(_("Enter valid bill fields."))
        if values.get("category") not in ("event", "maintenance"):
            raise ValidationError(_("Choose an event or maintenance category."))
        amount = values.get("amount")
        if type(amount) not in (int, float) or not math.isfinite(amount) or amount <= 0:
            raise ValidationError(_("Enter a bill amount greater than zero."))
        company = self.env.company
        for key, model in (("vendor_id", "res.partner"), ("department_id", "op.department")):
            if type(values.get(key)) is not int or not self.env[model].search_count([
                    ("id", "=", values[key]), ("company_id", "in", [False, company.id])]):
                raise AccessError(_("Choose a vendor and department available in the active college."))
        try:
            day = fields.Date.to_date(values.get("date"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid bill date.")) from exc
        if not day:
            raise ValidationError(_("Choose a bill date."))
        journal = self.env["account.journal"].search([("company_id", "=", company.id), ("type", "=", "purchase")], limit=1)
        account = journal.default_account_id.filtered(lambda a: a.account_type.startswith("expense"))
        if not account:
            account = self.env["account.account"].search([("company_id", "=", company.id),
                ("account_type", "in", ["expense", "expense_direct_cost"]), ("deprecated", "=", False)], limit=1)
        if not journal or not account:
            raise ValidationError(_("Configure a purchase journal and expense account before entering bills."))
        reference = values.get("reference", "")
        if not isinstance(reference, str) or len(reference) > 250:
            raise ValidationError(_("Keep the reference within 250 characters."))
        bill = self.env["account.move"].create({"move_type": "in_invoice", "company_id": company.id,
            "partner_id": values["vendor_id"], "journal_id": journal.id, "invoice_date": day, "ref": reference,
            "currency_id": company.currency_id.id,
            "campus_spend_category": values["category"], "campus_spend_department_id": values["department_id"],
            "invoice_line_ids": [(0, 0, {"name": reference or dict(self.env["account.move"]._fields["campus_spend_category"].selection)[values["category"]],
                "quantity": 1, "price_unit": amount, "account_id": account.id, "tax_ids": [(5, 0, 0)]})]})
        return bill.id
