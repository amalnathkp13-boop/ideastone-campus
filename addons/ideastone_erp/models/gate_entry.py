from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class GateEntry(models.Model):
    _name = "campus.gate.entry"
    _description = "Hostel and library gate register"
    _inherit = "campus.record"
    _order = "entered_on desc"

    area = fields.Selection([("hostel", "Hostel"), ("library", "Library")], required=True)
    student_id = fields.Many2one("op.student", ondelete="restrict")
    faculty_id = fields.Many2one("op.faculty", ondelete="restrict")
    entered_on = fields.Datetime(required=True, default=fields.Datetime.now)
    exited_on = fields.Datetime()
    reason = fields.Char()

    @api.constrains("student_id", "faculty_id", "entered_on", "exited_on")
    def _check_entry(self):
        for rec in self:
            if bool(rec.student_id) == bool(rec.faculty_id):
                raise ValidationError(_("Choose exactly one student or faculty member."))
            if rec.exited_on and rec.exited_on < rec.entered_on:
                raise ValidationError(_("Exit must follow entry."))

    def action_exit(self):
        if any(rec.exited_on for rec in self):
            raise ValidationError(_("This gate visit is already closed."))
        return self.write({"exited_on": fields.Datetime.now()})
