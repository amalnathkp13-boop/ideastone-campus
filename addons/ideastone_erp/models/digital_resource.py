from odoo import fields, models


class DigitalResource(models.Model):
    _name = "campus.digital.resource"
    _description = "Restricted digital library resource"
    _inherit = "campus.approval"

    subject_id = fields.Many2one("op.subject", ondelete="restrict")
    author = fields.Char()
    resource_type = fields.Selection([("book", "E-book"), ("notes", "Lecture notes"), ("journal", "Journal"), ("other", "Other")], required=True, default="book")
    batch_ids = fields.Many2many("op.batch", string="Permitted batches", help="An empty batch list permits all authenticated campus students and staff.")
    document = fields.Binary(attachment=True, required=True)
    filename = fields.Char(required=True)
    description = fields.Text()
