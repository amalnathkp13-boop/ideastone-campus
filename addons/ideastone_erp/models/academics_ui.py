from collections import Counter
from datetime import timedelta
from math import isfinite

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

VIEWS = {
    "overview": ("Overview", "op.course", None),
    "years": ("Academic years", "op.academic.year", "mvp_years"),
    "departments": ("Departments", "op.department", "mvp_departments"),
    "programmes": ("Programmes", "op.course", "mvp_programmes"),
    "semesters": ("Semesters", "op.academic.term", "mvp_terms"),
    "sections": ("Sections", "op.batch", "mvp_sections"),
    "curriculum": ("Subjects & curriculum", "op.subject", "mvp_subjects"),
}
EDITABLE = {
    "years": ("name", "code", "start_date", "end_date", "campus_current", "term_structure", "active"),
    "departments": ("name", "code", "campus_academic_area", "active"),
    "programmes": ("name", "code", "department_id", "campus_level", "campus_duration", "campus_award", "active"),
    "semesters": ("name", "academic_year_id", "campus_course_id", "campus_sequence", "term_start_date", "term_end_date"),
    "sections": ("name", "code", "course_id", "campus_year_id", "campus_term_id", "start_date", "end_date", "active"),
    "curriculum": ("name", "code", "department_id", "campus_term_id", "campus_credits", "type", "subject_type", "active"),
}


class AcademicDepartment(models.Model):
    _inherit = "op.department"

    campus_academic_area = fields.Selection([
        ("engineering", "Engineering & technology"), ("science", "Science & humanities"),
        ("management", "Business & management"), ("health", "Health sciences"), ("other", "Other"),
    ], string="Academic area")


class AcademicProgramme(models.Model):
    _inherit = "op.course"

    campus_level = fields.Selection([
        ("undergraduate", "Undergraduate"), ("postgraduate", "Postgraduate"), ("diploma", "Diploma / other"),
    ], string="Programme level")


class AcademicsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        return [(key, label, icon, [(title, "action_academics_" + view) for view, (title, _model, _source) in VIEWS.items()])
                if key == "academics" else (key, label, icon, entries)
                for key, label, icon, entries in super()._owner_modules()]

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{"action_academics_" + key: value[1] for key, value in VIEWS.items()})

    @api.model
    def get_overview(self):
        data = super().get_overview()
        for module in data.get("faculty_modules", []):
            if module["key"] == "academics" and data.get("is_owner_workspace"):
                for item in module["items"]:
                    view = item["action"].removeprefix("ideastone_erp.action_academics_")
                    if VIEWS[view][2]:
                        item["source_action"] = "ideastone_erp." + VIEWS[view][2]
        return data


class AcademicsUI(models.AbstractModel):
    _name = "campus.academics.ui"
    _description = "Academic administration workspace"

    def _check_workspace(self):
        if not self.env["campus.dashboard"]._is_mvp_user():
            raise AccessError(_("College academic workspace permission is required."))
        self.env["op.course"].check_access_rights("read")

    def _records(self, model, domain=None):
        return self.env["campus.dashboard"].with_context(active_test=False)._mvp_records(
            model, [("company_id", "=", self.env.company.id)] + (domain or []), limit=10000)

    def _values(self, view, record):
        return {key: record[key].id if record._fields[key].type == "many2one" else
                str(record[key]) if record._fields[key].type == "date" and record[key] else record[key]
                for key in EDITABLE[view]}

    def _row(self, view, record):
        return {"id": record.id, "name": record.name, "values": self._values(view, record)}

    @api.model
    def get_workspace(self):
        self._check_workspace()
        today = fields.Date.context_today(self)
        years = self._records("op.academic.year").sorted("start_date", reverse=True)
        current = years.filtered(lambda r: r.active and r.campus_current)[:1]
        year_id = current.id
        departments = self._records("op.department").sorted("name")
        programmes = self._records("op.course").sorted("name")
        terms = self._records("op.academic.term").sorted("term_start_date", reverse=True)
        sections = self._records("op.batch").sorted("name")
        subjects = self._records("op.subject").sorted("name")
        current_sections = sections.filtered(lambda r: r.active and r.campus_year_id.id == year_id) if current else sections.browse()
        enrolments = self._records("op.student.course", [("state", "=", "running"), ("academic_years_id", "=", year_id)]) if current else self.env["op.student.course"]
        faculty = self._records("op.faculty", [("active", "=", True)])
        intakes = self._records("op.admission.register", [("academic_years_id", "=", year_id)]) if current else self.env["op.admission.register"]
        plans = self._records("campus.teaching.plan", [("term_id.academic_year_id", "=", year_id), ("review_state", "!=", "rejected")]) if current else self.env["campus.teaching.plan"]
        sessions = self._records("op.session", [("batch_id.campus_year_id", "=", year_id), ("state", "!=", "cancel")]) if current else self.env["op.session"]
        exams = self._records("op.exam", [("campus_year_id", "=", year_id), ("state", "!=", "cancel")]) if current else self.env["op.exam"]
        rows = {key: [] for key in EDITABLE}
        for year in years:
            status = "archived" if not year.active else "current" if year.campus_current else "upcoming" if year.start_date > today else "completed" if year.end_date < today else "recorded"
            rows["years"].append(dict(self._row("years", year), start=str(year.start_date), end=str(year.end_date), status=status,
                progress=round(max(0, min(1, (today - year.start_date).days / max(1, (year.end_date - year.start_date).days))) * 100),
                duration=max(1, round((year.end_date - year.start_date).days / 30.44))))
        section_counts = Counter(e.batch_id.id for e in enrolments)
        for dept in departments:
            courses = programmes.filtered(lambda r, dept=dept: r.department_id == dept)
            cohorts = current_sections.filtered(lambda r, courses=courses: r.course_id in courses)
            students = enrolments.filtered(lambda r, courses=courses: r.course_id in courses).student_id
            capacity = sum(intakes.filtered(lambda r, courses=courses: r.course_id in courses).mapped("max_count"))
            rows["departments"].append(dict(self._row("departments", dept), code=dept.code or "—", area=dept.campus_academic_area or "",
                active=dept.active, students=len(students), capacity=capacity, fill=round(len(students) * 100 / capacity) if capacity else None,
                sections=len(cohorts), faculty=len(faculty.filtered(lambda r, dept=dept: r.main_department_id == dept)),
                section_rows=[{"id": s.id, "name": s.name, "students": section_counts[s.id]} for s in cohorts]))
        levels = dict(self.env["op.course"]._fields["campus_level"].selection)
        for course in programmes:
            rows["programmes"].append(dict(self._row("programmes", course), code=course.code, department=course.department_id.name or _("Not specified"),
                department_id=course.department_id.id, level=course.campus_level or "", level_label=levels.get(course.campus_level, _("Not specified")),
                duration=course.campus_duration, active=course.active))
        for term in terms:
            status = "upcoming" if term.term_start_date > today else "completed" if term.term_end_date < today else "current"
            rows["semesters"].append(dict(self._row("semesters", term), year=term.academic_year_id.name, year_id=term.academic_year_id.id,
                programme=term.campus_course_id.name or _("Not specified"), programme_id=term.campus_course_id.id,
                sequence=term.campus_sequence, start=str(term.term_start_date), end=str(term.term_end_date), status=status,
                period_type="quarter" if term.parent_term else "semester"))
        for section in sections:
            rows["sections"].append(dict(self._row("sections", section), code=section.code, programme=section.course_id.name,
                programme_id=section.course_id.id, area=section.course_id.department_id.campus_academic_area or "",
                year=section.campus_year_id.name or _("Not specified"), year_id=section.campus_year_id.id,
                semester=section.campus_term_id.name or _("Not specified"), active=section.active,
                mapped=bool(section.campus_year_id and section.campus_term_id), students=section_counts[section.id]))
        for subject in subjects:
            rows["curriculum"].append(dict(self._row("curriculum", subject), code=subject.code, department=subject.department_id.name or _("Not specified"),
                department_id=subject.department_id.id, semester=subject.campus_term_id.name or _("Not specified"),
                mapped=bool(subject.campus_term_id), credits=subject.campus_credits, active=subject.active))
        active_subjects = subjects.filtered("active")
        active_programmes = programmes.filtered("active")
        missing_credits = len(active_subjects.filtered(lambda r: r.campus_credits <= 0))
        missing_subjects = len(active_subjects.filtered(lambda r: not r.campus_term_id))
        missing_sections = len(sections.filtered(lambda r: r.active and (not r.campus_year_id or not r.campus_term_id)))
        missing_terms = len(terms.filtered(lambda r: not r.campus_course_id))
        due = plans.filtered(lambda r: r.planned_date <= today)
        planned_hours = sum(due.mapped("planned_hours"))
        delivered = sum(min(r.actual_hours, r.planned_hours) for r in due if r.execution_date and r.execution_date <= today)
        coverage = round(delivered * 100 / planned_hours, 1) if planned_hours else None
        checks = missing_credits + missing_subjects + missing_sections + missing_terms
        def percent(count, total):
            return round(count * 100 / total) if total else None
        mapped_subjects = set(active_programmes.subject_ids.ids)
        readiness = [
            {"name": "Subject mapping", "percent": percent(sum(s.id in mapped_subjects for s in active_subjects), len(active_subjects)), "note": _("Subjects linked to active programmes")},
            {"name": "Lesson plans", "percent": percent(len(plans.filtered(lambda r: r.review_state == "approved")), len(plans)), "note": _("Approved plans / saved plans in the current year")},
            {"name": "Assessment plans", "percent": percent(len(current_sections.filtered(lambda r: bool(r.campus_exam_ids))), len(current_sections)), "note": _("Current sections with scheduled examination records")},
            {"name": "Section allocation", "percent": percent(len(sections.filtered(lambda r: r.active and r.campus_year_id and r.campus_term_id)), len(sections.filtered("active"))), "note": _("Active sections with year and semester mappings")},
        ]
        trend = []
        if current:
            month = current.start_date.replace(day=1)
            for _index in range(12):
                if month > min(today, current.end_date):
                    break
                next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
                end = min(next_month - timedelta(days=1), today, current.end_date)
                due_plans = plans.filtered(lambda r, end=end: r.planned_date <= end)
                target = sum(due_plans.mapped("planned_hours"))
                actual = sum(min(r.actual_hours, r.planned_hours) for r in plans if r.execution_date and r.execution_date <= end)
                scheduled = sessions.filtered(lambda r, end=end: r.start_datetime.date() <= end)
                trend.append({"month": month.strftime("%b"), "progress": percent(actual, sum(plans.mapped("planned_hours"))),
                    "target": percent(target, sum(plans.mapped("planned_hours"))), "classes": len(scheduled.filtered(lambda r: r.state == "done")), "scheduled": len(scheduled)})
                month = next_month
        milestones = []
        for term in terms:
            for value, label in ((term.term_start_date, _("Starts")), (term.term_end_date, _("Ends"))):
                if today <= value <= today + timedelta(days=30):
                    milestones.append({"name": term.name, "date": str(value), "detail": term.academic_year_id.name, "status": label})
        for exam in exams:
            when = fields.Datetime.context_timestamp(self, exam.start_time).date()
            if today <= when <= today + timedelta(days=30):
                milestones.append({"name": exam.name, "date": str(when), "detail": exam.course_id.name, "status": _("Scheduled")})
        return {"today": str(today), "company": self.env.company.name, "is_demo": self.env.company.campus_demo,
            "rows": rows, "current": next((r for r in rows["years"] if r["id"] == year_id), None),
            "counts": {"programmes": len(active_programmes), "coverage": coverage, "sections": len(current_sections), "checks": checks,
                "students": len(enrolments.student_id), "missing_credits": missing_credits, "missing_subjects": missing_subjects,
                "missing_sections": missing_sections, "missing_terms": missing_terms},
            "readiness": readiness, "trend": trend, "milestones": sorted(milestones, key=lambda r: r["date"])[:12],
            "distribution": dict(Counter(s.department_id.name or _("Not specified") for s in active_subjects)),
            "can_edit": self.env.user.has_group("ideastone_erp.group_mvp_registrar"),
            "create": {key: self.env[VIEWS[key][1]].check_access_rights("create", raise_exception=False) for key in EDITABLE}}

    @api.model
    def save_record(self, view, values, record_id=False):
        self._check_workspace()
        if not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            raise AccessError(_("Academic records may be changed by the college registrar."))
        if not isinstance(view, str) or view not in EDITABLE or not isinstance(values, dict) or set(values) - set(EDITABLE[view]):
            raise ValidationError(_("Use the academic form's supported fields."))
        if record_id is not False and (type(record_id) is not int or not 0 < record_id <= 2147483647):
            raise ValidationError(_("Choose a valid academic record."))
        model = self.env[VIEWS[view][1]]
        model.check_access_rights("write" if record_id else "create")
        record = model.browse(record_id).exists() if record_id else model
        if record_id:
            record.check_access_rule("write")
            if not record or record.company_id != self.env.company:
                raise AccessError(_("Choose a record in the active college."))
        vals = dict(values)
        for key, value in vals.items():
            field = model._fields[key]
            if field.type == "many2one":
                if value is False or value is None:
                    vals[key] = False
                elif type(value) is not int or not 0 < value <= 2147483647:
                    raise ValidationError(_("Choose a valid linked academic record."))
                else:
                    related = self.env[field.comodel_name].browse(value).exists()
                    related.check_access_rights("read")
                    related.check_access_rule("read")
                    if not related or related.company_id != self.env.company:
                        raise AccessError(_("Linked records must belong to the active college."))
            elif field.type in {"integer", "float"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0 or (field.type == "integer" and (int(value) != value or value > 100)):
                    raise ValidationError(_("Enter valid positive academic values."))
            elif field.type == "boolean" and not isinstance(value, bool):
                raise ValidationError(_("Use a valid academic status."))
            elif field.type == "char":
                if value is False:
                    value = ""
                if not isinstance(value, str) or len(value) > (field.size or 256):
                    raise ValidationError(_("Enter text within the field's length limit."))
                vals[key] = value.strip()
            elif field.type == "selection":
                if not isinstance(value, (str, bool)) or value not in {False, *dict(field._description_selection(self.env))}:
                    raise ValidationError(_("Choose a valid academic option."))
            elif field.type == "date":
                try:
                    vals[key] = fields.Date.to_date(value) if isinstance(value, str) and len(value) == 10 else False
                except (TypeError, ValueError) as exc:
                    raise ValidationError(_("Enter a valid academic date.")) from exc
        for key in ("name", "code"):
            if key in EDITABLE[view] and not vals.get(key, record[key] if record else ""):
                raise ValidationError(_("Name and code are required."))
        if view == "semesters":
            programme = model.new(dict({k: record[k].id for k in ("campus_course_id", "academic_year_id")} if record else {}, **vals)).campus_course_id
            if programme and vals.get("campus_sequence", record.campus_sequence if record else 1) > programme.campus_duration:
                raise ValidationError(_("Semester number exceeds the programme duration."))
        if view == "years" and vals.get("campus_current"):
            model.flush_model(["campus_current", "active"])
            self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [self.env.company.id])
            model.invalidate_model(["campus_current"])
            previous = model.search([("company_id", "=", self.env.company.id), ("campus_current", "=", True), ("id", "!=", record.id or 0)])
            previous.write({"campus_current": False})
            previous.flush_recordset(["campus_current"])
        if record:
            record.write(vals)
        else:
            record = model.create(dict(vals, company_id=self.env.company.id))
        return record.id
