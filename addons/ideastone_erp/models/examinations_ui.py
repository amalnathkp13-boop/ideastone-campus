from collections import defaultdict
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

WORKSPACES = {
    "overview": ("Overview", "op.exam", "mvp_exams"),
    "sessions": ("Exam sessions", "op.exam.session", "mvp_exam_sessions"),
    "marks": ("Schedule & marks entry", "op.exam", "mvp_exams"),
    "grades": ("Grade rules", "op.grade.configuration", "mvp_grades"),
    "results": ("Results & missing entries", "op.result.line", "mvp_results"),
    "papers": ("Question papers", "op.exam", "mvp_exams"),
}


class ExaminationsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        module = next((m for m in data.get("faculty_modules", []) if m["key"] == "exams"), None)
        if module and data.get("is_owner_workspace"):
            module["items"] = [{"label": label, "action": "ideastone_erp.action_examinations_" + view,
                "action_id": self.env.ref("ideastone_erp.action_examinations_" + view).id,
                "source_action": "ideastone_erp." + original, "model": model, "group": "Examinations", "allowed": True}
                for view, (label, model, original) in WORKSPACES.items()
                if self.env[model].check_access_rights("read", raise_exception=False)]
        return data

    def _mvp_module_for(self, xmlid):
        if xmlid in {"ideastone_erp.action_examinations_" + view for view in WORKSPACES}:
            return "exams"
        return super()._mvp_module_for(xmlid)


class ExaminationsUI(models.AbstractModel):
    _name = "campus.examinations.ui"
    _description = "Access-controlled examination workspace"

    def _records(self, model, domain):
        return self.env["campus.dashboard"]._mvp_records(model, domain)

    def _datetime(self, value, short=False):
        return fields.Datetime.context_timestamp(self, value).strftime("%d %b, %I:%M %p" if short else "%d %b %Y · %I:%M %p") if value else "—"

    def _percent(self, numerator, denominator):
        return round(100 * numerator / denominator, 1) if denominator else None

    @api.model
    def get_workspace(self, view="overview", filters=None, query="", page=0):
        if not isinstance(view, str) or view not in WORKSPACES:
            raise ValidationError(_("Choose a valid examinations workspace."))
        f = self.env["campus.dashboard"]._mvp_filters(filters)
        self.env[WORKSPACES[view][1]].check_access_rights("read")
        if not isinstance(query, str) or len(query) > 200 or isinstance(page, bool) or not isinstance(page, int) or not 0 <= page <= 2000:
            raise ValidationError(_("Use a valid search and page."))
        raw = filters or {}
        for key, model in (("session_id", "op.exam.session"), ("type_id", "op.exam.type")):
            value = raw.get(key) or 0
            if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).isdigit() or not 0 <= int(value) <= 2147483647:
                raise ValidationError(_("Choose a valid exam session or type."))
            f[key] = int(value)
            if f[key] and not self._records(model, [("id", "=", f[key]), ("company_id", "=", self.env.company.id)]):
                raise AccessError(_("Choose an examination record in the active college."))
        if f["department_id"] and not self._records("op.department", [("id", "=", f["department_id"]), ("company_id", "=", self.env.company.id)]):
            raise AccessError(_("Choose a department in the active college."))
        if not isinstance(raw.get("status", ""), str) or raw.get("status", "") not in {"", "draft", "schedule", "held", "cancel", "done", "entry", "submitted", "locked", "published", "missing"}:
            raise ValidationError(_("Choose a valid examination status."))
        paper_department = raw.get("paper_department_id", "")
        if isinstance(paper_department, bool) or not isinstance(paper_department, (str, int)) or str(paper_department) and (not str(paper_department).isdigit() or not 0 <= int(paper_department) <= 2147483647):
            raise ValidationError(_("Choose a valid question-paper department."))
        f["paper_department_id"] = int(paper_department) if str(paper_department) else ""
        if f["paper_department_id"] and not self._records("op.department", [("id", "=", f["paper_department_id"]), ("company_id", "=", self.env.company.id)]):
            raise AccessError(_("Choose a question-paper department in the active college."))
        if raw.get("paper_period", "all") not in ("all", "upcoming", "previous"):
            raise ValidationError(_("Choose a valid question-paper period."))
        f["paper_period"] = raw.get("paper_period", "all")
        company = [("company_id", "=", self.env.company.id)]
        domain = company + ([("campus_year_id", "=", f["year_id"])] if f["year_id"] else [])
        sessions = self._records("op.exam.session", domain)
        if f["department_id"]:
            sessions = sessions.filtered(lambda r: r.course_id.department_id.id == f["department_id"])
        if f["session_id"]:
            sessions = sessions.filtered(lambda r: r.id == f["session_id"])
        if f["type_id"]:
            sessions = sessions.filtered(lambda r: r.exam_type.id == f["type_id"])
        exams = self._records("op.exam", company + [("campus_managed", "=", True), ("session_id", "in", sessions.ids)])
        results = self._records("op.result.line", company + [("exam_id", "in", exams.ids)])
        grades = self._records("op.grade.configuration", company).sorted("min_per", reverse=True)
        pass_marks = {self._percent(exam.min_marks, exam.total_marks) for exam in exams if exam.total_marks}
        papers_allowed = self.env["campus.faculty.document"].check_access_rights("read", raise_exception=False)
        papers = self._records("campus.faculty.document", company + [("kind", "=", "question")])
        if any(f[key] for key in ("year_id", "department_id", "session_id", "type_id")):
            papers = papers.filtered(lambda p: p.exam_id in exams)
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        published = exams.filtered(lambda e: e.campus_state == "published").sorted(lambda e: e.campus_published_on or e.start_time, reverse=True)
        latest_sessions = {}
        for exam in published:
            latest_sessions.setdefault(exam.course_id.department_id.id, exam.session_id)
        snapshot = results.filtered(lambda r: r.exam_id in published and r.campus_entered
            and r.exam_id.session_id == latest_sessions.get(r.exam_id.course_id.department_id.id))
        passed = snapshot.filtered(lambda r: r.status == "pass")
        failed = snapshot.filtered(lambda r: r.status == "fail")
        missing = results.filtered(lambda r: not r.campus_entered)
        rosters = defaultdict(list)
        for result in results:
            rosters[result.exam_id.id].append(result)
        labels = dict(self.env["op.exam"]._fields["campus_state"].selection)
        session_labels = dict(self.env["op.exam.session"]._fields["state"].selection)
        session_rows = [{"id": s.id, "kind": "sessions", "name": s.name, "code": s.exam_code, "type": s.exam_type.name,
            "audience": s.course_id.name, "section": s.batch_id.name, "start": str(s.start_date), "end": str(s.end_date),
            "year": s.campus_year_id.name or "—", "status_key": s.state, "status": session_labels[s.state],
            "tone": "green" if s.state == "done" else "amber" if s.state == "draft" else "red" if s.state == "cancel" else "blue"}
            for s in sessions.sorted("start_date", reverse=True)]
        exam_rows = []
        for exam in exams.sorted("start_time", reverse=True):
            roster = rosters[exam.id]
            entered = sum(r.campus_entered for r in roster)
            exam_rows.append({"id": exam.id, "kind": "marks", "name": exam.subject_id.name, "code": exam.exam_code,
                "session": exam.session_id.name, "section": exam.batch_id.name, "department": exam.course_id.department_id.name or _("Not assigned"),
                "start": self._datetime(exam.start_time), "end": self._datetime(exam.end_time),
                "faculty": ", ".join(exam.responsible_id.mapped("name")) or _("Unassigned"),
                "total": len(roster), "entered": entered, "missing": len(roster) - entered,
                "status_key": exam.campus_state, "status": labels[exam.campus_state],
                "tone": "green" if exam.campus_state in {"submitted", "locked", "published"} else "amber" if exam.campus_state == "entry" else "blue"})
        grouped = defaultdict(list)
        for result in results.filtered(lambda r: r.exam_id.campus_state == "published"):
            grouped[(result.exam_id.course_id.department_id, result.exam_id.session_id)].append(result)
        result_rows = []
        for (department, session), lines in grouped.items():
            entered = [r for r in lines if r.campus_entered]
            n_pass = sum(r.status == "pass" for r in entered)
            result_rows.append({"id": f"{department.id}-{session.id}", "kind": "results", "name": department.name or _("Not assigned"),
                "code": department.code or "—", "exam": session.name, "session_id": session.id, "appeared": len(entered),
                "passed": n_pass, "failed": sum(r.status == "fail" for r in entered), "missing": len(lines) - len(entered),
                "rate": self._percent(n_pass, len(entered)), "status": _("Published"), "status_key": "published", "tone": "green"})
        grade_rows = [{"id": g.id, "kind": "grades", "name": g.result, "minimum": g.min_per, "maximum": g.max_per,
            "uses": len(exams.filtered(lambda e, grade=g: grade in e.campus_grade_ids)), "company": g.company_id.name,
            "locked": bool(exams.filtered(lambda e, grade=g: grade in e.campus_grade_ids and e.campus_state in {"locked", "published"}))}
            for g in grades]
        paper_rows = [{"id": p.id, "name": p.name, "kind": "papers", "code": f"QP-{p.id:05}", "subject": p.subject_id.name or _("Subject not assigned"),
            "exam": p.exam_id.name or _("Exam not assigned"), "type": p.exam_id.session_id.exam_type.name or "—",
            "department_id": p.exam_id.course_id.department_id.id or p.subject_id.department_id.id or 0,
            "filename": p.filename, "updated": self._datetime(p.write_date), "updated_short": self._datetime(p.write_date, short=True), "owner": p.user_id.name,
            "previous": bool(p.exam_id and p.exam_id.end_time < now), "upcoming": bool(p.exam_id and p.exam_id.start_time >= now), "status": dict(p._fields["state"].selection)[p.state],
            "tone": "green" if p.state == "done" else "amber", "status_key": p.state}
            for p in papers.sorted("write_date", reverse=True)]
        departments = self._records("op.department", company)
        department_rows = []
        for dept in departments.sorted("name"):
            docs = [p for p in paper_rows if p["department_id"] == dept.id]
            lines = snapshot.filtered(lambda r, d=dept: r.exam_id.course_id.department_id == d)
            department_rows.append({"id": dept.id, "name": dept.name, "code": dept.code or "—", "papers": len(docs),
                "completed": sum(p["status_key"] == "done" for p in docs), "pending": sum(p["status_key"] != "done" for p in docs),
                "updated": docs[0]["updated_short"] if docs else _("No question papers yet"), "appeared": len(lines),
                "passed": len(lines.filtered(lambda r: r.status == "pass")), "failed": len(lines.filtered(lambda r: r.status == "fail")),
                "rate": self._percent(len(lines.filtered(lambda r: r.status == "pass")), len(lines))})
        if any(p["department_id"] == 0 for p in paper_rows):
            unassigned = [p for p in paper_rows if p["department_id"] == 0]
            department_rows.append({"id": 0, "name": _("Department not assigned"), "code": "—", "papers": len(unassigned),
                "completed": sum(p["status_key"] == "done" for p in unassigned), "pending": sum(p["status_key"] != "done" for p in unassigned),
                "updated": _("Review document details"), "appeared": 0, "passed": 0, "failed": 0, "rate": None})
        session_by_id = {r["id"]: r for r in session_rows}
        upcoming = [dict(session_by_id[s.id], month=s.start_date.strftime("%b"), day=s.start_date.strftime("%d"), days=(s.start_date - today).days)
            for s in sessions.sorted("start_date") if today <= s.start_date <= today + timedelta(days=30) and s.state != "cancel"]
        activity = [{"id": f"exam-{e.id}", "name": f"{e.name} · {labels[e.campus_state]}", "detail": self._datetime(e.write_date), "date": e.write_date, "kind": "marks", "record_id": e.id,
            "tone": "green" if e.campus_state == "locked" else "amber" if e.campus_state in {"entry", "submitted"} else "",
            "icon": "✓" if e.campus_state == "locked" else "◷" if e.campus_state in {"entry", "submitted"} else "▤"}
            for e in exams.sorted("write_date", reverse=True)[:5]]
        activity += [{"id": f"paper-{p.id}", "name": p.name, "detail": _("Question paper updated · ") + self._datetime(p.write_date), "date": p.write_date, "kind": "papers", "record_id": p.id,
            "tone": "green" if p.state == "done" else "amber", "icon": "✓" if p.state == "done" else "◷"} for p in papers.sorted("write_date", reverse=True)[:5]]
        rows = {"sessions": session_rows, "marks": exam_rows, "grades": grade_rows, "results": result_rows, "papers": paper_rows}.get(view, [])
        if view == "papers":
            rows = [r for r in rows if (f["paper_department_id"] == "" or r["department_id"] == f["paper_department_id"])
                and (f["paper_period"] == "all" or r[f["paper_period"]])]
        term = query.strip().casefold()
        rows = [r for r in rows if (not f["status"] or r.get("status_key") == f["status"] or f["status"] == "missing" and r.get("missing", 0))
            and (not term or term in " ".join(str(v) for v in r.values()).casefold())]
        return {"today": str(today), "company": self.env.company.name, "view": view,
            "filters": {k: f[k] for k in ("year_id", "department_id", "session_id", "type_id", "status", "paper_department_id", "paper_period")},
            "counts": {"upcoming": len(upcoming), "pass_rate": self._percent(len(passed), len(snapshot)), "failure_rate": self._percent(len(failed), len(snapshot)),
                "followup": len((failed | missing).student_id), "passed": len(passed), "failed": len(failed), "evaluated": len(snapshot),
                "sessions": len(sessions), "scheduled_sessions": len(sessions.filtered(lambda r: r.state == "schedule")), "types": len(sessions.exam_type),
                "papers": len(papers), "previous_papers": sum(p["previous"] for p in paper_rows), "exams": len(exams),
                "submitted": len(exams.filtered(lambda r: r.campus_state in {"submitted", "locked", "published"})), "faculty": sum(len(e.responsible_id) for e in exams),
                "unassigned": len(exams.filtered(lambda r: not r.responsible_id)), "grades": len(grades), "grade_uses": len(exams.filtered("campus_grade_ids")),
                "missing": len(missing), "missing_exams": len(missing.exam_id), "locked_grades": sum(g["locked"] for g in grade_rows),
                "pass_mark": next(iter(pass_marks)) if len(pass_marks) == 1 else None},
            "snapshot": _("Latest published session per department") if published else _("No published results"), "departments": department_rows, "upcoming": upcoming[:4],
            "activity": [{k: v for k, v in item.items() if k != "date"} for item in sorted(activity, key=lambda a: a["date"], reverse=True)[:4]],
            "missing_exams": [r for r in exam_rows if r["missing"]][:5], "rows": rows[page * 30:(page + 1) * 30], "total_rows": len(rows),
            "years": [{"id": y.id, "name": y.name} for y in self._records("op.academic.year", company).sorted("start_date", reverse=True)],
            "sessions": [{"id": s.id, "name": s.name} for s in self._records("op.exam.session", domain)],
            "types": [{"id": t.id, "name": t.name} for t in self._records("op.exam.type", company)],
            "papers_allowed": papers_allowed, "can_create": self.env["campus.faculty.document" if view == "papers" else WORKSPACES[view][1]].check_access_rights("create", raise_exception=False)}

    @api.model
    def get_record_action(self, kind, record_id=None):
        self.env["campus.dashboard"]._mvp_filters()
        if not isinstance(kind, str) or kind not in {"sessions", "marks", "grades", "papers"}:
            raise ValidationError(_("Choose a valid examination record."))
        model, xmlid, form = ("campus.faculty.document", "action_faculty_document", "view_faculty_document_form") if kind == "papers" else (
            WORKSPACES[kind][1], WORKSPACES[kind][2], {"sessions": "mvp_exam_sessions_form", "marks": "mvp_exams_form", "grades": "mvp_grades_form"}[kind])
        source = self.env[model]
        source.check_access_rights("read")
        if record_id is None:
            source.check_access_rights("create")
        else:
            if isinstance(record_id, bool) or not isinstance(record_id, int) or not 1 <= record_id <= 2147483647:
                raise ValidationError(_("Choose a valid record ID."))
            domain = [("id", "=", record_id), ("company_id", "=", self.env.company.id)]
            if kind == "papers":
                domain.append(("kind", "=", "question"))
            elif kind == "marks":
                domain.append(("campus_managed", "=", True))
            if not source.search_count(domain):
                raise AccessError(_("This record is outside your examination workspace."))
        if kind == "papers":
            self.env["op.exam"].check_access_rights("read")
            action = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp." + xmlid)
            action["context"] = {"default_kind": "question", "default_company_id": self.env.company.id}
        else:
            action = self.env["campus.dashboard"].get_owner_action("ideastone_erp." + xmlid)
        action.update(views=[(self.env.ref("ideastone_erp." + form).id, "form")], view_mode="form")
        action["context"].update(campus_module="exams")
        if record_id:
            action["res_id"] = record_id
        return action
