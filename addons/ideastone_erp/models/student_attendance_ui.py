"""Student attendance workspace over the existing timetable and attendance sheets."""

from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import _, api, fields, models


class StudentAttendanceUI(models.AbstractModel):
    _name = "campus.student.attendance.ui"
    _description = "Student attendance workspace"

    def _require_internal(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("An internal campus account is required."))
        self.env["op.attendance.sheet"].check_access_rights("read")

    def _local_day(self, value):
        return fields.Datetime.context_timestamp(self, value).date()

    def _local_time(self, value):
        return fields.Datetime.context_timestamp(self, value).strftime("%I:%M %p")

    @api.model
    def get_dashboard(self, year_id=None, department_id=None, faculty_id=None, batch_id=None,
                      attendance_date=None, session_id=None, term_id=None):
        self._require_internal()
        day = fields.Date.to_date(attendance_date) if attendance_date else fields.Date.context_today(self)
        if not day:
            raise UserError(_("Choose a valid attendance date."))
        company = self.env.company
        years = self.env["op.academic.year"].search([("company_id", "=", company.id)], order="start_date desc")
        year = years.filtered(lambda item: item.id == int(year_id or 0))[:1]
        if year_id and not year:
            raise AccessError(_("That academic year is outside your campus."))
        year = year or years.filtered("campus_current")[:1] or years.filtered(
            lambda item: item.start_date <= day <= item.end_date)[:1] or years[:1]
        terms = self.env["op.academic.term"].search([("academic_year_id", "=", year.id)],
                                                      order="term_start_date, id") if year else self.env["op.academic.term"]
        term = terms.filtered(lambda item: item.id == int(term_id or 0))[:1]
        if term_id and not term:
            raise AccessError(_("That semester is outside the selected academic year."))
        term = term or terms.filtered(lambda item: item.term_start_date <= day <= item.term_end_date)[:1] or terms[:1]

        departments = self.env["op.department"].search([("company_id", "in", [False, company.id])], order="name")
        department = departments.filtered(lambda item: item.id == int(department_id or 0))[:1]
        if department_id and not department:
            raise AccessError(_("That department is outside your campus."))
        faculty = self.env["op.faculty"].search([("company_id", "in", [False, company.id])], order="name")
        if department:
            faculty = faculty.filtered(lambda item: item.main_department_id == department)
        linked = faculty.filtered(lambda item: item.user_id == self.env.user)[:1]
        chosen_faculty = faculty.filtered(lambda item: item.id == int(faculty_id or 0))[:1]
        if faculty_id and not chosen_faculty:
            raise AccessError(_("That staff member is outside your permitted campus and department."))
        can_manage_all = self.env.user.has_group("ideastone_erp.group_mvp_registrar") or self.env.user.has_group(
            "openeducat_attendance.group_op_attendance_manager")
        can_view_all = can_manage_all or self.env.user.has_group("ideastone_erp.group_mvp_hod") or self.env.user.has_group(
            "ideastone_erp.group_mvp_readonly")
        chosen_faculty = chosen_faculty or linked or (faculty[:1] if can_view_all else faculty.browse())
        if not can_view_all and not linked:
            raise AccessError(_("A linked faculty account is required to view class attendance."))
        if not can_view_all and chosen_faculty and chosen_faculty.user_id != self.env.user:
            raise AccessError(_("Faculty may view attendance only for their assigned classes."))

        batch_domain = [("company_id", "=", company.id), ("active", "=", True)]
        if year:
            batch_domain.append(("campus_year_id", "=", year.id))
        if term:
            batch_domain.append(("campus_term_id", "=", term.id))
        if department:
            batch_domain.append(("course_id.department_id", "=", department.id))
        batches = self.env["op.batch"].search(batch_domain, order="name, id")
        if chosen_faculty:
            assigned = self.env["op.session"].search([
                ("company_id", "=", company.id), ("faculty_id", "=", chosen_faculty.id),
                ("state", "!=", "cancel"), ("batch_id", "in", batches.ids),
            ]).batch_id
            batches &= assigned
        selected_batch = batches.filtered(lambda item: item.id == int(batch_id or 0))[:1]
        if batch_id and not selected_batch:
            raise AccessError(_("That class is outside your assigned attendance scope."))
        selected_batch = selected_batch or batches[:1]

        enrolments = self.env["op.student.course"].search([
            ("batch_id", "in", batches.ids), ("state", "=", "running"),
            ("campus_date_from", "<=", day), "|", ("campus_date_to", "=", False),
            ("campus_date_to", ">=", day),
        ], order="roll_number, id") if batches else self.env["op.student.course"]
        roster = enrolments.filtered(lambda item: item.batch_id == selected_batch and item.student_id.active)
        class_rows = []
        for batch in batches:
            current = enrolments.filtered(lambda item, batch=batch: item.batch_id == batch and item.student_id.active)
            class_rows.append({"id": batch.id, "name": batch.name, "from": str(batch.start_date),
                               "to": str(batch.end_date), "semester": batch.campus_term_id.campus_sequence or 0,
                               "total": len(current), "year": batch.campus_year_id.name or ""})

        # Search an expanded UTC range, then apply the user's local date to avoid
        # dropping early or late timetable hours around a time-zone boundary.
        start = datetime.combine(day - timedelta(days=1), time.min)
        end = datetime.combine(day + timedelta(days=2), time.min)
        session_domain = [("company_id", "=", company.id), ("state", "!=", "cancel"),
                          ("batch_id", "=", selected_batch.id),
                          ("start_datetime", ">=", fields.Datetime.to_string(start)),
                          ("start_datetime", "<", fields.Datetime.to_string(end))]
        if chosen_faculty:
            session_domain.append(("faculty_id", "=", chosen_faculty.id))
        sessions = self.env["op.session"].search(session_domain, order="start_datetime, id").filtered(
            lambda item: self._local_day(item.start_datetime) == day) if selected_batch else self.env["op.session"]
        sheets = self.env["op.attendance.sheet"].search([
            ("session_id", "in", sessions.ids), ("state", "!=", "cancel")]) if sessions else self.env["op.attendance.sheet"]
        selected_session = sessions.filtered(lambda item: item.id == int(session_id or 0))[:1]
        if session_id and not selected_session:
            raise AccessError(_("That teaching hour is outside the selected class and date."))
        selected_session = selected_session or sessions[:1]
        selected_sheet = sheets.filtered(lambda item: item.session_id == selected_session)[:1]
        lines_by_student = {line.student_id.id: line for line in selected_sheet.attendance_line}
        student_rows = [{"id": item.student_id.id, "roll": item.roll_number or item.student_id.gr_no or "",
                         "reg": item.student_id.gr_no or "",
                         "name": item.student_id.name, "absent": bool(lines_by_student.get(item.student_id.id)
                         and lines_by_student[item.student_id.id].campus_status == "absent")}
                        for item in roster]
        hour_rows = []
        for index, session in enumerate(sessions, 1):
            sheet = sheets.filtered(lambda item, session=session: item.session_id == session)[:1]
            hour_rows.append({"id": session.id, "number": index, "subject": session.subject_id.name or "",
                              "time": "%s – %s" % (self._local_time(session.start_datetime), self._local_time(session.end_datetime)),
                              "absent": len(sheet.attendance_line.filtered(lambda item: item.campus_status == "absent")),
                              "state": sheet.state or "unrecorded"})

        month_start = day.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_lines = self.env["op.attendance.line"].search([
            ("batch_id", "in", batches.ids), ("attendance_date", ">=", month_start),
            ("attendance_date", "<", next_month), ("attendance_id.state", "=", "done")]) if batches else self.env["op.attendance.line"]
        completed = month_lines.filtered(lambda item: not chosen_faculty or item.attendance_id.faculty_id == chosen_faculty)
        today_lines = completed.filtered(lambda item: item.attendance_date == day)
        today_sheets = self.env["op.attendance.sheet"].search([
            ("batch_id", "in", batches.ids), ("attendance_date", "=", day), ("state", "=", "done")]) if batches else self.env["op.attendance.sheet"]
        if chosen_faculty:
            today_sheets = today_sheets.filtered(lambda item: item.faculty_id == chosen_faculty)
        attended = len(completed.filtered(lambda item: item.campus_status in ("present", "late")))
        rate = round(attended * 100 / len(completed)) if completed else None
        weekly = defaultdict(lambda: [0, 0])
        performance = defaultdict(lambda: [0, 0, 0])
        for line in completed:
            week = min(5, (line.attendance_date.day - 1) // 7 + 1)
            weekly[week][1] += 1
            weekly[week][0] += int(line.campus_status in ("present", "late"))
            score = performance[line.batch_id.id]
            score[1] += 1
            score[0] += int(line.campus_status in ("present", "late"))
            score[2] += int(line.campus_status == "absent")
        trend = [{"label": "Week %s" % week, "rate": round(weekly[week][0] * 100 / weekly[week][1])
                  if weekly[week][1] else 0} for week in range(1, 1 + min(5, (next_month - month_start).days // 7 + 1))]
        ranked = [(batch, performance[batch.id]) for batch in batches if performance[batch.id][1]]
        highest = max(ranked, key=lambda item: item[1][2], default=None)
        best = max(ranked, key=lambda item: item[1][0] / item[1][1], default=None)
        insights = [
            {"title": "Highest Absence Class", "text": "%s · %s absences this month" % (highest[0].name, highest[1][2])
             if highest else "No completed attendance yet", "tone": "red", "icon": "fa-line-chart"},
            {"title": "Best Performing Class", "text": "%s · %s%% attendance" % (best[0].name, round(best[1][0] * 100 / best[1][1]))
             if best else "No completed attendance yet", "tone": "green", "icon": "fa-signal"},
            {"title": "Recommendation", "text": "Review the highest absence class and follow up with its students."
             if highest and highest[1][2] else "Keep recording each teaching hour to build useful insights.",
             "tone": "blue", "icon": "fa-lightbulb-o"},
        ]
        login = fields.Datetime.context_timestamp(self, self.env.user.login_date).strftime("%d %b %Y %I:%M %p") if self.env.user.login_date else ""
        return {"company": company.name, "last_login": login, "date": str(day),
                "month_name": day.strftime("%B"), "year": day.year,
                "years": [{"id": item.id, "name": item.name} for item in years], "year_id": year.id or False,
                "terms": [{"id": item.id, "name": item.name} for item in terms], "term_id": term.id or False,
                "departments": [{"id": item.id, "name": item.name} for item in departments],
                "department_id": department.id or False,
                "faculty": [{"id": item.id, "name": item.name} for item in faculty],
                "faculty_id": chosen_faculty.id or False, "classes": class_rows,
                "batch_id": selected_batch.id or False, "students": student_rows,
                "session_id": selected_session.id or False, "hours": hour_rows,
                "notes": selected_sheet.campus_lesson_notes or "", "sheet_state": selected_sheet.state or "unrecorded",
                "can_save": bool(selected_session and self.env["op.attendance.sheet"].check_access_rights("create", raise_exception=False)
                                 and self.env["op.attendance.line"].check_access_rights("write", raise_exception=False)
                                 and (can_manage_all or selected_session.faculty_id.user_id == self.env.user)
                                 and selected_sheet.state not in ("done", "cancel")),
                "metrics": {"classes": len(batches), "students": len(set(enrolments.student_id.ids)),
                            "absentees": len(set(today_lines.filtered(lambda item: item.campus_status == "absent").student_id.ids)),
                            "rate": rate, "sessions": len(today_sheets)},
                "trend": trend, "insights": insights}

    @api.model
    def save_hour(self, session_id, absent_student_ids, notes=""):
        self._require_internal()
        session = self.env["op.session"].browse(int(session_id or 0)).exists()
        if not session or session.company_id != self.env.company or session.state == "cancel":
            raise AccessError(_("This teaching hour is not available in your campus."))
        if not (self.env.user.has_group("ideastone_erp.group_mvp_registrar") or
                self.env.user.has_group("openeducat_attendance.group_op_attendance_manager") or
                session.faculty_id.user_id == self.env.user):
            raise AccessError(_("You may record only your assigned teaching hours."))
        self.env["op.attendance.sheet"].check_access_rights("create")
        self.env["op.attendance.line"].check_access_rights("write")
        if len(notes or "") > 2000:
            raise ValidationError(_("Lesson notes must be under 2,000 characters."))
        day = self._local_day(session.start_datetime)
        register = self.env["op.attendance.register"].search([
            ("batch_id", "=", session.batch_id.id), ("course_id", "=", session.course_id.id)], limit=1)
        if not register:
            raise ValidationError(_("Create an attendance register for this class before recording attendance."))
        sheet = self.env["op.attendance.sheet"].search([("session_id", "=", session.id)], limit=1)
        if sheet and sheet.state not in ("draft", "start"):
            raise ValidationError(_("Submitted attendance is locked. Reopen it through the authorized correction flow."))
        if not sheet:
            sheet = self.env["op.attendance.sheet"].create({"register_id": register.id, "session_id": session.id,
                "faculty_id": session.faculty_id.id, "attendance_date": day, "campus_managed": True})
        sheet._check_teaching_allocation()
        if sheet.state == "draft":
            sheet.action_campus_roster()
        elif not sheet.attendance_line:
            raise ValidationError(_("Load a roster before saving attendance."))
        absent = set(int(value) for value in absent_student_ids)
        available = set(sheet.attendance_line.student_id.ids)
        if absent - available:
            raise ValidationError(_("Only students in this class roster may be marked absent."))
        for line in sheet.attendance_line:
            status = "absent" if line.student_id.id in absent else "present"
            if line.campus_status != status:
                line.write({"campus_status": status})
        sheet.write({"campus_lesson_notes": notes or False})
        return {"sheet_id": sheet.id, "message": _("Attendance draft saved. Submit the sheet to finalize it.")}


class StudentAttendanceLessonNotes(models.Model):
    _inherit = "op.attendance.sheet"

    campus_lesson_notes = fields.Text(string="Notes of lesson")
