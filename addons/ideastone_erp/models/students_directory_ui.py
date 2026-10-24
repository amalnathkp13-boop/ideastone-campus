from collections import defaultdict
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

VIEWS = {
    "directory": ("Student directory", "op.student", "mvp_students"),
    "enrolments": ("Enrolments & transfers", "op.student.course", "mvp_enrolments"),
}


class StudentsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        module = next((m for m in data.get("faculty_modules", []) if m["key"] == "students"), None)
        if module and data.get("is_owner_workspace"):
            module["items"] = [{"label": label, "action": "ideastone_erp.action_students_" + view,
                "action_id": self.env.ref("ideastone_erp.action_students_" + view).id,
                "source_action": "ideastone_erp." + original, "model": model, "group": "Students", "allowed": True}
                for view, (label, model, original) in VIEWS.items()
                if self.env[model].check_access_rights("read", raise_exception=False)]
        return data

    def _mvp_module_for(self, xmlid):
        if xmlid in {"ideastone_erp.action_students_" + view for view in VIEWS}:
            return "students"
        return super()._mvp_module_for(xmlid)


class StudentsDirectoryUI(models.AbstractModel):
    _name = "campus.students.ui"
    _description = "College student directory projections"

    def _read(self, model, domain):
        return self.env["campus.dashboard"].with_context(active_test=False)._mvp_records(model, domain)

    def _filters(self, filters):
        f = self.env["campus.dashboard"]._mvp_filters(filters)
        raw = filters or {}
        company = [("company_id", "=", self.env.company.id)]
        if "year_id" not in raw:
            years = self._read("op.academic.year", company + [("active", "=", True)])
            today = fields.Date.context_today(self)
            current = years.filtered("campus_current") or years.filtered(lambda r: r.start_date <= today <= r.end_date)
            f["year_id"] = current.sorted("start_date", reverse=True)[:1].id or 0
        for key, model in (("department_id", "op.department"), ("batch_id", "op.batch")):
            if f[key] and not self._read(model, company + [("id", "=", f[key])]):
                raise AccessError(_("Choose a department or section in the active college."))
        if f["batch_id"] and f["department_id"]:
            section = self.env["op.batch"].browse(f["batch_id"])
            if section.course_id.department_id.id != f["department_id"]:
                raise ValidationError(_("Choose a section in the selected department."))
        enums = {"capacity": {"", "under80", "80to89", "90plus"}, "section_size": {"", "small", "large"},
                 "record_type": {"", "running", "finished", "incomplete"}, "submitted": {"", "recent"},
                 "status": {"", "active", "applicant", "on_hold", "graduated", "withdrawn", "archived", "running", "finished"}}
        for key, values in enums.items():
            if not isinstance(raw.get(key, ""), str) or raw.get(key, "") not in values:
                raise ValidationError(_("Choose a valid directory filter."))
            f[key] = raw.get(key, "")
        study_year = raw.get("study_year", "")
        if isinstance(study_year, bool) or not isinstance(study_year, (str, int)) or str(study_year) not in {"", *map(str, range(0, 51))}:
            raise ValidationError(_("Choose a valid year of study."))
        f["study_year"] = int(study_year or 0)
        if not isinstance(raw.get("attention", False), bool):
            raise ValidationError(_("Choose a valid profile review filter."))
        f["attention"] = raw.get("attention", False)
        return f

    def _enrolment_domain(self, f):
        domain = [("company_id", "=", self.env.company.id)]
        if f["year_id"]:
            domain.append(("academic_years_id", "=", f["year_id"]))
        return domain

    def _date(self, value):
        return fields.Datetime.context_timestamp(self, value).strftime("%d %b %Y, %H:%M") if value else "—"

    @api.model
    def get_workspace(self, view="directory", filters=None, query="", page=0, export=False):
        if view not in VIEWS:
            raise ValidationError(_("Choose a valid Students workspace."))
        f = self._filters(filters)
        self.env[VIEWS[view][1]].check_access_rights("read")
        if isinstance(page, bool) or not isinstance(page, int) or not 0 <= page <= 2000 or not isinstance(export, bool):
            raise ValidationError(_("Choose a valid directory page."))
        if not isinstance(query, str) or len(query) > 200:
            raise ValidationError(_("Use a search of at most 200 characters."))
        company = [("company_id", "=", self.env.company.id)]
        students = self._read("op.student", company)
        enrolments = self._read("op.student.course", self._enrolment_domain(f) + [("student_id", "in", students.ids)])
        if f["year_id"]:
            enrolled_ids = set(enrolments.student_id.ids)
            students = students.filtered(lambda s: s.id in enrolled_ids)
        sections = self._read("op.batch", company + ([("campus_year_id", "=", f["year_id"])] if f["year_id"] else []))
        departments = self._read("op.department", company + [("active", "=", True)])
        intakes = self._read("op.admission.register", company + [("state", "!=", "cancel")] +
                             ([("academic_years_id", "=", f["year_id"])] if f["year_id"] else []))
        today = fields.Date.context_today(self)
        placements = defaultdict(list)
        for enrolment in enrolments.sorted(lambda r: (r.state == "running", r.campus_date_from or today, r.id), reverse=True):
            placements[enrolment.student_id.id].append(enrolment)
        section_rows = []
        for section in sections.sorted("name"):
            roster = enrolments.filtered(lambda r, batch=section: r.batch_id == batch and r.state == "running")
            term = section.campus_term_id
            section_rows.append({"id": section.id, "name": section.name, "department_id": section.course_id.department_id.id or 0,
                "programme": section.course_id.name, "semester": term.name or _("Semester not assigned"),
                "study_year": (term.campus_sequence + 1) // 2 if term else 0,
                "year": section.campus_year_id.name or _("Academic year not assigned"), "count": len(roster.student_id)})
        department_rows = []
        for department in departments.sorted("name"):
            rows = enrolments.filtered(lambda r, dept=department: r.course_id.department_id == dept)
            members = rows.student_id
            active = rows.filtered(lambda r: r.state == "running").student_id.filtered(lambda s: s.active and s.campus_status == "active")
            capacity = sum(intakes.filtered(lambda r, dept=department: r.course_id.department_id == dept).mapped("max_count"))
            department_rows.append({"id": department.id, "name": department.name, "code": department.code or "—", "count": len(members),
                "capacity": capacity, "active": len(active), "inactive": len(members - active), "available": max(0, capacity - len(members)) if capacity else None,
                "fill": round(len(members) * 100 / capacity, 1) if capacity else None,
                "sections": sum(r["department_id"] == department.id for r in section_rows)})
        labels = dict(self.env["op.student"]._fields["campus_status"].selection)
        rows = []
        for student in students.sorted(lambda r: (r.write_date, r.id), reverse=True):
            assigned = placements[student.id]
            matches = [e for e in assigned if (not f["department_id"] or e.course_id.department_id.id == f["department_id"])
                       and (not f["batch_id"] or e.batch_id.id == f["batch_id"])
                       and (not f["study_year"] or e.academic_term_id and (e.academic_term_id.campus_sequence + 1) // 2 == f["study_year"])]
            if (f["department_id"] or f["batch_id"] or f["study_year"]) and not matches:
                continue
            placement = matches[0] if matches else assigned[0] if assigned else self.env["op.student.course"]
            missing = []
            if not (student.register_no or student.gr_no):
                missing.append(_("Registration number"))
            if not student.email:
                missing.append(_("Email"))
            if not (student.phone or student.mobile):
                missing.append(_("Contact number"))
            if self.env["op.student.course"].check_access_rights("read", raise_exception=False) and not any(e.batch_id and e.academic_years_id and e.academic_term_id for e in assigned):
                missing.append(_("Academic placement"))
            status = student.campus_status if student.active else "archived"
            rows.append({"id": student.id, "name": student.name, "register": student.register_no or student.gr_no or "—", "email": student.email or "—",
                "department": placement.course_id.department_id.name or _("Not assigned"), "department_id": placement.course_id.department_id.id or 0,
                "programme": placement.course_id.name or _("Not assigned"), "year": placement.academic_years_id.name or "—",
                "semester": placement.academic_term_id.name or "—", "section": placement.batch_id.name or _("Not assigned"),
                "updated": self._date(student.write_date), "status_key": status, "status": labels.get(status, _("Archived")),
                "tone": "" if status == "active" else "pending" if status == "on_hold" else "red" if status in {"withdrawn", "archived"} else "blue",
                "missing": missing, "attention": bool(missing), "kind": "student"})
        visible_ids = {row["id"] for row in rows}
        records = enrolments.filtered(lambda r: r.student_id.id in visible_ids
            and (not f["department_id"] or r.course_id.department_id.id == f["department_id"])
            and (not f["batch_id"] or r.batch_id.id == f["batch_id"])
            and (not f["study_year"] or r.academic_term_id and (r.academic_term_id.campus_sequence + 1) // 2 == f["study_year"]))
        enrolment_rows = []
        for record in records.sorted(lambda r: (r.write_date, r.id), reverse=True):
            complete = bool(record.batch_id and record.academic_years_id and record.academic_term_id)
            enrolment_rows.append({"id": record.id, "reference": "ENR-" + str(record.id).zfill(5), "student_id": record.student_id.id,
                "name": record.student_id.name, "register": record.student_id.register_no or record.student_id.gr_no or "—",
                "type": _("Placement needs details") if not complete else _("Finished placement") if record.state == "finished" else _("Running enrolment"),
                "type_key": "incomplete" if not complete else record.state, "programme": record.course_id.name,
                "section": record.batch_id.name or _("Not assigned"), "year": record.academic_years_id.name or "—",
                "effective": str(record.campus_date_from or "—"), "until": str(record.campus_date_to or "—"),
                "submitted": self._date(record.create_date), "recent": record.create_date.date() >= today - timedelta(days=7),
                "status_key": record.state or "", "status": _("Running") if record.state == "running" else _("Finished"),
                "tone": "" if record.state == "running" else "blue", "reason": record.campus_reason or "—", "kind": "enrolment"})
        years = self._read("op.academic.year", company + [("active", "=", True)]).sorted("start_date", reverse=True)
        selected_year = years.filtered(lambda r: r.id == f["year_id"])[:1]
        period_start = selected_year.start_date if selected_year else today.replace(month=1, day=1)
        period_end = selected_year.end_date if selected_year else today.replace(month=12, day=31)
        counts = {"total": len(students), "active": len(students.filtered(lambda s: s.active and s.campus_status == "active")),
            "new": len(students.filtered(lambda s: s.campus_admission_date and period_start <= s.campus_admission_date <= period_end)),
            "attention": sum(r["attention"] for r in rows), "running": len(records.filtered(lambda r: r.state == "running")),
            "incomplete": sum(r["type_key"] == "incomplete" for r in enrolment_rows),
            "history": len(records.filtered(lambda r: r.campus_date_to or r.campus_reason)),
            "new_enrolments": len(records.filtered(lambda r: period_start <= r.create_date.date() <= period_end))}
        term = query.casefold().strip()
        result_rows = enrolment_rows if view == "enrolments" else rows
        result_rows = [r for r in result_rows if (not f["status"] or r["status_key"] == f["status"])
            and (not f["attention"] or r.get("attention", False))
            and (view != "enrolments" or (not f["record_type"] or r["type_key"] == f["record_type"]) and (not f["submitted"] or r["recent"]))
            and (not term or term in " ".join(str(v) for v in r.values()).casefold())]
        return {"view": view, "today": str(today), "company": self.env.company.name, "is_demo": self.env.company.campus_demo,
            "filters": {key: f[key] for key in ("year_id", "department_id", "batch_id", "study_year", "status", "attention", "capacity", "section_size", "record_type", "submitted")},
            "year_label": selected_year.name or _("All academic years"), "new_label": _("New this academic year") if selected_year else _("New this calendar year"), "counts": counts, "departments": department_rows,
            "sections": section_rows, "recent": rows[:6], "rows": result_rows if export else result_rows[page * 30:(page + 1) * 30],
            "total_rows": len(result_rows), "has_next": len(result_rows) > (page + 1) * 30,
            "years": [{"id": r.id, "name": r.name} for r in years], "statuses": [{"key": key, "name": value} for key, value in labels.items()] + [{"key": "archived", "name": _("Archived")}],
            "create_enrolment": self.env["op.student.course"].check_access_rights("create", raise_exception=False)}

    @api.model
    def get_record_action(self, kind, record_id=None, create=False):
        self.env["campus.dashboard"]._mvp_filters()
        if kind not in {"student", "enrolment"} or not isinstance(create, bool):
            raise ValidationError(_("Choose a valid student record."))
        model, original = ("op.student", "mvp_students") if kind == "student" else ("op.student.course", "mvp_enrolments")
        source = self.env[model].with_context(active_test=False)
        source.check_access_rights("read")
        if record_id is None and not create:
            raise ValidationError(_("Choose an existing record or create a new enrolment."))
        if create:
            source.check_access_rights("create")
        if record_id is not None:
            if isinstance(record_id, bool) or not isinstance(record_id, int) or not 1 <= record_id <= 2147483647:
                raise ValidationError(_("Choose a valid student record."))
            if not source.search_count([("id", "=", record_id), ("company_id", "=", self.env.company.id)]):
                raise AccessError(_("This record is outside the active college or your access permissions."))
        action = self.env["campus.dashboard"].get_owner_action("ideastone_erp." + original)
        action.update(view_mode="form", views=[(self.env.ref("ideastone_erp.mvp_student_form" if kind == "student" else "ideastone_erp.mvp_enrolments_form").id, "form")])
        action["context"].update(active_test=False, campus_module="students")
        if record_id:
            action["res_id"] = record_id
        return action
