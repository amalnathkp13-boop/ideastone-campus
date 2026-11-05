from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, ValidationError
from pytz import UTC, timezone

from odoo import _, api, fields, models


def rate(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


class HodDashboard(models.AbstractModel):
    _name = "campus.hod.dashboard"
    _description = "Department overview for the head of department"

    def _is_hod(self):
        user = self.env.user
        return user.active and user.has_group("ideastone_erp.group_mvp_hod")

    def _department(self):
        department = self.env.user.dept_id.sudo()
        if not self._is_hod() or not department or department.company_id != self.env.company:
            raise AccessError(_("An assigned HOD department in the active college is required."))
        return department

    def _search(self, model, domain, **options):
        # Every caller supplies a department, assigned reviewer, or previously scoped record IDs.
        return self.env[model].sudo().search([("company_id", "=", self.env.company.id)] + domain, **options)

    def _filters(self, filters, batches):
        if not isinstance(filters, dict) or filters.keys() - {"year", "semester", "section", "from", "to"}:
            raise ValidationError(_("Choose valid dashboard filters."))
        year, semester, section = (filters.get(key, "") for key in ("year", "semester", "section"))
        if year not in ("", "1", "2", "3", "4") or semester not in ("", "odd", "even"):
            raise ValidationError(_("Choose a valid year of study and semester."))
        if section not in ["", *map(str, batches.ids)]:
            raise ValidationError(_("Choose a section in your department."))
        try:
            dates = [fields.Date.to_date(filters.get(key) or False) for key in ("from", "to")]
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Enter valid dates.")) from exc
        if any(day and not 1900 <= day.year <= 9998 for day in dates):
            raise ValidationError(_("Enter dates from 1900 through 9998."))
        if all(dates) and dates[0] > dates[1]:
            raise ValidationError(_("The from date must be on or before the to date."))
        return year, semester, section, *dates

    def _date_domain(self, name, start, end):
        return ([(name, ">=", start)] if start else []) + ([(name, "<=", end)] if end else [])

    def _datetime_domain(self, name, start, end):
        zone = timezone(self.env.context.get("tz") or self.env.user.tz or "UTC")

        def boundary(day):
            return zone.localize(datetime.combine(day, time.min)).astimezone(UTC).replace(tzinfo=None)

        return ([(name, ">=", boundary(start))] if start else []) + (
            [(name, "<", boundary(end + timedelta(days=1)))] if end else [])

    @api.model
    def get_overview(self, filters=None):
        department = self._department()
        today = fields.Date.context_today(self)
        academic_year = self._search("op.academic.year", [("campus_current", "=", True)], limit=1)
        if not academic_year:
            academic_year = self._search("op.academic.year", [("start_date", "<=", today), ("end_date", ">=", today)], limit=1)
        batches = self._search("op.batch", [("course_id.department_id", "=", department.id)]
            + ([("campus_year_id", "=", academic_year.id)] if academic_year else []), order="name, id")
        options = [{"id": str(batch.id), "name": batch.name} for batch in batches]
        year, semester, section, start, end = self._filters(filters if filters is not None else {}, batches)
        batches = batches.filtered(lambda batch: not section or str(batch.id) == section)
        enrolments = self._search("op.student.course", [
            ("course_id.department_id", "=", department.id), ("batch_id", "in", batches.ids),
            ("state", "=", "running"), ("student_id.active", "=", True),
            ("campus_date_from", "<=", end or today),
            "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", start or today),
        ])
        def term_number(record):
            return (record.academic_term_id or record.batch_id.campus_term_id).campus_sequence

        enrolments = enrolments.filtered(lambda row:
            (not year or str((term_number(row) + 1) // 2) == year)
            and (not semester or term_number(row) and term_number(row) % 2 == (semester == "odd")))
        if year or semester:
            batches = batches.filtered(lambda batch: batch in enrolments.batch_id or (
                batch.campus_term_id
                and (not year or str((batch.campus_term_id.campus_sequence + 1) // 2) == year)
                and (not semester or batch.campus_term_id.campus_sequence % 2 == (semester == "odd"))))
        students = enrolments.student_id
        start = start or academic_year.start_date
        end = end or academic_year.end_date
        lines = self._search("op.attendance.line", [
            ("batch_id", "in", batches.ids), ("student_id", "in", students.ids),
            ("attendance_id.state", "=", "done"),
        ] + self._date_domain("attendance_date", start, end))
        policy = self.env.company.campus_excused_policy
        threshold = self.env.company.campus_attendance_threshold
        totals, present = Counter(), Counter()
        today_total, today_present = Counter(), Counter()
        for line in lines:
            if line.excused and policy == "exclude":
                continue
            attended = bool(line.present or line.late or (line.excused and policy == "present"))
            totals[line.student_id.id] += 1
            present[line.student_id.id] += attended
            if line.attendance_date == today:
                today_total[line.batch_id.id] += 1
                today_present[line.batch_id.id] += attended
        risks = {sid for sid, count in totals.items() if present[sid] * 100 < threshold * count}
        attendance = rate(sum(present.values()), sum(totals.values()))

        by_year = defaultdict(set)
        student_sections = defaultdict(set)
        for row in enrolments:
            by_year[(term_number(row) + 1) // 2].add(row.student_id.id)
            student_sections[row.student_id.id].add(row.batch_id.name)
        year_rows = [{"year": _("Year %s", key) if key else _("Year not recorded"), "students": len(ids),
            "attendance": rate(sum(present[sid] for sid in ids), sum(totals[sid] for sid in ids)),
            "risk": len(risks & ids)} for key, ids in sorted(by_year.items(), key=lambda item: (not item[0], item[0]))]

        faculty = self._search("op.faculty", [("main_department_id", "=", department.id)], order="name, id")
        employees = self._search("hr.employee", [("user_id", "in", faculty.user_id.ids)])
        leave = self._search("hr.leave", [("employee_id", "in", employees.ids), ("state", "=", "validate"),
            ("request_date_from", "<=", today), ("request_date_to", ">=", today)])
        punches = self.env["hr.attendance"].sudo().search(
            [("employee_id", "in", employees.ids)] + self._datetime_domain("check_in", today, today))
        sessions = self._search("op.session", [("batch_id", "in", batches.ids), ("state", "!=", "cancel")]
            + self._datetime_domain("start_datetime", start, end), order="start_datetime, id")
        allocated = sessions.filtered(lambda session: session.faculty_id and session.state in ("confirm", "done"))
        loads = Counter(session.faculty_id.id for session in allocated)
        exams = self._search("op.exam", [("batch_id", "in", batches.ids)]
            + self._datetime_domain("start_time", start, end))
        results = exams.filtered(lambda exam: exam.campus_state == "published").campus_result_ids.filtered("campus_entered")
        pass_rate = rate(sum(result.marks >= result.exam_id.min_marks for result in results), len(results))
        assignment = self._search("op.assignment", [("batch_id", "in", batches.ids), ("campus_learning", "=", True),
            ("state", "in", ["publish", "finish"])] + self._datetime_domain("submission_date", start, end))
        expected = sum(len(task.allocation_ids & students) for task in assignment)
        completed = sum(
            len(task.assignment_sub_line.filtered("campus_submitted_by").student_id & task.allocation_ids & students)
            for task in assignment
        )

        approvals, paper_dates = self._approvals(department, students, batches, exams, year, semester, start, end)
        schedule = self._schedule(sessions, paper_dates, today, start, end)
        mentors = self._search("campus.student.leave.routing", [("student_id", "in", students.ids),
            ("hod_id", "=", self.env.uid), ("active", "=", True)])
        next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        appraisal = self._search("campus.faculty.task", [("user_id", "in", faculty.user_id.ids), ("state", "in", ["planned", "progress"]),
            ("name", "ilike", "appraisal"), ("deadline", ">=", today), ("deadline", "<", next_month)])
        leave_users = leave.employee_id.user_id
        present_users = punches.employee_id.user_id
        readiness = rate(len(exams.filtered(lambda exam: exam.campus_state in ("submitted", "locked", "published"))), len(exams))
        return {
            "department": department.name, "company": self.env.company.name, "today": str(today), "year": academic_year.name or _("All academic years"),
            "sample": self.env.company.campus_demo, "sections": options, "years": year_rows, "threshold": threshold,
            "students": len(students), "faculty": len(faculty), "on_leave": len(faculty.filtered(lambda member: member.user_id in leave_users)),
            "attendance": attendance, "attendance_today": rate(sum(today_present.values()), sum(today_total.values())),
            "short_classes": sum(today_present[key] * 100 < threshold * count for key, count in today_total.items()),
            "pending": sum(len(queue["rows"]) for queue in approvals), "readiness": readiness,
            "active_sections": len(batches), "subjects": len((allocated.subject_id | batches.course_id.subject_ids).filtered(
                lambda subject: subject.company_id.id in (False, self.env.company.id))),
            "coverage": rate(len(allocated), len(sessions)), "unassigned": len(sessions - allocated),
            "pass_rate": pass_rate, "risk": len(risks), "workload": rate(len(allocated.filtered(lambda session: session.faculty_id in faculty)), len(sessions)),
            "completion": rate(completed, expected), "present": len(faculty.filtered(lambda member: member.user_id in present_users)),
            "mentor_groups": len(enrolments.filtered(lambda row: row.student_id in mentors.student_id).batch_id),
            "appraisal_due": len(appraisal), "approvals": approvals, "schedule": schedule,
            "student_rows": [[student.name, student.gr_no or "—",
                ", ".join(sorted(student_sections[student.id])),
                rate(present[student.id], totals[student.id]), student.id in risks] for student in students.sorted("name")],
            "faculty_rows": [[member.name, loads[member.id], _("Present") if member.user_id in present_users
                else _("On leave") if member.user_id in leave_users else _("No punch recorded")] for member in faculty],
            "session_rows": [[row.subject_id.name or row.name, row.batch_id.name, row.faculty_id.name or "—",
                fields.Datetime.context_timestamp(self, row.start_datetime).strftime("%Y-%m-%d %H:%M")]
                for row in sessions],
            "exam_rows": [[exam.name, exam.batch_id.name,
                fields.Datetime.context_timestamp(self, exam.start_time).strftime("%Y-%m-%d %H:%M"),
                dict(exam._fields["campus_state"].selection).get(exam.campus_state, "—")]
                for exam in exams],
        }

    def _approvals(self, department, students, batches, exams, year, semester, start, end):
        user = self.env.user
        paper_role = user.has_group("ideastone_erp.group_exam_paper_hod")
        od_role = user.has_group("ideastone_erp.group_od_hod_approver")
        papers = self._search("campus.question.paper", [("department_id", "=", department.id),
            ("hod_id", "=", user.id), ("state", "in", ["submitted", "approved"])]
            + self._date_domain("exam_date", start, end)) if paper_role else self.env["campus.question.paper"]
        papers = papers.filtered(lambda row: (not year or row.study_year == year)
            and (not semester or row.semester in (("I", "III", "V", "VII") if semester == "odd" else ("II", "IV", "VI", "VIII"))))
        ods = self._search("campus.student.od", [("hod_id", "=", user.id), ("student_id", "in", students.ids),
            ("enrolment_id.batch_id", "in", batches.ids), ("routing_id.active", "=", True),
            ("state", "in", ["pending_hod", "proof_review"])] + self._date_domain("date_from", start, end)) if od_role else self.env["campus.student.od"]
        leave = self.env["campus.student.leave"]
        if leave.check_access_rights("read", raise_exception=False):
            leave = leave.search([("company_id", "=", self.env.company.id), ("hod_id", "=", user.id),
                ("student_id", "in", students.ids), ("state", "=", "hod")] + self._date_domain("date", start, end))
        corrections = self._search("campus.service.request", [("attendance_review_assignee_id", "=", user.id),
            ("attendance_review_mode", "!=", False), ("state", "=", "submitted"),
            "|", ("student_id", "in", students.ids), ("attendance_review_department", "=", department.name)]
            + self._date_domain("date", start, end))
        # Offer native record links only for records the current account can read.
        readable_corrections = self.env["campus.service.request"]
        if readable_corrections.check_access_rights("read", raise_exception=False):
            readable_corrections = readable_corrections.search([("id", "in", corrections.ids)])
        marks = exams.filtered(lambda row: row.campus_managed and row.campus_state in ("entry", "submitted"))
        return [
            {"key": "papers", "name": _("Question-paper submissions"), "tone": "amber", "status": _("Review"),
             "action": "ideastone_erp.action_hod_question_papers" if paper_role else "",
             "rows": [[row.subject_id.name, str(row.exam_date)] for row in papers]},
            {"key": "od", "name": _("OD requests"), "tone": "blue", "status": _("Pending"),
             "action": "ideastone_erp.action_hod_od_management" if od_role else "",
             "rows": [[row.name, str(row.date_from)] for row in ods]},
            {"key": "leave", "name": _("Leave / attendance corrections"), "tone": "amber", "status": _("Pending"),
             "action": "", "rows": [[row.name, str(row.date), "campus.student.leave", row.id] for row in leave]
             + [[row.name, str(row.date), "campus.service.request", row.id if row.id in readable_corrections.ids else False] for row in corrections]},
            {"key": "marks", "name": _("Internal marks verification"), "tone": "red", "status": _("Action needed"),
             "action": "", "columns": [_("Exam"), _("Section"), _("Stage"), _("Marks entered"), _("Roster size")],
             "rows": [[row.name, row.batch_id.name,
                 _("Submitted") if row.campus_state == "submitted" else _("Marks entry"),
                 len(row.campus_result_ids.filtered("campus_entered")), len(row.campus_result_ids)] for row in marks]},
        ], papers

    def _schedule(self, sessions, papers, today, start, end):
        start = max(today, start or today)
        horizon = today + timedelta(days=30)
        end = min(horizon, end or horizon)
        if start > end:
            return []
        events = self._search("campus.calendar.event", [("audience", "=", "All campus"), ("status", "=", "upcoming"),
            ("date_end", ">=", start), ("date_start", "<=", end)])
        rows = [{"name": row.name, "date": str(row.date_start), "detail": row.time, "status": _("Upcoming")} for row in events]
        for row in sessions.filtered(lambda session: session.state == "confirm"):
            day = fields.Datetime.context_timestamp(self, row.start_datetime).date()
            if start <= day <= end:
                rows.append({"name": row.subject_id.name or row.name, "date": str(day),
                    "detail": row.batch_id.name, "status": _("Scheduled")})
        rows += [{"name": _("Question-paper review · %s", row.subject_id.name), "date": str(row.exam_date),
            "detail": _("HOD review queue"), "status": _("Review")} for row in papers if start <= row.exam_date <= end]
        return sorted(rows, key=lambda row: (row["date"], row["name"]))


class HodDashboardNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if not any(data.get(key) for key in ("is_admin", "is_owner_workspace", "is_coe_workspace", "is_principal_workspace")):
            if self.env["campus.hod.dashboard"]._is_hod():
                data.update(hod_dashboard_enabled=True, is_hod=True, faculty_home_enabled=False, workspace_role="HOD")
                home = next((module for module in data["faculty_modules"] if module["key"] == "home"), None)
                if home:
                    home["items"] = [{"label": _("Department overview"), "page": "overview"}]
        return data
