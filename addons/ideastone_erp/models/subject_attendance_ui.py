"""Subject-wise attendance workspace backed by assigned timetable sessions."""

from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import _, api, fields, models


class SubjectAttendanceUI(models.AbstractModel):
    _name = "campus.subject.attendance.ui"
    _description = "Subject-wise attendance workspace"

    def _require_staff(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("An internal campus account is required."))
        self.env["op.attendance.sheet"].check_access_rights("read")

    def _can_manage_all(self):
        return self.env.user.has_group("ideastone_erp.group_mvp_registrar") or self.env.user.has_group(
            "openeducat_attendance.group_op_attendance_manager")

    def _can_view_all(self):
        return self._can_manage_all() or self.env.user.has_group("ideastone_erp.group_mvp_hod") or self.env.user.has_group(
            "ideastone_erp.group_mvp_readonly")

    def _local_day(self, value):
        return fields.Datetime.context_timestamp(self, value).date()

    def _select_faculty(self, faculty_id):
        faculty = self.env["op.faculty"].search([("company_id", "in", [False, self.env.company.id])], order="name")
        linked = faculty.filtered(lambda item: item.user_id == self.env.user)[:1]
        chosen = faculty.filtered(lambda item: item.id == int(faculty_id or 0))[:1]
        if faculty_id and not chosen:
            raise AccessError(_("The selected staff member is outside this campus."))
        if not self._can_view_all():
            if not linked or chosen and chosen != linked:
                raise AccessError(_("You may view only your assigned classes."))
            return faculty, linked
        return faculty, chosen or linked or faculty[:1]

    @api.model
    def get_dashboard(self, term_id=None, faculty_id=None, attendance_date=None, subject_key=None, session_id=None):
        self._require_staff()
        day = fields.Date.to_date(attendance_date) if attendance_date else fields.Date.context_today(self)
        if not day:
            raise UserError(_("Choose a valid attendance date."))
        terms = self.env["op.academic.term"].search([("company_id", "=", self.env.company.id)],
                                                     order="term_start_date desc, id desc")
        term = terms.filtered(lambda item: item.id == int(term_id or 0))[:1]
        if term_id and not term:
            raise AccessError(_("That semester is outside this campus."))
        term = term or terms.filtered(lambda item: item.term_start_date <= day <= item.term_end_date)[:1] or terms[:1]
        faculty, chosen_faculty = self._select_faculty(faculty_id)
        sessions = self.env["op.session"]
        if term and chosen_faculty:
            sessions = sessions.search([
                ("company_id", "=", self.env.company.id), ("faculty_id", "=", chosen_faculty.id),
                ("batch_id.campus_term_id", "=", term.id), ("state", "!=", "cancel"),
            ], order="start_datetime, id")
        allocated = {}
        for session in sessions:
            if session.subject_id and session.batch_id:
                key = "%s:%s" % (session.subject_id.id, session.batch_id.id)
                allocated.setdefault(key, session)
        if subject_key and subject_key not in allocated:
            raise AccessError(_("That subject is outside your teaching allocation."))
        chosen_key = subject_key or next(iter(allocated), "")
        selected = allocated.get(chosen_key)
        selected_batch = selected.batch_id if selected else self.env["op.batch"]
        enrolments = self.env["op.student.course"]
        if allocated:
            enrolments = enrolments.search([
                ("batch_id", "in", list({item.batch_id.id for item in allocated.values()})),
                ("campus_date_from", "<=", day),
                "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", day),
            ], order="roll_number, id")
        subject_rows = []
        for key, item in allocated.items():
            roster = enrolments.filtered(lambda entry, batch=item.batch_id: entry.batch_id == batch and entry.student_id.active)
            subject_rows.append({
                "key": key, "code": item.subject_id.code or "", "name": item.subject_id.name,
                "kind": (item.subject_id.subject_type or "core").title(),
                "class": item.batch_id.name, "students": len(set(roster.student_id.ids)),
            })
        start = datetime.combine(day - timedelta(days=1), time.min)
        end = datetime.combine(day + timedelta(days=2), time.min)
        day_sessions = sessions.filtered(lambda item: selected and item.subject_id == selected.subject_id
                                         and item.batch_id == selected_batch
                                         and start <= fields.Datetime.to_datetime(item.start_datetime) < end
                                         and self._local_day(item.start_datetime) == day)
        chosen_session = day_sessions.filtered(lambda item: item.id == int(session_id or 0))[:1]
        if session_id and not chosen_session:
            raise AccessError(_("That hour is outside the selected subject and date."))
        chosen_session = chosen_session or day_sessions[:1]
        sheet = self.env["op.attendance.sheet"].search([
            ("session_id", "=", chosen_session.id), ("state", "!=", "cancel")], limit=1) if chosen_session else self.env["op.attendance.sheet"]
        line_by_student = {line.student_id.id: line for line in sheet.attendance_line}
        roster = enrolments.filtered(lambda entry: entry.batch_id == selected_batch and entry.student_id.active)
        students = []
        seen_students = set()
        for entry in roster:
            student = entry.student_id
            if student.id in seen_students:
                continue
            seen_students.add(student.id)
            students.append({
                "id": student.id, "roll": entry.roll_number or student.gr_no or "",
                "name": student.name, "class": selected_batch.name,
                "status": line_by_student[student.id].campus_status if student.id in line_by_student else "present",
            })
        hours = []
        for number, session in enumerate(day_sessions, 1):
            session_sheet = self.env["op.attendance.sheet"].search([
                ("session_id", "=", session.id), ("state", "!=", "cancel")], limit=1)
            hours.append({
                "id": session.id, "number": number,
                "time": "%s–%s" % (fields.Datetime.context_timestamp(self, session.start_datetime).strftime("%H:%M"),
                                     fields.Datetime.context_timestamp(self, session.end_datetime).strftime("%H:%M")),
                "total": len(students),
                "present": len(session_sheet.attendance_line.filtered("present")) if session_sheet else 0,
                "absent": len(session_sheet.attendance_line.filtered(lambda line: line.campus_status == "absent")) if session_sheet else 0,
                "state": session_sheet.state or "unrecorded",
            })
        can_save = bool(chosen_session and (self._can_manage_all() or chosen_session.faculty_id.user_id == self.env.user)
                        and self.env["op.attendance.sheet"].check_access_rights("create", raise_exception=False)
                        and self.env["op.attendance.line"].check_access_rights("write", raise_exception=False)
                        and sheet.state not in ("done", "cancel"))
        login = fields.Datetime.context_timestamp(self, self.env.user.login_date).strftime("%d %b %Y %I:%M %p") if self.env.user.login_date else ""
        return {
            "company": self.env.company.name, "date": str(day), "last_login": login,
            "terms": [{"id": item.id, "name": "%s : %s" % (item.academic_year_id.name or "", item.name)} for item in terms],
            "term_id": term.id or False,
            "faculty": [{"id": item.id, "name": item.name} for item in (faculty if self._can_view_all() else chosen_faculty)],
            "faculty_id": chosen_faculty.id or False,
            "subjects": subject_rows, "subject_key": chosen_key,
            "students": students, "hours": hours, "session_id": chosen_session.id or False,
            "allocated_class": {"name": selected_batch.name, "semester": term.name, "total": len(students)} if selected else None,
            "notes": sheet.campus_subject_lesson_notes or "", "sheet_state": sheet.state or "unrecorded",
            "can_save": can_save,
        }

    @api.model
    def save_attendance(self, session_id, student_statuses, notes=""):
        self._require_staff()
        session = self.env["op.session"].browse(int(session_id or 0)).exists()
        if not session or session.company_id != self.env.company or session.state == "cancel":
            raise AccessError(_("This teaching hour is unavailable in your campus."))
        if not (self._can_manage_all() or session.faculty_id.user_id == self.env.user):
            raise AccessError(_("You may record only your assigned teaching hours."))
        self.env["op.attendance.sheet"].check_access_rights("create")
        self.env["op.attendance.line"].check_access_rights("write")
        if len(notes or "") > 500:
            raise ValidationError(_("Lesson notes must be 500 characters or fewer."))
        register = self.env["op.attendance.register"].search([
            ("batch_id", "=", session.batch_id.id), ("course_id", "=", session.course_id.id)], limit=1)
        if not register:
            raise ValidationError(_("Create an attendance register for this class before saving attendance."))
        sheet = self.env["op.attendance.sheet"].search([
            ("session_id", "=", session.id), ("state", "!=", "cancel")], limit=1)
        if sheet and sheet.state not in ("draft", "start"):
            raise ValidationError(_("Submitted attendance is locked. Use the authorized correction flow."))
        if not sheet:
            sheet = self.env["op.attendance.sheet"].create({
                "register_id": register.id, "session_id": session.id, "faculty_id": session.faculty_id.id,
                "attendance_date": self._local_day(session.start_datetime), "campus_managed": True,
            })
        sheet._check_teaching_allocation()
        if sheet.state == "draft":
            sheet.action_campus_roster()
        elif not sheet.attendance_line:
            raise ValidationError(_("Load a roster before saving attendance."))
        statuses = {int(student_id): status for student_id, status in student_statuses.items()}
        if set(statuses) != set(sheet.attendance_line.student_id.ids):
            raise ValidationError(_("Attendance must include every student in this class roster."))
        if set(statuses.values()) - {"present", "absent", "late", "excused"}:
            raise ValidationError(_("Choose a valid attendance status for each student."))
        for line in sheet.attendance_line:
            status = statuses[line.student_id.id]
            if line.campus_status != status:
                line.write({"campus_status": status})
        sheet.write({"campus_subject_lesson_notes": notes or False})
        return {"message": _("Attendance draft saved. Submit the sheet to finalize it."), "sheet_id": sheet.id}


class SubjectAttendanceLessonNotes(models.Model):
    _inherit = "op.attendance.sheet"

    campus_subject_lesson_notes = fields.Text(string="Subject attendance lesson notes")
