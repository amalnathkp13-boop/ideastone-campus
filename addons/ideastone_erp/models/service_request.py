from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class ServiceRequest(models.Model):
    _name = "campus.service.request"
    _description = "Staff and student service requests"
    _inherit = "campus.approval"
    _order = "date desc"

    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict")
    kind = fields.Selection([
        ("grievance", "Grievance"), ("certificate", "TC / conduct certificate"),
        ("transfer", "Programme transfer"), ("alternate", "Alternate teaching hour"),
        ("room", "Room request"), ("travel", "Travel proposal"), ("training", "Training request"),
        ("work", "Work / service order"), ("advance", "Payment / salary advance proposal"),
    ], required=True, default="grievance")
    student_id = fields.Many2one("op.student", ondelete="restrict")
    faculty_id = fields.Many2one("op.faculty", ondelete="restrict")
    replacement_id = fields.Many2one("op.faculty", string="Replacement faculty", ondelete="restrict")
    department_id = fields.Many2one("op.department", ondelete="restrict")
    requested_course_id = fields.Many2one("op.course", string="Requested programme", ondelete="restrict")
    date = fields.Date(required=True, default=fields.Date.today)
    date_from = fields.Date()
    date_to = fields.Date()
    amount = fields.Monetary()
    description = fields.Text(required=True)
    resolution = fields.Text()
    document = fields.Binary(attachment=True)
    filename = fields.Char()

    @api.constrains("date_from", "date_to", "amount", "kind", "requested_course_id", "student_id")
    def _check_values(self):
        for rec in self:
            if rec.amount < 0 or rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Check the amount and request date range."))
            if rec.kind == "transfer" and (not rec.student_id or not rec.requested_course_id):
                raise ValidationError(_("Programme transfer requires a student and destination programme."))

    def _validate_transition(self, target):
        if target == "done" and not self.resolution:
            raise ValidationError(_("Record the resolution before completing a service request."))
