from odoo.exceptions import AccessError, ValidationError

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
        ("student_complaint", "Complaint on a student"),
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
    complaint_category = fields.Char()
    service_area = fields.Selection([("service", "Service request"), ("maintenance", "Maintenance")], default="service")
    service_category = fields.Selection([
        ("it", "IT & network"), ("facilities", "Facilities"), ("transport", "Transport"),
        ("housekeeping", "Housekeeping"), ("electrical", "Electrical"),
    ])
    service_priority = fields.Selection([("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal")
    service_location = fields.Char()
    service_contact = fields.Char()
    service_team = fields.Char()
    document = fields.Binary(attachment=True)
    filename = fields.Char()

    def _faculty_self_service(self):
        return not self.env.su and self.env.user.has_group("openeducat_core.group_op_faculty") and not (
            self.env.user.has_group("ideastone_erp.group_services") or self.env.user.has_group("ideastone_erp.group_manager")
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._faculty_self_service():
            if any(v.get("requester_id", self.env.uid) != self.env.uid for v in vals_list):
                raise AccessError(_("Submit service requests under your own account."))
        return super().create(vals_list)

    def write(self, vals):
        if "requester_id" in vals and self._faculty_self_service():
            raise AccessError(_("A service operator must reassign a faculty service request."))
        if "service_team" in vals and self._faculty_self_service():
            raise AccessError(_("Only a service operator can assign a campus team."))
        if set(vals) == {"resolution"} and self and all(rec.state == "approved" for rec in self):
            if not self.env.user.has_group("ideastone_erp.group_manager"):
                raise AccessError(_("Campus manager approval is required to record a resolution."))
            self._lock()
            return self._set_system_values(vals)
        return super().write(vals)

    @api.constrains("date_from", "date_to", "amount", "kind", "requested_course_id", "student_id", "complaint_category", "company_id")
    def _check_values(self):
        for rec in self:
            if rec.amount < 0 or rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Check the amount and request date range."))
            if rec.kind == "transfer" and (not rec.student_id or not rec.requested_course_id):
                raise ValidationError(_("Programme transfer requires a student and destination programme."))
            if rec.kind == "student_complaint" and (not rec.student_id or not rec.complaint_category):
                raise ValidationError(_("A student complaint requires the student, complaint type and description."))
            if rec.student_id.company_id and rec.student_id.company_id != rec.company_id:
                raise ValidationError(_("The student and service request must belong to the same college."))

    def _validate_transition(self, target):
        if target == "done" and not self.resolution:
            raise ValidationError(_("Record the resolution before completing a service request."))
