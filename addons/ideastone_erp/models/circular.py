from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class Circular(models.Model):
    _name = "campus.circular"
    _description = "Published institutional circular"
    _inherit = "campus.approval"
    _order = "date_from desc"

    reference = fields.Char(required=True, copy=False)
    date_from = fields.Date(required=True, default=fields.Date.today)
    date_to = fields.Date()
    audience = fields.Selection([
        ("all", "Everyone"), ("student", "Students"), ("parent", "Parents"), ("faculty", "Staff"),
    ], required=True, default="all")
    body = fields.Html(required=True, sanitize=True)
    attachment_ids = fields.Many2many("ir.attachment")

    _sql_constraints = [("circular_reference", "unique(company_id, reference)", "Circular reference must be unique.")]

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Circular expiry must follow publication date."))
