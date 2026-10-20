import base64
import math

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


def _external(env):
    return not env.su and not env.user.has_group("base.group_user")


class LearningGrade(models.Model):
    _inherit = "grading.assignment"

    campus_assignment_ids = fields.One2many("op.assignment", "grading_assignment_id")

    @api.model_create_multi
    def create(self, vals_list):
        if _external(self.env):
            raise AccessError(_("Students and parents cannot create assignments."))
        return super().create(vals_list)

    def write(self, vals):
        if _external(self.env):
            raise AccessError(_("Assignment instructions are maintained by assigned faculty."))
        assignments = self.campus_assignment_ids
        assignments._campus_manage()
        if assignments.filtered(lambda r: r.campus_learning and r.state != "draft") and set(vals) & {"name", "course_id", "subject_id", "issued_date", "assignment_type", "faculty_id", "point"}:
            raise ValidationError(_("Published assignment identity and instructions cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if _external(self.env):
            raise AccessError(_("Assignment instructions are maintained by assigned faculty."))
        assignments = self.campus_assignment_ids
        assignments._campus_manage()
        if assignments.assignment_sub_line or assignments.filtered(lambda r: r.campus_learning and r.state != "draft"):
            raise ValidationError(_("Retain published assignment identity and submitted work."))
        return super().unlink()


class LearningAssignment(models.Model):
    _inherit = "op.assignment"

    company_id = fields.Many2one(related="batch_id.company_id", store=True, index=True)
    campus_learning = fields.Boolean(string="Reviewed campus coursework", default=False)
    campus_allow_late = fields.Boolean(string="Allow late submission", default=False)

    def _campus_manage(self):
        if _external(self.env):
            raise AccessError(_("Students and parents cannot change assignments."))
        if self.env.su:
            return
        for rec in self:
            if rec.batch_id.company_id not in self.env.companies:
                raise AccessError(_("This assignment belongs to another college."))
            if not (self.env.user.has_group("ideastone_erp.group_mvp_registrar") or self.env.user.has_group("openeducat_assignment.group_op_assignment_manager")):
                if rec.faculty_id.user_id != self.env.user:
                    raise AccessError(_("Only the assigned faculty member may manage this assignment."))
                if rec.campus_learning and not self.env["op.session"].sudo().search_count([("faculty_id", "=", rec.faculty_id.id), ("batch_id", "=", rec.batch_id.id), ("subject_id", "=", rec.subject_id.id), ("state", "!=", "cancel")]):
                    raise AccessError(_("Faculty need a teaching allocation for this section and subject."))

    @api.constrains("course_id", "batch_id", "subject_id", "allocation_ids", "marks", "campus_learning")
    def _campus_scope(self):
        for rec in self.filtered("campus_learning"):
            if rec.course_id != rec.batch_id.course_id or rec.subject_id not in rec.course_id.subject_ids:
                raise ValidationError(_("Choose a subject and section belonging to the assignment programme."))
            if not math.isfinite(rec.marks) or rec.marks < 0:
                raise ValidationError(_("Maximum marks must be a non-negative finite number; zero means ungraded work."))
            for student in rec.allocation_ids:
                if student.company_id != rec.batch_id.company_id or not student.active or not student.course_detail_ids.filtered(lambda p, rec=rec: p.state == "running" and p.batch_id == rec.batch_id and p.course_id == rec.course_id):
                    raise ValidationError(_("Allocate work only to active students enrolled in this section."))

    @api.model_create_multi
    def create(self, vals_list):
        if _external(self.env):
            raise AccessError(_("Students and parents cannot create assignments."))
        if not self.env.su and any(v.get("campus_learning") and v.get("state", "draft") != "draft" for v in vals_list):
            raise ValidationError(_("Create coursework as a draft, then publish it after allocating students."))
        records = super().create(vals_list)
        records._campus_manage()
        return records

    def write(self, vals):
        self._campus_manage()
        if self.filtered(lambda r: r.campus_learning and r.state != "draft") and set(vals) - {"state", "active", "message_follower_ids", "message_ids", "activity_ids"}:
            raise ValidationError(_("Published coursework is fixed. Return it to draft before changing instructions or allocation."))
        if vals.get("state") == "draft" and self.assignment_sub_line:
            raise ValidationError(_("Retain published work with submissions. Create a new assignment for revised instructions."))
        return super().write(vals)

    def unlink(self):
        self._campus_manage()
        if self.assignment_sub_line or self.filtered(lambda r: r.campus_learning and r.state != "draft"):
            raise ValidationError(_("Retain published coursework and submissions for the academic record."))
        return super().unlink()


class LearningSubmission(models.Model):
    _inherit = "op.assignment.sub.line"

    campus_file = fields.Binary(string="Student submission", attachment=False)
    campus_filename = fields.Char()
    campus_submission_slot = fields.Char(readonly=True, copy=False)
    campus_marks_entered = fields.Boolean(string="Grade confirmed", copy=False)
    campus_feedback_released = fields.Boolean(readonly=True, copy=False)
    campus_submitted_by = fields.Many2one("res.users", readonly=True, copy=False)
    campus_maximum = fields.Float(related="assignment_id.marks", string="Maximum marks")
    campus_revision_reason = fields.Text(string="Reason for reopening released work")
    _sql_constraints = [("campus_submission_slot_unique", "unique(campus_submission_slot)", "This student already has a coursework submission.")]

    @api.constrains("student_id", "assignment_id", "company_id", "marks")
    def _campus_submission_scope(self):
        for rec in self:
            if rec.student_id not in rec.assignment_id.allocation_ids or rec.student_id.company_id != rec.company_id or rec.assignment_id.batch_id.company_id != rec.company_id:
                raise ValidationError(_("The submission must belong to an allocated student in the assignment's college."))
            if not math.isfinite(rec.marks) or not 0 <= rec.marks <= rec.assignment_id.marks:
                raise ValidationError(_("Enter a mark between zero and the assignment maximum."))

    @api.model_create_multi
    def create(self, vals_list):
        if _external(self.env):
            raise AccessError(_("Submit your work through the authenticated student workspace."))
        if not self.env.su and any(set(v) & {"campus_submission_slot", "campus_feedback_released", "campus_submitted_by", "campus_marks_entered"} for v in vals_list):
            raise AccessError(_("Submission and release evidence is assigned by the workflow."))
        if not self.env.su and any(v.get("state", "draft") != "draft" for v in vals_list):
            raise AccessError(_("Students submit their own work before faculty review."))
        records = super().create([dict(v, campus_marks_entered=True) if "marks" in v and "campus_marks_entered" not in v else v for v in vals_list])
        records.assignment_id._campus_manage()
        return records

    def write(self, vals):
        if _external(self.env):
            raise AccessError(_("Submit or revise work through your student workspace."))
        self.assignment_id._campus_manage()
        if not self.env.su and set(vals) & {"student_id", "assignment_id", "company_id", "campus_file", "campus_filename", "description", "submission_date", "campus_submitted_by", "campus_submission_slot", "campus_feedback_released"}:
            raise AccessError(_("Faculty may review work but cannot change a student's submitted evidence."))
        vals = dict(vals)
        if vals.get("active") is False and self.filtered(lambda r: r.state != "draft"):
            raise ValidationError(_("Submitted work and released feedback must remain in the academic record."))
        if not self.env.su and "campus_marks_entered" in vals and self.filtered(lambda r: r.state != "submit"):
            raise ValidationError(_("Confirm an entered grade only while reviewing a submitted assignment."))
        if self.filtered(lambda r: r.state == "accept") and "note" in vals and vals.get("state") != "change":
            raise ValidationError(_("Released feedback is fixed. Return the work for revision with a reason."))
        if "marks" in vals:
            if self.filtered(lambda r: r.state == "accept"):
                raise ValidationError(_("Return the submission for revision before changing a released grade."))
            if "campus_marks_entered" not in vals:
                vals["campus_marks_entered"] = True
        target = vals.get("state")
        if target and not self.env.su:
            for rec in self:
                if target not in {"accept", "change", "reject"} or rec.state not in {"submit", "accept"}:
                    raise ValidationError(_("Review a submitted assignment or return released work for revision."))
                if rec.state == "accept" and target != "change":
                    raise ValidationError(_("Return released work for revision before reviewing it again."))
                if target in {"change", "reject"} and not (vals.get("note", rec.note) or "").strip():
                    raise ValidationError(_("Give the student a reason or revision instructions."))
                if target == "accept" and rec.assignment_id.marks and not (vals.get("campus_marks_entered") or rec.campus_marks_entered):
                    raise ValidationError(_("Enter the grade explicitly, including zero, before releasing feedback."))
        if target in {"accept", "change", "reject"}:
            vals["campus_feedback_released"] = True
        result = super().write(vals)
        if target in {"accept", "change", "reject"}:
            for rec in self:
                self.env["campus.mvp.audit"]._log(rec, "Coursework reviewed: " + target, rec.note, {"student_id": rec.student_id.id, "assignment_id": rec.assignment_id.id, "marks": rec.marks})
        return result

    def act_change_req(self):
        for rec in self:
            reason = rec.campus_revision_reason if rec.state == "accept" else rec.note
            if not (reason or "").strip():
                raise ValidationError(_("Enter revision instructions, or a reason for reopening released work."))
            rec.write({"state": "change", "note": reason, "campus_revision_reason": False})
        return True

    def unlink(self):
        if _external(self.env) or self.filtered(lambda r: r.state != "draft"):
            raise AccessError(_("Submitted coursework and released feedback must be retained."))
        self.assignment_id._campus_manage()
        return super().unlink()


class LearningPortal(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _learning_assignments(self, student, placement=None):
        placements = placement or student.course_detail_ids.filtered(lambda p: p.state == "running")
        subjects = placements.subject_ids or placements.course_id.subject_ids
        return self._records("op.assignment", [("batch_id.company_id", "=", student.company_id.id), ("batch_id", "in", placements.batch_id.ids),
            ("subject_id", "in", subjects.ids), ("allocation_ids", "in", student.ids), ("state", "in", ["publish", "finish"]),
            ("active", "=", True), ("issued_date", "<=", fields.Datetime.now())], limit=500, order="submission_date")

    def _learning_rows(self, student, placement):
        assignments = self._learning_assignments(student, placement) if placement else self.env["op.assignment"]
        submissions = self._records("op.assignment.sub.line", [("student_id", "=", student.id), ("assignment_id", "in", assignments.ids)], limit=1000, order="id desc")
        rows = []
        for task in assignments:
            work = submissions.filtered(lambda s, task=task: s.assignment_id == task)[:1]
            late = task.submission_date < fields.Datetime.now()
            can_submit = task.state == "publish" and work.state not in {"submit", "accept", "reject"} and (not late or task.campus_allow_late or work.state == "change")
            rows.append({"id": task.id, "name": task.name, "subject": task.subject_id.name, "teacher": task.faculty_id.name, "instructions": task.description,
                "due": self._dates(task.submission_date), "late": late, "allow_late": task.campus_allow_late, "state": work.state or "not_started",
                "status": dict(work._fields["state"].selection).get(work.state, "Not submitted"), "can_submit": can_submit,
                "description": work.description or "", "file": work.campus_filename if work.campus_file else "", "submission_id": work.id or False,
                "feedback": work.note if work.campus_feedback_released else "", "marks": work.marks if work.state == "accept" and work.campus_feedback_released and task.marks else None,
                "maximum": task.marks, "submitted": self._dates(work.submission_date) if work else ""})
        return rows

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student, placement, _placements, _first, _last = self._portal_context(enrolment, date_from, date_to)
        data["assignments"] = self._learning_rows(student, placement)
        data["placement"]["status"] = "Active" if placement and placement.state == "running" else "Finished" if placement else "Not recorded"
        resources = {resource.id: resource for resource in self._materials(student, placement)}
        for material in data["materials"]:
            resource = resources.get(material["id"])
            material["subject_id"] = resource.subject_id.id if resource else 0
            material["code"] = (resource.subject_id.code or "") if resource else ""
        return data

    @api.model
    def act(self, operation, payload=None):
        if operation != "assignment":
            return super().act(operation, payload)
        student = self._identity()
        if self._request_audience() != "student":
            raise AccessError(_("Only a student may submit their own coursework."))
        payload = payload or {}
        if not isinstance(payload, dict) or set(payload) - {"assignment_id", "description", "file", "filename"}:
            raise AccessError(_("Submit only your work, never identity, marks or review values."))
        self._serialize(student)
        task = self._learning_assignments(student).filtered(lambda t: t.id == int(payload.get("assignment_id") or 0))
        if not task or task.state != "publish":
            raise AccessError(_("This assignment is not available for submission."))
        model = self.env["op.assignment.sub.line"].sudo()
        work = model.search([("student_id", "=", student.id), ("assignment_id", "=", task.id)], order="id desc", limit=1)
        if work.state in {"submit", "accept"}:
            return {"saved": True, "submission_id": work.id}
        if work.state == "reject" or task.submission_date < fields.Datetime.now() and not task.campus_allow_late and work.state != "change":
            raise ValidationError(_("Submissions are closed. Ask the assigned faculty about revisions or an extension."))
        description = str(payload.get("description") or "").strip()
        if not description or len(description) > 10000:
            raise ValidationError(_("Describe your work in 1 to 10,000 characters."))
        content, filename = self.env["campus.service.request"]._portal_upload(payload.get("file"), payload.get("filename"), 5)
        vals = {"description": description, "state": "submit", "submission_date": fields.Datetime.now(), "campus_submitted_by": self.env.uid,
                "campus_feedback_released": False, "campus_marks_entered": False, "marks": 0, "note": False}
        if content:
            vals.update(campus_file=content, campus_filename=filename)
        if work:
            work.write(vals)
        else:
            work = model.create(dict(vals, assignment_id=task.id, student_id=student.id, company_id=student.company_id.id,
                                     campus_submission_slot=f"{task.id}:{student.id}"))
        self.env["campus.mvp.audit"]._log(work, "Student coursework submitted", details={"student_id": student.id, "assignment_id": task.id})
        return {"saved": True, "submission_id": work.id}

    def _download(self, kind, record_id):
        if kind != "assignment":
            return super()._download(kind, record_id)
        student = self._identity()
        work = self._records("op.assignment.sub.line", [("id", "=", record_id), ("student_id", "=", student.id), ("assignment_id", "in", self._learning_assignments(student, student.course_detail_ids).ids)])
        if not work or not work.campus_file:
            raise AccessError(_("This submission is not available to your account."))
        return base64.b64decode(work.campus_file), work.campus_filename or "coursework", "application/octet-stream"
