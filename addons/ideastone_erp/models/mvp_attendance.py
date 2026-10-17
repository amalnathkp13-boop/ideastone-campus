from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class AttendanceRegister(models.Model):
    _inherit = "op.attendance.register"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)


class Session(models.Model):
    _inherit = ["op.session", "campus.mvp.mixin"]
    _name = "op.session"

    campus_year_id = fields.Many2one(related="batch_id.campus_year_id", store=True, index=True)

    @api.constrains("start_datetime", "end_datetime", "faculty_id", "batch_id", "classroom_id", "state", "active")
    def _check_mvp_session(self):
        for rec in self.filtered("campus_year_id"):
            rec._mvp_company("faculty_id", "batch_id", "subject_id", "course_id")
            if rec.start_datetime >= rec.end_datetime:
                raise ValidationError(_("Session end must be after its start."))
            if rec.batch_id.course_id != rec.course_id or not rec.faculty_id.active:
                raise ValidationError(_("Choose an active faculty member and the section's programme."))
            if rec.state == "cancel" or not rec.active:
                continue
            # Lock allocation resources, not only sessions: concurrent inserts cannot both pass.
            for table, ids in [("op_faculty", rec.faculty_id.ids), ("op_batch", rec.batch_id.ids), ("op_classroom", rec.classroom_id.ids)]:
                if ids:
                    self.env.cr.execute(f'SELECT id FROM "{table}" WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(ids)])
            domain = [("id", "!=", rec.id), ("company_id", "=", rec.company_id.id), ("state", "!=", "cancel"),
                      ("start_datetime", "<", rec.end_datetime), ("end_datetime", ">", rec.start_datetime)]
            resources = ["|", ("faculty_id", "=", rec.faculty_id.id), ("batch_id", "=", rec.batch_id.id)]
            if rec.classroom_id:
                resources = ["|"] + resources + [("classroom_id", "=", rec.classroom_id.id)]
            if self.sudo().search_count(domain + resources):
                raise ValidationError(_("Timetable conflict: this class, faculty member or room is already allocated."))

    def action_campus_attendance(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        if self.state == "cancel":
            raise ValidationError(_("Attendance cannot be taken for a cancelled session."))
        existing = self.env["op.attendance.sheet"].search([("session_id", "=", self.id)], limit=1)
        register = self.env["op.attendance.register"].search([("batch_id", "=", self.batch_id.id), ("course_id", "=", self.course_id.id)], limit=1)
        if not register:
            raise ValidationError(_("Create an attendance register for this programme and section first."))
        return {"type": "ir.actions.act_window", "name": _("Take attendance"), "res_model": "op.attendance.sheet",
                "res_id": existing.id, "views": [(self.env.ref("ideastone_erp.mvp_attendance_form").id, "form")],
                "context": {"default_register_id": register.id, "default_session_id": self.id,
                            "default_faculty_id": self.faculty_id.id, "default_attendance_date": fields.Datetime.context_timestamp(self, self.start_datetime).date(),
                            "default_campus_managed": True}}


class AttendanceSheet(models.Model):
    _inherit = ["op.attendance.sheet", "campus.mvp.mixin"]
    _name = "op.attendance.sheet"

    company_id = fields.Many2one(related="register_id.company_id", store=True, index=True)
    campus_managed = fields.Boolean(default=False)
    campus_manual_subject_id = fields.Many2one("op.subject", string="Subject for manual session")
    campus_correction_reason = fields.Text(string="Correction reason")
    campus_submitted_by = fields.Many2one("res.users", readonly=True, copy=False)
    campus_submitted_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({"campus_submitted_by", "campus_submitted_on"}) or v.get("campus_managed") and v.get("state", "draft") != "draft" for v in vals_list):
            raise AccessError(_("New attendance starts in draft; use Submit attendance."))
        records = super().create(vals_list)
        for rec in records.filtered("campus_managed"):
            rec._validate_mvp_identity()
            if rec.session_id:
                rec.env.cr.execute("SELECT id FROM op_session WHERE id=%s FOR UPDATE", [rec.session_id.id])
            else:
                rec.env.cr.execute("SELECT id FROM op_attendance_register WHERE id=%s FOR UPDATE", [rec.register_id.id])
            identity = [("id", "!=", rec.id), ("register_id", "=", rec.register_id.id), ("state", "!=", "cancel")]
            if rec.session_id:
                identity = [("id", "!=", rec.id), ("state", "!=", "cancel"), ("session_id", "=", rec.session_id.id)]
            else:
                identity += [
                ("session_id", "=", False), ("attendance_date", "=", rec.attendance_date), ("campus_manual_subject_id", "=", rec.campus_manual_subject_id.id)]
            if self.sudo().search_count(identity):
                raise ValidationError(_("An attendance sheet already exists for this session."))
        return records

    def _validate_mvp_identity(self):
        for rec in self:
            rec._mvp_company("register_id", "session_id", "faculty_id", "campus_manual_subject_id")
            if not rec.faculty_id or not (rec.session_id or rec.campus_manual_subject_id):
                raise ValidationError(_("Select a timetable session, or a subject and faculty for a manual session."))
            if rec.session_id and (rec.session_id.state == "cancel" or rec.session_id.batch_id != rec.batch_id or rec.session_id.faculty_id != rec.faculty_id):
                raise ValidationError(_("Attendance must match an uncancelled assigned timetable session."))

    def write(self, vals):
        if any(rec.campus_managed for rec in self):
            if {"campus_submitted_by", "campus_submitted_on", "campus_managed", "state"}.intersection(vals):
                raise AccessError(_("Use attendance submit, cancel or correction actions."))
            if {"session_id", "register_id", "attendance_date", "faculty_id", "campus_manual_subject_id"}.intersection(vals) and self.attendance_line:
                raise ValidationError(_("A loaded roster keeps its original session, section and date."))
            if any(rec.state == "done" for rec in self) and set(vals) - {"campus_correction_reason", "message_follower_ids", "activity_ids"}:
                raise ValidationError(_("Reopen submitted attendance with an authorized correction reason."))
        return super().write(vals)

    def action_campus_roster(self):
        self._mvp_lock()
        for rec in self:
            if not rec.campus_managed or rec.state != "draft":
                raise ValidationError(_("Load the roster on a draft MVP attendance sheet."))
            rec._validate_mvp_identity()
            rec._check_teaching_allocation()
            enrolled = self.env["op.student.course"].search([
                ("batch_id", "=", rec.batch_id.id), ("course_id", "=", rec.course_id.id),
                ("campus_date_from", "<=", rec.attendance_date), "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", rec.attendance_date)])
            for student in enrolled.student_id - rec.attendance_line.student_id:
                self.env["op.attendance.line"].create({"attendance_id": rec.id, "student_id": student.id, "present": True})
        return True

    def attendance_done(self):
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(AttendanceSheet, legacy).attendance_done()
        for rec in self - legacy:
            rec._mvp_lock()
            if rec.state == "done":
                continue
            rec._validate_mvp_identity()
            rec._check_teaching_allocation()
            if rec.state not in {"draft", "start"} or not rec.attendance_line:
                raise ValidationError(_("Load and mark a roster before submitting attendance."))
            super(AttendanceSheet, rec).write({"state": "done", "campus_submitted_by": self.env.uid, "campus_submitted_on": fields.Datetime.now()})
            rec._mvp_log("Attendance submitted", details={"students": len(rec.attendance_line)})
        return True

    def attendance_draft(self):
        for rec in self.filtered("campus_managed"):
            rec._mvp_require("ideastone_erp.group_mvp_registrar", "openeducat_attendance.group_op_attendance_manager")
            rec._mvp_lock()
            if rec.state != "done" or not (rec.campus_correction_reason or "").strip():
                raise ValidationError(_("Enter a correction reason to reopen submitted attendance."))
            rec._mvp_log("Attendance reopened for correction", rec.campus_correction_reason)
            super(AttendanceSheet, rec).write({"state": "draft", "campus_correction_reason": False})
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(AttendanceSheet, legacy).attendance_draft()
        return True

    def attendance_cancel(self):
        for rec in self.filtered("campus_managed"):
            rec._mvp_require("ideastone_erp.group_mvp_registrar", "openeducat_attendance.group_op_attendance_manager")
            rec._mvp_lock()
            if not (rec.campus_correction_reason or "").strip():
                raise ValidationError(_("Enter a reason before cancelling attendance."))
            super(AttendanceSheet, rec).write({"state": "cancel"})
            rec._mvp_log("Attendance cancelled", rec.campus_correction_reason)
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(AttendanceSheet, legacy).attendance_cancel()
        return True


class AttendanceLine(models.Model):
    _inherit = "op.attendance.line"

    company_id = fields.Many2one(related="attendance_id.company_id", store=True, index=True)
    campus_status = fields.Selection([("present", "Present"), ("absent", "Absent"), ("late", "Late"), ("excused", "Excused")],
        compute="_compute_campus_status", inverse="_inverse_campus_status", store=True)

    @api.depends("present", "absent", "late", "excused")
    def _compute_campus_status(self):
        for rec in self:
            rec.campus_status = "excused" if rec.excused else "late" if rec.late else "present" if rec.present else "absent"

    def _inverse_campus_status(self):
        for rec in self:
            rec.write({status: status == rec.campus_status for status in ["present", "absent", "late", "excused"]})

    def _check_mvp_edit(self):
        for sheet in self.attendance_id.filtered("campus_managed"):
            sheet._mvp_lock()
            if sheet.state not in {"draft", "start"}:
                raise ValidationError(_("Submitted attendance is locked. Request an authorized correction."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            sheet = self.env["op.attendance.sheet"].browse(vals.get("attendance_id"))
            if sheet.campus_managed and sheet.state not in {"draft", "start"}:
                raise ValidationError(_("Submitted attendance is locked."))
            if sheet.campus_managed:
                sheet._mvp_lock()
                student_id = vals.get("student_id")
                if not self.env["op.student.course"].search_count([("student_id", "=", student_id), ("batch_id", "=", sheet.batch_id.id),
                    ("campus_date_from", "<=", sheet.attendance_date), "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", sheet.attendance_date)]):
                    raise ValidationError(_("The attendance student must be enrolled in this section on the session date."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_mvp_edit()
        if {"student_id", "attendance_id"}.intersection(vals) and self.attendance_id.filtered("campus_managed"):
            raise ValidationError(_("Attendance roster identity cannot be reassigned."))
        return super().write(vals)

    def unlink(self):
        self._check_mvp_edit()
        return super().unlink()
