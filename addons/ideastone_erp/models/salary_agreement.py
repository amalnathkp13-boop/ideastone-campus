from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class SalaryAgreement(models.Model):
    _name = "campus.salary.agreement"
    _description = "Approved salary terms"
    _inherit = "campus.approval"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict", check_company=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date()
    basic = fields.Monetary(required=True)
    allowance = fields.Monetary()
    fixed_deduction = fields.Monetary()
    tds = fields.Monetary("Monthly TDS")
    pf_rate = fields.Float("Employee PF rate (%)")
    esi_rate = fields.Float("Employee ESI rate (%)")
    pf_base = fields.Monetary("PF contribution base")
    esi_base = fields.Monetary("ESI contribution base")
    daily_hours = fields.Float(required=True, default=8)
    bank_reference = fields.Char("Payroll bank reference", groups="ideastone_erp.group_people")

    @api.constrains("date_from", "date_to", "basic", "allowance", "fixed_deduction", "tds", "pf_rate", "esi_rate", "pf_base", "esi_base", "daily_hours", "state")
    def _check_terms(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from or rec.daily_hours <= 0:
                raise ValidationError(_("Check salary agreement dates and daily hours."))
            if min(rec.basic, rec.allowance, rec.fixed_deduction, rec.tds, rec.pf_base, rec.esi_base) < 0 or not 0 <= rec.pf_rate <= 100 or not 0 <= rec.esi_rate <= 100:
                raise ValidationError(_("Salary amounts and contribution rates must be valid nonnegative values."))
            if rec.state == "approved":
                rec.employee_id.check_access_rights("write")
                self.env.cr.execute("SELECT id FROM hr_employee WHERE id=%s FOR UPDATE", [rec.employee_id.id])
                if self.sudo().search_count([
                    ("id", "!=", rec.id), ("employee_id", "=", rec.employee_id.id), ("state", "=", "approved"),
                    ("date_from", "<=", rec.date_to or "9999-12-31"),
                    "|", ("date_to", "=", False), ("date_to", ">=", rec.date_from),
                ]):
                    raise ValidationError(_("Approved salary agreements cannot overlap for an employee."))
