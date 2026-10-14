from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class Visitor(models.Model):
    _name = "campus.visitor"
    _description = "Visitor entry and closure"
    _inherit = "campus.record"
    _order = "entered_on desc"

    organization = fields.Char()
    phone = fields.Char()
    host_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    purpose = fields.Text(required=True)
    entered_on = fields.Datetime(required=True, default=fields.Datetime.now)
    exited_on = fields.Datetime()
    closing_notes = fields.Text()
    follow_up_date = fields.Date()

    @api.constrains("entered_on", "exited_on")
    def _check_times(self):
        for rec in self:
            if rec.exited_on and rec.exited_on < rec.entered_on:
                raise ValidationError(_("Visitor exit must follow entry."))

    def action_exit(self):
        if any(rec.exited_on for rec in self):
            raise ValidationError(_("Visitor entry is already closed."))
        return self.write({"exited_on": fields.Datetime.now()})
