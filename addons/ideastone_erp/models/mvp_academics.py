from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class CollegeSettings(models.Model):
    _inherit = "res.company"

    campus_attendance_threshold = fields.Float(default=75, string="Attendance shortage threshold (%)")
    campus_excused_policy = fields.Selection([
        ("exclude", "Exclude excused sessions"), ("present", "Count excused as present"),
        ("absent", "Count excused as absent"),
    ], default="exclude", required=True)
    campus_demo = fields.Boolean(string="Demonstration college", default=False)

    @api.constrains("campus_attendance_threshold")
    def _check_attendance_threshold(self):
        if any(not 0 <= rec.campus_attendance_threshold <= 100 for rec in self):
            raise ValidationError(_("Attendance threshold must be between 0 and 100."))


class AcademicYear(models.Model):
    _inherit = ["op.academic.year", "campus.mvp.mixin"]
    _name = "op.academic.year"

    code = fields.Char(index=True)
    campus_current = fields.Boolean(string="Current academic year")
    active = fields.Boolean(default=True)

    def _auto_init(self):
        result = super()._auto_init()
        self.env.cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS campus_one_current_year ON op_academic_year(company_id) WHERE campus_current AND active")
        return result

    @api.constrains("start_date", "end_date", "company_id", "campus_current")
    def _check_college_year(self):
        self._mvp_company()
        for rec in self:
            if rec.end_date < rec.start_date:
                raise ValidationError(_("Academic year end must follow its start."))


class Department(models.Model):
    _inherit = "op.department"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)
    _sql_constraints = [("campus_department_code", "unique(company_id, code)", "Department code must be unique in this college.")]


class Programme(models.Model):
    _inherit = "op.course"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    campus_duration = fields.Integer(string="Duration (semesters)", default=8)
    campus_award = fields.Char(string="Award / programme type")

    @api.constrains("department_id", "company_id", "campus_duration")
    def _check_programme_scope(self):
        for rec in self:
            if rec.campus_duration < 1 or (rec.department_id.company_id and rec.department_id.company_id != rec.company_id):
                raise ValidationError(_("Choose a department in this college and a positive programme duration."))


class AcademicTerm(models.Model):
    _inherit = "op.academic.term"

    campus_sequence = fields.Integer(string="Semester / year number", default=1)
    campus_course_id = fields.Many2one("op.course", string="Programme")

    @api.constrains("term_start_date", "term_end_date", "academic_year_id", "campus_sequence", "company_id")
    def _check_term_scope(self):
        for rec in self:
            year = rec.academic_year_id
            if rec.campus_sequence < 1 or not year.start_date <= rec.term_start_date <= rec.term_end_date <= year.end_date:
                raise ValidationError(_("Semester dates must be inside the academic year with a positive sequence."))
            if year.company_id != rec.company_id:
                raise ValidationError(_("Semester and academic year must belong to the same college."))


class Section(models.Model):
    _inherit = "op.batch"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    campus_year_id = fields.Many2one("op.academic.year", string="Academic year", ondelete="restrict")
    campus_term_id = fields.Many2one("op.academic.term", string="Semester", ondelete="restrict")

    @api.constrains("campus_year_id", "campus_term_id", "course_id", "company_id")
    def _check_section_scope(self):
        for rec in self:
            if rec.campus_year_id and rec.campus_year_id.company_id != rec.company_id:
                raise ValidationError(_("Section academic year belongs to another college."))
            if rec.campus_term_id and (rec.campus_term_id.academic_year_id != rec.campus_year_id or
                    rec.campus_term_id.campus_course_id and rec.campus_term_id.campus_course_id != rec.course_id):
                raise ValidationError(_("Section semester must match its programme and academic year."))
            if rec.course_id.company_id and rec.course_id.company_id != rec.company_id:
                raise ValidationError(_("Section programme belongs to another college."))


class Subject(models.Model):
    _inherit = "op.subject"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    campus_term_id = fields.Many2one("op.academic.term", string="Semester")
    campus_credits = fields.Float(string="Credits")
    campus_max_marks = fields.Integer(string="Default maximum marks", default=100)


class Enrolment(models.Model):
    _inherit = ["op.student.course", "campus.mvp.mixin"]
    _name = "op.student.course"

    company_id = fields.Many2one(related="student_id.company_id", store=True, index=True)
    campus_date_from = fields.Date(string="Effective from", default=fields.Date.context_today)
    campus_date_to = fields.Date(string="Effective until")
    campus_reason = fields.Text(string="Transfer / completion reason")

    @api.constrains("student_id", "course_id", "batch_id", "academic_years_id", "academic_term_id", "campus_date_from", "campus_date_to")
    def _check_enrolment_scope(self):
        self._mvp_company("student_id", "course_id", "batch_id", "academic_years_id")
        for rec in self:
            if rec.batch_id and rec.batch_id.course_id != rec.course_id:
                raise ValidationError(_("Enrolment section must belong to the selected programme."))
            if rec.campus_date_to and rec.campus_date_to < rec.campus_date_from:
                raise ValidationError(_("Enrolment end must follow its start."))
            if rec.academic_term_id and rec.academic_term_id.academic_year_id != rec.academic_years_id:
                raise ValidationError(_("Enrolment semester must match its academic year."))

    def write(self, vals):
        if {"student_id", "course_id", "batch_id", "academic_years_id", "academic_term_id"}.intersection(vals):
            for rec in self.filtered("academic_years_id"):
                if rec.env["op.attendance.line"].sudo().search_count([("student_id", "=", rec.student_id.id), ("batch_id", "=", rec.batch_id.id)]):
                    raise ValidationError(_("Retain this historic enrolment. Finish it and create a new placement with an effective date."))
        if vals.get("state") == "finished" and any(rec.academic_years_id for rec in self) and not (vals.get("campus_reason") or all(rec.campus_reason for rec in self)):
            raise ValidationError(_("Record a reason before finishing or transferring an enrolment."))
        result = super().write(vals)
        if {"state", "batch_id", "course_id"}.intersection(vals):
            self._mvp_log("Enrolment updated", details={k: str(v) for k, v in vals.items()})
        return result
