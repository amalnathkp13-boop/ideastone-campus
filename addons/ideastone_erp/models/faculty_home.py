from datetime import datetime, time, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyHomeNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if data.get("faculty_modules") and not any(data.get(key) for key in ("is_admin", "is_owner_workspace", "is_hod", "is_coe_workspace")):
            data["faculty_home_enabled"] = True
            home = next((module for module in data["faculty_modules"] if module["key"] == "home"), None)
            if home:
                home["items"].insert(1, {"label": "My departments", "page": "faculty-departments"})
        return data


class FacultyHome(models.AbstractModel):
    _name = "campus.faculty.home"
    _description = "Faculty home and allocated class directory"

    def _read(self, model, domain, order="id", limit=15000):
        source = self.env[model]
        if not source.check_access_rights("read", raise_exception=False):
            return source
        domain = [("company_id", "=", self.env.company.id)] + domain
        if source.search_count(domain) > limit:
            raise ValidationError(_("This teaching scope is too large. Review the active-year allocations."))
        return source.search(domain, order=order, limit=limit)

    def _scope(self):
        faculty = self.env["campus.question.paper"]._faculty()
        today = fields.Date.context_today(self)
        available_years = self._read("op.academic.year", [], "start_date desc, id desc")
        years = (available_years.filtered("campus_current") or available_years.filtered(lambda r: r.start_date <= today <= r.end_date))[:1]
        sessions = self._read("op.session", [("faculty_id", "=", faculty.id), ("state", "in", ["confirm", "done"])] +
            (["|", ("campus_year_id", "=", False), ("campus_year_id", "=", years.id)] if years else []), "start_datetime, id")
        batches = sessions.batch_id.filtered(lambda r: r.active and r.company_id == self.env.company)
        sessions = sessions.filtered(lambda r: r.batch_id in batches)
        enrolments = self._read("op.student.course", [("batch_id", "in", batches.ids), ("state", "=", "running"),
            ("student_id.active", "=", True), ("campus_date_from", "<=", today),
            "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", today)])
        return faculty, years, sessions, batches, enrolments

    def _study_year(self, batch):
        term = batch.campus_term_id
        return (term.campus_sequence + 1) // 2 if term else -1

    @api.model
    def get_directory(self, department_id=0, study_year=0, section_id=0):
        faculty, year, sessions, batches, enrolments = self._scope()
        for value in (department_id, section_id):
            if type(value) is not int or not 0 <= value <= 2147483647:
                raise ValidationError(_("Choose a valid allocated department or section."))
        if type(study_year) is not int or not -1 <= study_year <= 50:
            raise ValidationError(_("Choose a valid year of study."))
        departments = batches.course_id.department_id.filtered(lambda r: r.company_id == self.env.company)
        selected = departments.filtered(lambda r: r.id == department_id)
        if department_id and not selected:
            raise AccessError(_("This department is outside your current teaching allocations."))
        local_batches = batches.filtered(lambda r: r.course_id.department_id == selected) if selected else batches.browse()
        years = sorted({self._study_year(batch) for batch in local_batches})
        if study_year and (not selected or study_year not in years):
            raise AccessError(_("This year is outside your allocated department."))
        cohorts = local_batches.filtered(lambda r: self._study_year(r) == study_year) if study_year else local_batches.browse()
        section = cohorts.filtered(lambda r: r.id == section_id)
        if section_id and not section:
            raise AccessError(_("This section is outside your allocated department and year."))
        students = enrolments.filtered(lambda r: r.batch_id == section) if section else enrolments.browse()
        return {"company": self.env.company.name, "academic_year": year.name or _("Assigned classes"),
            "departments": [{"id": d.id, "name": d.name, "code": d.code or "—",
                "years": len({self._study_year(b) for b in batches if b.course_id.department_id == d}),
                "sections": len(batches.filtered(lambda b, d=d: b.course_id.department_id == d))} for d in departments.sorted(lambda d: (d != faculty.main_department_id, d.name))],
            "years": [{"id": value, "label": _("Year %s", value) if value > 0 else _("Year not recorded"),
                "sections": len(local_batches.filtered(lambda b, value=value: self._study_year(b) == value))} for value in years],
            "sections": [{"id": b.id, "name": b.name, "programme": b.course_id.name,
                "students": len(enrolments.filtered(lambda e, b=b: e.batch_id == b).student_id)} for b in cohorts.sorted("name")],
            "students": [{"id": e.id, "name": e.student_id.name, "register": e.student_id.gr_no or e.roll_number or "—",
                "programme": e.course_id.name, "section": e.batch_id.name,
                "email": e.student_id.email or "—", "status": e.student_id.campus_status.replace("_", " ").title()} for e in students.sorted(lambda e: e.student_id.name)],
            "selected": {"department": selected.name or "", "year": study_year, "section": section.name or ""}}

    @api.model
    def get_home(self):
        faculty, year, sessions, batches, enrolments = self._scope()
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        zone = pytz.timezone(self.env.user.tz or "UTC")
        def utc_day(day):
            return zone.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        start, end = utc_day(today), utc_day(today + timedelta(days=1))
        day_sessions = sessions.filtered(lambda r: r.start_datetime < end and r.end_datetime > start)
        sheets = self._read("op.attendance.sheet", [("faculty_id", "=", faculty.id), ("session_id", "in", sessions.ids), ("state", "=", "done")])
        submitted_ids = set(sheets.session_id.ids)
        pending = day_sessions.filtered(lambda r: r.end_datetime <= now and r.id not in submitted_ids)
        next_class = day_sessions.filtered(lambda r: r.state != "done" and r.end_datetime > now)[:1]
        schedule = []
        for session in day_sessions:
            status = "done" if session.state == "done" else "next" if session == next_class else "elapsed" if session.end_datetime <= now else "upcoming"
            schedule.append({"id": session.id, "time": "%s–%s" % (fields.Datetime.context_timestamp(self, session.start_datetime).strftime("%H:%M"),
                fields.Datetime.context_timestamp(self, session.end_datetime).strftime("%H:%M")), "subject": session.subject_id.name,
                "class": session.batch_id.name, "room": session.classroom_id.name or _("Room not assigned"), "status": status,
                "attendance": session.id in submitted_ids})
        task_records = self._read("campus.faculty.task", [("user_id", "=", self.env.uid)], "deadline, priority desc, id")
        tasks = task_records.filtered(lambda r: r.state in {"planned", "progress"})
        from_day = year.start_date if year else today - timedelta(days=90)
        lines = self._read("op.attendance.line", [("attendance_id", "in", sheets.ids), ("attendance_date", ">=", from_day), ("attendance_date", "<=", today)])
        attendance = []
        for subject in sessions.subject_id.sorted("name"):
            subject_lines = lines.filtered(lambda r, subject=subject: r.attendance_id.campus_subject_id == subject)
            rows = self.env["campus.dashboard"]._attendance_rows(subject_lines)
            total = sum(r["sessions"] for r in rows)
            present = sum(r["present"] for r in rows)
            attendance.append({"id": subject.id, "name": subject.name, "rate": round(present * 100 / total, 1) if total else None,
                "shortage": sum(r["shortage"] for r in rows), "recorded": total})
        exams = self._read("op.exam", [("responsible_id", "in", faculty.ids), ("batch_id", "in", batches.ids),
            ("subject_id", "in", sessions.subject_id.ids), ("state", "!=", "cancel")], "start_time desc, id desc")
        results = self._read("op.result.line", [("exam_id", "in", exams.filtered(lambda r: r.state == "done").ids)])
        assessments = []
        for exam in exams.filtered(lambda r: r.state == "done"):
            marks = results.filtered(lambda r, exam=exam: r.exam_id == exam and (not exam.campus_managed or r.campus_entered))
            if marks and exam.total_marks:
                assessments.append({"id": exam.id, "name": exam.name, "class": exam.batch_id.name,
                    "average": round(sum(marks.mapped("marks")) * 100 / len(marks) / exam.total_marks, 1)})
        papers = self._read("campus.question.paper", [("faculty_id", "=", faculty.id)], "write_date desc, id desc")
        paper_states = dict(self.env["campus.question.paper"]._fields["state"].selection)
        updates = [{"name": p.subject_id.name + " · " + p.paper_code, "date": str(p.exam_date), "status": paper_states[p.state],
                    "kind": "papers"} for p in papers if p.exam_date >= today - timedelta(days=7)][:5]
        updates += [{"name": e.name + " · " + e.subject_id.name, "date": str(fields.Datetime.context_timestamp(self, e.start_time).date()),
            "status": _("Scheduled"), "kind": "results"} for e in exams if now <= e.start_time <= now + timedelta(days=30)][:3]
        notices = self._read("campus.circular", [("campus_status", "=", "published"), ("audience", "in", ["all", "faculty"]),
            ("date_from", "<=", today), "|", ("date_to", "=", False), ("date_to", ">=", today)], "date_from desc, id desc")
        notices = notices.filtered(lambda n: (not n.campus_batch_id or n.campus_batch_id in batches)
            and (not n.campus_course_id or n.campus_course_id in batches.course_id)
            and (not n.campus_group_id or n.campus_group_id in self.env.user.groups_id))
        updates += [{"name": n.name, "date": str(n.date_from), "status": _("Notice"), "kind": "notices"} for n in notices[:3]]
        activity = [{"name": _("%s attendance submitted", s.session_id.subject_id.name), "at": s.campus_submitted_on or s.write_date, "tone": "green"} for s in sheets]
        activity += [{"name": p.paper_code + " · " + paper_states[p.state], "at": p.write_date, "tone": "orange"} for p in papers[:5]]
        activity += [{"name": t.name + " · " + dict(t._fields["state"].selection)[t.state], "at": t.write_date, "tone": "blue"} for t in task_records.sorted("write_date", reverse=True)[:5]]
        activity += [{"name": n.name, "at": n.approved_on or n.write_date, "tone": "green"} for n in notices[:3]]
        activity = [{"name": row["name"], "date": str(fields.Datetime.context_timestamp(self, row["at"]).date()), "tone": row["tone"]}
                    for row in sorted(activity, key=lambda r: r["at"], reverse=True)[:20]]
        completed = len(day_sessions.filtered(lambda r: r.state == "done"))
        return {"user": self.env.user.name, "company": self.env.company.name, "demo": self.env.company.campus_demo,
            "today": str(today), "academic_year": year.name or _("Assigned classes"), "department": faculty.main_department_id.code or faculty.main_department_id.name or _("Not recorded"),
            "semesters": sorted(set(batches.campus_term_id.mapped("name"))), "schedule": schedule,
            "counts": {"classes": len(day_sessions), "completed": completed, "remaining": len(day_sessions) - completed,
                "students": len(enrolments.student_id), "subjects": len(sessions.subject_id | faculty.faculty_subject_ids), "pending": len(pending),
                "tasks": len(tasks), "due_today": len(tasks.filtered(lambda r: r.deadline == today)), "overdue": len(tasks.filtered(lambda r: r.deadline < today)),
                "upcoming": len(tasks.filtered(lambda r: r.deadline > today)), "papers": len(papers.filtered(lambda r: r.state in {"draft", "returned"})),
                "marks_pending": len(exams.filtered(lambda r: r.campus_managed and r.campus_state in {"draft", "entry"}))},
            "attendance": attendance, "threshold": self.env.company.campus_attendance_threshold,
            "assessments": assessments[:3], "updates": updates[:8], "activity": activity,
            "tasks": [{"id": t.id, "name": t.name, "date": str(t.deadline)} for t in tasks[:5]]}

    @api.model
    def get_action(self, kind, record_id=0):
        faculty, year, sessions, batches, enrolments = self._scope()
        if not isinstance(kind, str):
            raise ValidationError(_("Choose a valid faculty workspace action."))
        if type(record_id) is not int or not 0 <= record_id <= 2147483647:
            raise ValidationError(_("Choose a valid assigned record."))
        if kind == "take_attendance":
            session = sessions.filtered(lambda r: r.id == record_id)
            if not session:
                raise AccessError(_("This class is outside your confirmed teaching allocations."))
            return session.action_campus_attendance()
        actions = {"attendance": "ideastone_erp.action_subject_attendance_workspace",
            "tasks": "ideastone_erp.action_faculty_task", "papers": "ideastone_erp.action_faculty_question_papers"}
        if kind in actions:
            action = self.env["ir.actions.actions"]._for_xml_id(actions[kind])
            action["context"] = dict(self.env.context, campus_module="attendance" if kind == "attendance" else "teaching")
            return action
        if kind in {"timetable", "results"}:
            model = "op.session" if kind == "timetable" else "op.exam"
            self.env[model].check_access_rights("read")
            domain = [("faculty_id", "=", faculty.id), ("id", "in", sessions.ids)] if kind == "timetable" else [("responsible_id", "in", faculty.ids), ("batch_id", "in", batches.ids)]
            return {"type": "ir.actions.act_window", "name": _("My timetable") if kind == "timetable" else _("My assessments"),
                "res_model": model, "views": [(False, "tree"), (False, "form")], "domain": [("company_id", "=", self.env.company.id)] + domain,
                "context": dict(self.env.context, campus_module="teaching")}
        raise ValidationError(_("Choose a valid faculty workspace action."))
