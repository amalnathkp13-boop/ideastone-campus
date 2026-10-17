import base64
import binascii
from pathlib import PurePath

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StudentPortalPolicy(models.Model):
    _inherit = "res.company"

    campus_student_portal_enabled = fields.Boolean(default=True, string="Enable Student Portal")
    campus_student_contact_edit = fields.Boolean(default=False, string="Allow student contact/address updates")


class StudentPortalPreferences(models.Model):
    _inherit = "op.student"

    campus_notice_badge = fields.Boolean(default=True, string="Show unread notice badge")
    campus_request_seen_at = fields.Datetime(readonly=True)
    campus_request_seen_event = fields.Integer(readonly=True, default=0)
    campus_portal_revision = fields.Integer(readonly=True, default=0)


class StudentRequestType(models.Model):
    _name = "campus.student.request.type"
    _description = "College student request catalogue"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection([("certificate", "Certificate"), ("grievance", "Support / correction"), ("training", "Training")], required=True, default="certificate")
    guidance = fields.Text(required=True)
    fee_guidance = fields.Char(string="Processing fee guidance (if applicable)")
    allow_cancel = fields.Boolean(default=True, string="Student may cancel before review")
    require_file = fields.Boolean(string="Supporting file required")
    max_upload_mb = fields.Integer(default=2, required=True)
    _sql_constraints = [("student_request_type_code", "unique(company_id,code)", "Request code must be unique per college.")]

    @api.constrains("max_upload_mb")
    def _check_upload_limit(self):
        if any(not 1 <= rec.max_upload_mb <= 10 for rec in self):
            raise ValidationError(_("Set an upload limit from 1 to 10 MB."))

    def copy(self, default=None):
        self.ensure_one()
        # Global catalogue entries are templates; an institution changes its own copy.
        return super().copy(dict(default or {}, company_id=self.env.company.id))


class StudentRequestEvent(models.Model):
    _name = "campus.student.request.event"
    _description = "Public student request status history"
    _order = "id desc"

    request_id = fields.Many2one("campus.service.request", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="request_id.company_id", store=True)
    name = fields.Char(required=True)
    response = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Status history is recorded by the request workflow."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Status history cannot be changed."))

    def unlink(self):
        raise AccessError(_("Status history must be retained."))


class StudentServiceRequest(models.Model):
    _inherit = "campus.service.request"

    state = fields.Selection(selection_add=[("information", "More information requested"), ("rejected", "Rejected"), ("ready", "Ready for collection")], ondelete={"information": "set default", "rejected": "set default", "ready": "set default"})
    portal_type_id = fields.Many2one("campus.student.request.type", ondelete="restrict")
    portal_reference = fields.Char(readonly=True, copy=False, index=True)
    portal_key = fields.Char(readonly=True, copy=False)
    portal_reply = fields.Text(string="Response shared with student")
    portal_student_reply = fields.Text(string="Student's additional information")
    portal_result_file = fields.Binary(attachment=True, string="Official document for student")
    portal_result_filename = fields.Char(string="Official document filename")
    portal_attendance_id = fields.Many2one("op.attendance.line", string="Attendance under review", ondelete="restrict")
    portal_event_ids = fields.One2many("campus.student.request.event", "request_id", readonly=True)
    _sql_constraints = [("portal_request_reference", "unique(portal_reference)", "Student request reference must be unique."), ("portal_request_key", "unique(requester_id,portal_key)", "This submission is already recorded.")]

    def _portal_operator(self):
        if not self.env.su and not any(self.env.user.has_group(g) for g in ["ideastone_erp.group_mvp_registrar", "ideastone_erp.group_services", "ideastone_erp.group_manager"]):
            raise AccessError(_("A college request operator is required."))

    @api.model
    def _portal_upload(self, content, filename, limit=2):
        if not content:
            return False, False
        filename = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        if not filename or len(filename) > 120 or any(ord(c) < 32 for c in filename):
            raise ValidationError(_("Use a short, safe filename."))
        if not isinstance(content, (str, bytes)) or len(content) > ((limit * 1024 * 1024 + 2) // 3) * 4:
            raise ValidationError(_("Upload a file within the configured size limit."))
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError(_("The upload is not a valid file.")) from exc
        if not raw or len(raw) > limit * 1024 * 1024:
            raise ValidationError(_("Upload a nonempty file within the configured size limit."))
        suffix = PurePath(filename).suffix.lower()
        valid = suffix == ".pdf" and raw.startswith(b"%PDF-") or suffix == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n") or suffix in {".jpg", ".jpeg"} and raw.startswith(b"\xff\xd8\xff")
        if suffix == ".txt":
            try:
                valid = "\x00" not in raw.decode("utf-8")
            except UnicodeError:
                valid = False
        if not valid:
            raise ValidationError(_("Only PDF, PNG, JPEG or UTF-8 text with matching content is permitted."))
        return base64.b64encode(raw), filename

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("portal_type_id"):
                self._portal_operator()
                if vals.get("portal_reference") or not vals.get("student_id"):
                    raise AccessError(_("Student requests require a student and a server-issued reference."))
                vals["portal_reference"] = self.env["ir.sequence"].next_by_code("campus.student.request")
                if not vals["portal_reference"]:
                    raise ValidationError(_("Configure student request numbering before accepting requests."))
                if vals.get("portal_result_file"):
                    raise ValidationError(_("The official response is added after request review."))
        records = super().create(vals_list)
        for rec in records.filtered("portal_type_id"):
            rec._portal_event("Draft")
        return records

    def _portal_event(self, name):
        for rec in self:
            self.env["campus.student.request.event"].sudo().create({"request_id": rec.id, "name": name, "response": rec.portal_reply or False})
            self.env["campus.mvp.audit"]._log(rec, "Student request: " + name)

    def write(self, vals):
        managed = self.filtered("portal_type_id")
        if not managed:
            return super().write(vals)
        self._portal_operator()
        managed._lock()
        if {"portal_key", "portal_reference", "portal_type_id", "requester_id", "student_id", "company_id", "portal_attendance_id"}.intersection(vals):
            raise AccessError(_("Student request identity and submission evidence are fixed."))
        if "state" in vals:
            if set(vals) != {"state"}:
                raise ValidationError(_("Save the response before changing request status."))
            transitions = {"draft": {"submitted", "cancelled"}, "submitted": {"information", "approved", "rejected", "cancelled"}, "information": {"submitted", "rejected", "cancelled"}, "approved": {"ready", "done", "rejected"}, "ready": {"done"}, "done": set(), "rejected": set(), "cancelled": set()}
            for rec in managed:
                if vals["state"] not in transitions[rec.state]:
                    raise ValidationError(_("This student request transition is not permitted."))
                if vals["state"] in {"information", "rejected"} and not (rec.portal_reply or "").strip():
                    raise ValidationError(_("Enter a response shared with the student before requesting information or rejecting."))
                if vals["state"] == "done" and not (rec.portal_reply or "").strip():
                    raise ValidationError(_("Enter a completion response for the student."))
                evidence = dict(vals)
                if vals["state"] == "approved":
                    evidence.update(approved_by=self.env.uid, approved_on=fields.Datetime.now())
                rec._set_system_values(evidence)
                rec._portal_event(dict(rec._fields["state"].selection).get(vals["state"], vals["state"]))
        else:
            if "portal_result_file" in vals:
                content, filename = self._portal_upload(vals["portal_result_file"], vals.get("portal_result_filename") or managed[:1].portal_result_filename, 10)
                vals = dict(vals, portal_result_file=content, portal_result_filename=filename)
            allowed = {"portal_reply", "portal_student_reply", "portal_result_file", "portal_result_filename", "message_ids", "message_follower_ids", "activity_ids"}
            if set(vals) - allowed:
                raise ValidationError(_("Retain submitted request details; add a response or official document instead."))
            managed._set_system_values(vals)
            if "portal_reply" in vals:
                managed._portal_event("College response")
        legacy = self - managed
        return super(StudentServiceRequest, legacy).write(vals) if legacy else True

    def action_portal_information(self):
        return self.write({"state": "information"})

    def action_portal_reject(self):
        return self.write({"state": "rejected"})

    def action_portal_ready(self):
        return self.write({"state": "ready"})

    def action_done(self):
        return self.write({"state": "done"}) if self.filtered("portal_type_id") else super().action_done()

    def unlink(self):
        if self.filtered("portal_type_id"):
            raise ValidationError(_("Student requests and their status history must be retained."))
        return super().unlink()


class StudentNoticeRead(models.Model):
    _name = "campus.student.notice.read"
    _description = "Student notice acknowledgement"

    student_id = fields.Many2one("op.student", required=True, ondelete="cascade")
    notice_id = fields.Many2one("campus.circular", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="student_id.company_id", store=True)
    _sql_constraints = [("student_notice_read", "unique(student_id,notice_id)", "Notice acknowledgement already exists.")]


class StudentExamSchedule(models.Model):
    _inherit = "op.exam"

    campus_schedule_published = fields.Boolean(readonly=True, copy=False, string="Schedule released to students")
    campus_schedule_published_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("campus_schedule_published") or v.get("campus_schedule_published_on") for v in vals_list):
            raise AccessError(_("Release schedules through the examination workflow."))
        return super().create(vals_list)

    def write(self, vals):
        if {"campus_schedule_published", "campus_schedule_published_on"}.intersection(vals):
            raise AccessError(_("Use Release schedule to make an examination visible to students."))
        return super().write(vals)

    def action_campus_release_schedule(self):
        self._mvp_require("ideastone_erp.group_mvp_exams", "openeducat_exam.group_op_exam_admin")
        self._mvp_lock()
        for rec in self:
            if rec.state == "cancel":
                raise ValidationError(_("A cancelled examination cannot be released."))
            super(StudentExamSchedule, rec).write({"campus_schedule_published": True, "campus_schedule_published_on": fields.Datetime.now()})
            rec._mvp_log("Examination schedule released to students")
        return True
