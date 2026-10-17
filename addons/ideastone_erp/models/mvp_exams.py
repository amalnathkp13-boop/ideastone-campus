from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class ExamSession(models.Model):
    _inherit = "op.exam.session"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    campus_year_id = fields.Many2one("op.academic.year", string="Academic year")


class GradeConfiguration(models.Model):
    _inherit = "op.grade.configuration"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)


class Exam(models.Model):
    _inherit = ["op.exam", "campus.mvp.mixin"]
    _name = "op.exam"

    company_id = fields.Many2one(related="session_id.company_id", store=True, index=True)
    campus_year_id = fields.Many2one(related="session_id.campus_year_id", store=True)
    campus_managed = fields.Boolean(default=False, copy=False)
    campus_state = fields.Selection([
        ("draft", "Draft"), ("entry", "Entry in progress"), ("submitted", "Submitted"),
        ("locked", "Locked / approved"), ("published", "Published"),
    ], default="draft", readonly=True, tracking=True)
    campus_result_ids = fields.One2many("op.result.line", "exam_id", string="Marks roster")
    campus_grade_ids = fields.Many2many("op.grade.configuration", string="Grade rules")
    campus_reopen_reason = fields.Text(string="Reopen reason")
    campus_published_by = fields.Many2one("res.users", readonly=True, copy=False)
    campus_published_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        protected = {"campus_state", "campus_published_by", "campus_published_on"}
        if any(protected.intersection(v) or v.get("campus_managed") and v.get("state", "draft") != "draft" for v in vals_list):
            raise AccessError(_("Create exams in draft and use the result publication workflow."))
        return super().create(vals_list)

    def write(self, vals):
        managed = self.filtered("campus_managed")
        if managed:
            if {"campus_managed", "campus_state", "campus_published_by", "campus_published_on", "state"}.intersection(vals):
                raise AccessError(_("Use the examination workflow to change publication status."))
            if any(r.campus_state in {"submitted", "locked", "published"} for r in managed) and set(vals) - {"campus_reopen_reason", "message_follower_ids", "activity_ids"}:
                raise ValidationError(_("Submitted or published examinations must be explicitly reopened before editing."))
            if managed.campus_result_ids and {"session_id", "subject_id"}.intersection(vals):
                raise ValidationError(_("A loaded examination roster retains its original section and subject."))
        return super().write(vals)

    def _campus_can_enter(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_exams"):
            if any(self.env.uid not in rec.responsible_id.user_id.ids for rec in self):
                raise AccessError(_("Only assigned faculty or an examination officer may enter these marks."))

    def action_campus_roster(self):
        self._campus_can_enter()
        self._mvp_lock()
        for rec in self:
            if not rec.campus_managed or rec.campus_state not in {"draft", "entry"}:
                raise ValidationError(_("Load a marks roster before submitting the examination."))
            if not rec.campus_year_id or not rec.session_id:
                raise ValidationError(_("Configure an examination session with academic year, programme and section."))
            rec._mvp_company("session_id", "subject_id")
            day = fields.Datetime.context_timestamp(rec, rec.start_time).date()
            enrolments = self.env["op.student.course"].search([
                ("batch_id", "=", rec.batch_id.id), ("academic_years_id", "=", rec.campus_year_id.id),
                ("campus_date_from", "<=", day), "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", day)])
            for enrolment in enrolments.filtered(lambda e, existing=rec.campus_result_ids.student_id: e.student_id not in existing):
                self.env["op.result.line"].create({"exam_id": rec.id, "student_id": enrolment.student_id.id,
                    "marks": 0, "campus_entered": False, "campus_enrolment_id": enrolment.id})
            super(Exam, rec).write({"campus_state": "entry"})
        return True

    def action_campus_submit(self):
        self._campus_can_enter()
        self._mvp_lock()
        for rec in self:
            if rec.campus_state != "entry" or not rec.campus_result_ids or rec.campus_result_ids.filtered(lambda r: not r.campus_entered):
                raise ValidationError(_("Enter every student's marks, including explicitly confirmed zero marks, before submission."))
            super(Exam, rec).write({"campus_state": "submitted"})
            rec._mvp_log("Examination marks submitted")
        return True

    def action_campus_lock(self):
        self._mvp_require("ideastone_erp.group_mvp_exams")
        self._mvp_lock()
        for rec in self:
            if rec.campus_state != "submitted":
                raise ValidationError(_("Submit complete marks before approval."))
            super(Exam, rec).write({"campus_state": "locked"})
            rec._mvp_log("Examination marks approved and locked")
        return True

    def action_campus_publish(self):
        self._mvp_require("ideastone_erp.group_mvp_exams")
        self._mvp_lock()
        for rec in self:
            if rec.campus_state != "locked":
                raise ValidationError(_("Approve and lock marks before publication."))
            grades = rec.campus_grade_ids.sorted("min_per")
            if not grades or grades[0].min_per != 0 or grades[-1].max_per != 100:
                raise ValidationError(_("Configure a complete grade scale covering 0 through 100 before publication."))
            for pos, grade in enumerate(grades):
                if grade.company_id != rec.company_id or grade.min_per < 0 or grade.max_per < grade.min_per or (pos and grade.min_per != grades[pos - 1].max_per + 1):
                    raise ValidationError(_("Grade bands must belong to this college and cover consecutive, non-overlapping integer percentage bands."))
            super(Exam, rec).write({"campus_state": "published", "state": "done", "campus_published_by": self.env.uid, "campus_published_on": fields.Datetime.now()})
            rec._mvp_log("Examination results published")
        return True

    def action_campus_reopen(self):
        self._mvp_require("ideastone_erp.group_mvp_exams")
        self._mvp_lock()
        for rec in self:
            if rec.campus_state not in {"submitted", "locked", "published"} or not (rec.campus_reopen_reason or "").strip():
                raise ValidationError(_("An examination officer must enter a reason before reopening submitted or published marks."))
            rec._mvp_log("Examination reopened", rec.campus_reopen_reason,
                         {"previous_state": rec.campus_state, "marks": [{"student_id": r.student_id.id, "marks": r.marks} for r in rec.campus_result_ids]})
            super(Exam, rec).write({"campus_state": "entry", "state": "held", "campus_reopen_reason": False})
        return True

    def unlink(self):
        if self.filtered(lambda r: r.campus_managed and (r.campus_state != "draft" or r.campus_result_ids)):
            raise ValidationError(_("Retain examinations with academic history."))
        return super().unlink()


class ResultLine(models.Model):
    _inherit = "op.result.line"

    company_id = fields.Many2one(related="exam_id.company_id", store=True, index=True)
    campus_entered = fields.Boolean(string="Marks entered / zero confirmed", default=False)
    campus_enrolment_id = fields.Many2one("op.student.course", readonly=True, ondelete="restrict")
    campus_percentage = fields.Float(compute="_compute_campus_percentage", store=True)

    @api.depends("marks", "exam_id.total_marks", "campus_entered")
    def _compute_campus_percentage(self):
        for rec in self:
            rec.campus_percentage = rec.marks * 100 / rec.exam_id.total_marks if rec.campus_entered and rec.exam_id.total_marks else 0

    @api.depends("marks", "campus_entered", "exam_id.campus_managed", "exam_id.min_marks")
    def _compute_status(self):
        super()._compute_status()
        for rec in self.filtered(lambda r: r.exam_id.campus_managed and not r.campus_entered):
            rec.status = False

    @api.depends("marks", "campus_entered", "exam_id.total_marks", "exam_id.campus_grade_ids")
    def _compute_grade(self):
        super()._compute_grade()
        for rec in self.filtered(lambda r: r.exam_id.campus_managed):
            percentage = rec.marks * 100 / rec.exam_id.total_marks if rec.exam_id.total_marks else 0
            rec.grade = next((g.result for g in rec.exam_id.campus_grade_ids if g.min_per <= percentage < g.max_per + 1), False) if rec.campus_entered else False

    def _check_mvp_marks(self):
        exams = self.exam_id.filtered("campus_managed")
        exams._campus_can_enter()
        exams._mvp_lock()
        if any(e.campus_state not in {"draft", "entry"} for e in exams):
            raise ValidationError(_("Marks are locked. An examination officer must explicitly reopen them."))

    @api.model_create_multi
    def create(self, vals_list):
        exams = self.env["op.exam"].browse([v["exam_id"] for v in vals_list if v.get("exam_id")]).filtered("campus_managed")
        exams._campus_can_enter()
        exams._mvp_lock()
        if any(e.campus_state not in {"draft", "entry"} for e in exams):
            raise ValidationError(_("Cannot add marks to a submitted or published examination."))
        records = super().create([dict(v, campus_entered=v.get("campus_entered", "marks" in v)) for v in vals_list])
        for rec in records.filtered(lambda r: r.exam_id.campus_managed):
            if self.search_count([("exam_id", "=", rec.exam_id.id), ("student_id", "=", rec.student_id.id)]) > 1:
                raise ValidationError(_("A student can have only one marks entry per examination."))
            if not rec.campus_enrolment_id or rec.campus_enrolment_id.student_id != rec.student_id or rec.campus_enrolment_id.batch_id != rec.exam_id.batch_id:
                raise ValidationError(_("Marks must refer to the student's examination enrolment."))
        return records

    def write(self, vals):
        self._check_mvp_marks()
        if self.exam_id.filtered("campus_managed") and {"exam_id", "student_id", "campus_enrolment_id"}.intersection(vals):
            raise ValidationError(_("Marks roster identity is fixed."))
        if "marks" in vals:
            vals = dict(vals, campus_entered=True)
        return super().write(vals)

    def unlink(self):
        self._check_mvp_marks()
        return super().unlink()
