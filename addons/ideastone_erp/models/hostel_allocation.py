from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class HostelAllocation(models.Model):
    _name = "campus.hostel.allocation"
    _description = "Dated hostel residence"
    _inherit = "campus.approval"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict", index=True)
    room_id = fields.Many2one("campus.hostel.room", required=True, ondelete="restrict", check_company=True)
    date_from = fields.Date(required=True, default=fields.Date.today)
    date_to = fields.Date()
    food_preference = fields.Selection([("veg", "Vegetarian"), ("nonveg", "Non-vegetarian"), ("other", "Other")], default="veg")
    dietary_notes = fields.Text()
    emergency_phone = fields.Char()

    @api.constrains("student_id", "room_id", "date_from", "date_to", "state", "active")
    def _check_allocation(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Residence end date must follow the start date."))
            if rec.state != "approved":
                continue
            if not rec.active or not rec.room_id.active:
                raise ValidationError(_("Active residence requires an active room and allocation."))
            rec.room_id._lock()
            self.env.cr.execute("SELECT id FROM op_student WHERE id = %s FOR UPDATE", [rec.student_id.id])
            others = self.sudo().search([
                ("id", "!=", rec.id), ("state", "=", "approved"),
                ("date_from", "<=", rec.date_to or "9999-12-31"),
                "|", ("date_to", "=", False), ("date_to", ">=", rec.date_from),
            ])
            if others.filtered(lambda a, rec=rec: a.student_id == rec.student_id):
                raise ValidationError(_("The student already has a residence for this date range."))
            # Count occupancy at every boundary; non-overlapping bookings may share a room.
            room_others = others.filtered(lambda a, rec=rec: a.room_id == rec.room_id)
            boundaries = {rec.date_from} | {a.date_from for a in room_others if a.date_from >= rec.date_from}
            for day in boundaries:
                occupants = sum(a.date_from <= day and (not a.date_to or day <= a.date_to) for a in room_others)
                if occupants + 1 > rec.room_id.capacity:
                    raise ValidationError(_("Room capacity would be exceeded during this residence."))

    def _validate_transition(self, target):
        if target == "approved" and not self.room_id.active:
            raise ValidationError(_("Choose an active hostel room."))

    def write(self, vals):
        result = super().write(vals)
        if "state" in vals:
            for student in self.student_id:
                resident = bool(self.sudo().search_count([("student_id", "=", student.id), ("state", "=", "approved")]))
                student.sudo().write({"is_hosteller": resident})
        return result
