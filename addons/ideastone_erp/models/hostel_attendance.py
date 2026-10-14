from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class HostelAttendance(models.Model):
    _name = "campus.hostel.attendance"
    _description = "Hostel daily attendance"
    _inherit = "campus.record"

    allocation_id = fields.Many2one("campus.hostel.allocation", required=True, ondelete="restrict", check_company=True)
    student_id = fields.Many2one(related="allocation_id.student_id", store=True)
    date = fields.Date(required=True, default=fields.Date.today, index=True)
    present = fields.Boolean(default=True)
    remarks = fields.Char()

    _sql_constraints = [("presence_unique", "unique(allocation_id, date)", "Attendance already exists for this residence and date.")]

    @api.constrains("allocation_id", "date")
    def _check_residence(self):
        for rec in self:
            a = rec.allocation_id
            if a.state != "approved" or rec.date < a.date_from or a.date_to and rec.date > a.date_to:
                raise ValidationError(_("Attendance must fall within an approved residence."))
