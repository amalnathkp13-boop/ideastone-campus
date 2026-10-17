from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class AttendanceSheet(models.Model):
    _inherit = "op.attendance.sheet"

    campus_subject_id = fields.Many2one(related="session_id.subject_id", store=True, string="Subject")

    @api.constrains("faculty_id", "session_id", "register_id")
    def _check_teaching_allocation(self):
        if self.env.su or self.env.user.has_group("openeducat_attendance.group_op_attendance_manager"):
            return
        for rec in self:
            if (not rec.session_id or rec.session_id.faculty_id.user_id != self.env.user or
                    rec.faculty_id.user_id != self.env.user or rec.session_id.batch_id != rec.batch_id):
                raise AccessError(_("Faculty may record attendance only for their assigned timetable session and batch."))


class AttendanceLine(models.Model):
    _inherit = "op.attendance.line"

    @api.constrains("attendance_id", "student_id")
    def _check_student_allocation(self):
        if self.env.su or self.env.user.has_group("openeducat_attendance.group_op_attendance_manager"):
            return
        for rec in self:
            rec.attendance_id._check_teaching_allocation()
            if rec.attendance_id.batch_id not in rec.student_id.course_detail_ids.batch_id:
                raise AccessError(_("The student must be enrolled in the assigned batch."))

    def write(self, vals):
        self.attendance_id._check_teaching_allocation()
        return super().write(vals)


class Exam(models.Model):
    _inherit = "op.exam"

    campus_exam_kind = fields.Selection([
        ("unclassified", "Unclassified"), ("institution", "Institution test"),
        ("university", "University examination"), ("autonomous", "Autonomous ESE"),
    ], required=True, default="unclassified", string="Examination category",
        help="Classify the examination explicitly before using category-specific reports.")

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("state") == "done" for v in vals_list) and not self.env.su and not (self.env.user.has_group("openeducat_exam.group_op_exam_admin") or self.env.user.has_group("ideastone_erp.group_mvp_exams")):
            raise AccessError(_("Examination administrator permission is required to publish results."))
        return super().create(vals_list)

    def write(self, vals):
        if (vals.get("state") == "done" or any(r.state == "done" for r in self)) and not self.env.su and not (self.env.user.has_group("openeducat_exam.group_op_exam_admin") or self.env.user.has_group("ideastone_erp.group_mvp_exams")):
            raise AccessError(_("Examination administrator permission is required to publish or revise released results."))
        return super().write(vals)


class ResultLine(models.Model):
    _inherit = "op.result.line"

    @api.constrains("marks", "exam_id")
    def _check_mark_boundary(self):
        for rec in self:
            if rec.marks < 0 or rec.marks > rec.exam_id.total_marks:
                raise ValidationError(_("Marks must be between zero and the examination maximum."))

    def _check_published(self):
        if self.filtered(lambda r: r.exam_id.state == "done") and not self.env.su and not self.env.user.has_group("openeducat_exam.group_op_exam_admin"):
            raise AccessError(_("Released marks can only be revised by the examination administrator."))

    def write(self, vals):
        self._check_published()
        if vals.get("exam_id"):
            self.browse().new({"exam_id": vals["exam_id"]})._check_published()
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.new({"exam_id": vals.get("exam_id")})._check_published()
        return super().create(vals_list)

    def unlink(self):
        self._check_published()
        return super().unlink()
