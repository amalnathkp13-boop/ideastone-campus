"""Mentorship monitoring and the faculty's own attendance workflow."""

from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class TaskListNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _faculty_modules(self, visible, faculty, pages):
        is_hod = self.env.user.has_group("ideastone_erp.group_od_hod_approver")
        if not is_hod:
            visible[:] = [item for item in visible if item.get("action") != "ideastone_erp.action_subject_attendance_workspace"]
        modules = super()._faculty_modules(visible, faculty, pages)
        if not is_hod:
            modules = [module for module in modules if module["key"] != "attendance"]
        teaching = next((module for module in modules if module["key"] == "teaching"), None)
        if teaching:
            entries = [("My Teaching Subjects", "action_my_teaching_subjects")]
            if not is_hod:
                entries.insert(0, ("My Mentorship Class", "action_my_mentorship_class"))
            teaching["items"] = [{"label": title, "action": "ideastone_erp." + name,
                "action_id": self.env.ref("ideastone_erp." + name).id, "allowed": True}
                for title, name in entries] + [item for item in teaching["items"] if item.get("tool") != "subject_attendance"]
        return modules


class FacultyTaskList(models.AbstractModel):
    _name = "campus.faculty.task.list"
    _description = "Faculty task list: mentorship and own teaching subjects"

    def _faculty(self):
        return self.env["campus.question.paper"]._faculty()

    def _mentor_context(self, class_key=None):
        if class_key and not isinstance(class_key, str):
            raise ValidationError(_("Choose a valid mentorship class."))
        faculty = self._faculty()
        if self.env.user.has_group("ideastone_erp.group_od_hod_approver"):
            raise AccessError(_("HOD accounts use My Teaching Subjects; mentorship monitoring is a staff workspace."))
        mentor = self.env["campus.staff.od.ui"]
        routes = mentor._assigned_routes()
        classes = mentor._classes(routes)
        if class_key and class_key not in classes:
            raise AccessError(_("This class is outside your mentorship assignment."))
        selected = classes.get(class_key) if class_key else next(iter(classes.values()), None)
        return faculty, classes, selected

    def _lines(self, domain, sudo=False):
        model = self.env["op.attendance.line"]
        if sudo:
            model = model.sudo()
        domain = [("company_id", "=", self.env.company.id), ("attendance_id.state", "=", "done")] + domain
        if model.search_count(domain) > 50000:
            raise ValidationError(_("Choose a narrower class or semester to review attendance."))
        return model.search(domain, order="attendance_date desc, id desc", limit=50000)

    def _summary(self, lines):
        rows = self.env["campus.dashboard"]._attendance_rows(lines)
        held = sum(row["sessions"] for row in rows)
        present = sum(row["present"] for row in rows)
        rate = round(present * 100 / held, 1) if held else None
        return {"present": present, "held": held, "rate": rate,
            "shortage": bool(held and present * 100 < self.env.company.campus_attendance_threshold * held),
            "subjects": rows}

    def _history(self, lines):
        result = []
        for sheet in lines.attendance_id.sorted(lambda r: (r.attendance_date, r.id), reverse=True)[:15]:
            scoped = lines.filtered(lambda line, sheet=sheet: line.attendance_id == sheet)
            session = sheet.session_id
            result.append({"id": sheet.id, "date": str(sheet.attendance_date),
                "subject": sheet.campus_subject_id.name or sheet.campus_manual_subject_id.name,
                "class": sheet.batch_id.name, "hour": fields.Datetime.context_timestamp(self, session.start_datetime).strftime("%H:%M") if session else "—",
                "present": len(scoped.filtered(lambda r: r.present or r.late)),
                "absent": len(scoped.filtered("absent")), "status": "Submitted"})
        return result

    @api.model
    def get_mentor_data(self, class_key=None):
        faculty, classes, selected = self._mentor_context(class_key)
        result = {"user": self.env.user.name, "company": self.env.company.name, "is_hod": False,
            "classes": [{"key": item["key"], "label": item["label"], "semester": item["semester"]} for item in classes.values()],
            "class_key": selected["key"] if selected else "", "class_label": selected["label"] if selected else _("No mentorship class assigned"),
            "semester": selected["semester"] if selected else "", "threshold": self.env.company.campus_attendance_threshold,
            "students": [], "subjects": [], "history": [], "followups": []}
        if not selected:
            return result
        batch_id, term_id = (int(value) for value in selected["key"].split(":"))
        term = self.env["op.academic.term"].sudo().browse(term_id)
        # Cross-subject monitoring is limited to the students in the mentor's active routes.
        lines = self._lines([("student_id", "in", list(selected["student_ids"])), ("batch_id", "=", batch_id),
            ("attendance_date", ">=", term.term_start_date), ("attendance_date", "<=", term.term_end_date)], sudo=True) if term else self.env["op.attendance.line"]
        students = self.env["op.student"].sudo().browse(list(selected["student_ids"])).filtered("active")
        followups = self.env["campus.counseling"].search([("mentor_id", "=", faculty.id),
            ("student_id", "in", students.ids), ("company_id", "=", self.env.company.id)], order="date desc, id desc", limit=100)
        result["students"] = [{"id": student.id, "name": student.name, "roll": student.gr_no or "—",
            "followup": student in followups.filtered(lambda r: r.follow_up_date and r.follow_up_date >= fields.Date.context_today(self)).student_id,
            **self._summary(lines.filtered(lambda row, student=student: row.student_id == student))}
            for student in students.sorted("name")]
        result["subjects"] = [{"id": subject.id, "name": subject.name,
            **self._summary(lines.filtered(lambda r, subject=subject: r.attendance_id.campus_subject_id == subject))}
            for subject in lines.attendance_id.campus_subject_id.sorted("name")]
        result["history"] = self._history(lines)
        result["followups"] = [{"id": row.id, "student_id": row.student_id.id, "student": row.student_id.name,
            "note": row.discussion, "date": str(row.date), "due": str(row.follow_up_date) if row.follow_up_date else ""} for row in followups]
        return result

    @api.model
    def save_followup(self, student_id, note, class_key=None):
        faculty, _classes, selected = self._mentor_context(class_key)
        if type(student_id) is not int or not selected or student_id not in selected["student_ids"]:
            raise AccessError(_("Choose a student from your assigned mentorship class."))
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
            raise ValidationError(_("Enter a follow-up note of 1–2,000 characters."))
        self.env["campus.counseling"].create({"name": _("Attendance follow-up"), "student_id": student_id,
            "mentor_id": faculty.id, "company_id": self.env.company.id, "discussion": note.strip(),
            "follow_up_date": fields.Date.context_today(self) + timedelta(days=7)})
        return True

    @api.model
    def get_teaching_data(self, term_id=None, attendance_date=None, subject_key=None, session_id=None):
        faculty = self._faculty()
        data = self.env["campus.subject.attendance.ui"].get_dashboard(term_id, faculty.id, attendance_date, subject_key, session_id)
        sessions = self.env["op.session"].search([("company_id", "=", self.env.company.id),
            ("faculty_id", "=", faculty.id), ("batch_id.campus_term_id", "=", data["term_id"]), ("state", "!=", "cancel")])
        lines = self._lines([("attendance_id.session_id", "in", sessions.ids)])
        data.update(user=self.env.user.name, is_hod=self.env.user.has_group("ideastone_erp.group_od_hod_approver"),
            history=self._history(lines), threshold=self.env.company.campus_attendance_threshold)
        for row in data["students"]:
            row["performance"] = self._summary(lines.filtered(lambda line, row=row: line.student_id.id == row["id"]))
        return data

    @api.model
    def save_teaching_attendance(self, session_id, statuses, notes="", submit=False):
        faculty = self._faculty()
        if type(session_id) is not int or type(submit) is not bool or not isinstance(statuses, dict) or not isinstance(notes, str) or len(notes) > 500:
            raise ValidationError(_("Choose an assigned session and valid attendance entries."))
        if submit and not notes.strip():
            raise ValidationError(_("Enter the lesson notes before submitting attendance."))
        session = self.env["op.session"].browse(session_id).exists()
        if not session or session.company_id != self.env.company or session.faculty_id != faculty:
            raise AccessError(_("You may mark only your own assigned teaching sessions."))
        self.env.cr.execute("SELECT id FROM op_session WHERE id=%s FOR UPDATE", [session.id])
        sheet = self.env["op.attendance.sheet"].search([("session_id", "=", session.id), ("state", "!=", "cancel")], limit=1)
        sheet.invalidate_recordset()
        if sheet.state == "done":
            raise ValidationError(_("This attendance was already submitted. Use the authorized correction workflow."))
        protected = sheet.attendance_line.filtered("excused")
        if any(statuses.get(str(line.student_id.id), statuses.get(line.student_id.id)) != "excused" for line in protected):
            raise ValidationError(_("Keep approved OD / leave entries unchanged."))
        result = self.env["campus.subject.attendance.ui"].save_attendance(session.id, statuses, notes)
        if submit:
            self.env["op.attendance.sheet"].browse(result["sheet_id"]).attendance_done()
            result["message"] = _("Attendance submitted successfully.")
        return result
