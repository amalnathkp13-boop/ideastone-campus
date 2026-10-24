from collections import Counter, defaultdict
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

WORKSPACES = {
    "overview": ("Overview", "op.admission", "mvp_applications"),
    "enquiries": ("Enquiries", "crm.lead", "mvp_enquiries"),
    "applications": ("Applications & review", "op.admission", "mvp_applications"),
    "documents": ("Documents", "campus.admission.document", "mvp_documents"),
    "register": ("Admission register", "op.admission.register", "mvp_intakes"),
}
STAGES = {
    "new": ("New", "new"), "contacted": ("Contacted", "new"), "started": ("Application started", "new"),
    "submitted": ("Ready for review", "ready"), "documents": ("Documents pending", "docs"),
    "review": ("Decision pending", "review"), "approved": ("Offer issued", "new"),
    "rejected": ("Rejected", "rejected"), "waitlisted": ("Waitlisted", "review"), "enrolled": ("Enrolled", "ready"),
}


class AdmissionsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        module = next((m for m in data.get("faculty_modules", []) if m["key"] == "admissions"), None)
        if module and data.get("is_owner_workspace"):
            items = []
            for view, (label, model, original) in WORKSPACES.items():
                if not self.env[model].check_access_rights("read", raise_exception=False):
                    continue
                ref = self.env.ref("ideastone_erp.action_admissions_" + view)
                item = {"label": label, "action": "ideastone_erp.action_admissions_" + view,
                        "action_id": ref.id, "model": model, "group": "Admissions", "allowed": True,
                        "source_action": "ideastone_erp." + original}
                items.append(item)
            module["items"] = items
            # Original navigation entries remain available to source-form workflows.
        return data

    def _mvp_module_for(self, xmlid):
        if xmlid in {"ideastone_erp.action_admissions_" + view for view in WORKSPACES}:
            return "admissions"
        return super()._mvp_module_for(xmlid)


class AdmissionsUI(models.AbstractModel):
    _name = "campus.admissions.ui"
    _description = "College admissions workspace projections"

    def _filters(self, filters):
        f = self.env["campus.dashboard"]._mvp_filters(filters)
        if f["course_id"]:
            course = self.env["op.course"].browse(f["course_id"]).exists()
            course.check_access_rights("read")
            course.check_access_rule("read")
            if not course or course.company_id != self.env.company:
                raise AccessError(_("Choose a programme in the active college."))
        return f

    def _records(self, model, domain):
        return self.env["campus.dashboard"]._mvp_records(model, domain)

    def _domain(self, view, f):
        domain = [("company_id", "=", self.env.company.id)]
        if view == "enquiries":
            domain += [("campus_enquiry", "=", True)]
            paths = ("campus_year_id", "campus_course_id")
        elif view in {"overview", "applications"}:
            domain += [("campus_managed", "=", True)]
            paths = ("campus_year_id", "course_id")
        elif view == "documents":
            domain += [("admission_id.campus_managed", "=", True)]
            paths = ("admission_id.campus_year_id", "admission_id.course_id")
        else:
            paths = ("academic_years_id", "course_id")
        for key, path in zip(("year_id", "course_id"), paths, strict=True):
            if f[key]:
                domain.append((path, "=", f[key]))
        return domain

    @api.model
    def get_workspace(self, view="overview", filters=None, query="", status="", page=0):
        if view not in WORKSPACES:
            raise ValidationError(_("Choose a valid admissions workspace."))
        f = self._filters(filters)
        self.env[WORKSPACES[view][1]].check_access_rights("read")
        if isinstance(page, bool) or not isinstance(page, int) or not 0 <= page <= 2000:
            raise ValidationError(_("Choose a valid page."))
        if not isinstance(query, str) or len(query) > 200 or not isinstance(status, str):
            raise ValidationError(_("Use valid admissions search filters."))
        leads = self._records("crm.lead", self._domain("enquiries", f))
        apps = self._records("op.admission", self._domain("applications", f))
        docs = self._records("campus.admission.document", self._domain("documents", f)).with_context(bin_size=True)
        cycles = self._records("op.admission.register", self._domain("register", f))
        requirements = self._records("campus.admission.requirement", [("company_id", "=", self.env.company.id), ("required", "=", True)])
        today = fields.Date.context_today(self)
        week_start = today - timedelta(days=today.weekday())
        activities = self._records("mail.activity", [("res_model", "=", "crm.lead"), ("res_id", "in", leads.ids)])
        deadlines = defaultdict(list)
        for activity in activities:
            if activity.date_deadline:
                deadlines[activity.res_id].append(activity.date_deadline)
        converted = set(apps.campus_lead_id.ids)
        due_ids = {key for key, dates in deadlines.items() if min(dates) <= today}
        verified = defaultdict(set)
        for doc in docs:
            if doc.state == "verified":
                verified[doc.admission_id.id].add(doc.requirement_id.id)
        application_rows = []
        for app in apps.sorted(lambda r: (r.write_date, r.id), reverse=True):
            checklist = requirements.filtered(lambda r, course=app.course_id: not r.course_id or r.course_id == course)
            placement = bool(app.batch_id and app.campus_year_id and app.batch_id.course_id == app.course_id)
            complete = round((len(set(checklist.ids) & verified[app.id]) + int(placement)) * 100 / (len(checklist) + 1))
            label, tone = STAGES.get(app.campus_stage, (app.campus_stage, "new"))
            if app.campus_stage in {"submitted", "documents"}:
                label, tone = ("Ready for review", "ready") if complete == 100 else ("Documents pending", "docs")
            application_rows.append({"id": app.id, "name": app.name, "reference": app.application_number or str(app.id),
                "programme": app.course_id.name or "—", "submitted": self._local_date(app.application_date), "completeness": complete,
                "stage": app.campus_stage, "status": label, "tone": tone, "owner": app.campus_officer_id.name or _("Unassigned"),
                "updated": self._local_date(app.write_date), "kind": "applications"})
        lead_rows = [{"id": lead.id, "name": lead.contact_name or lead.partner_name or lead.name, "reference": lead.name,
            "programme": lead.campus_course_id.name or "—", "source": lead.source_id.name or _("Not specified"),
            "status": "Converted" if lead.id in converted else "Follow-up due" if lead.id in due_ids else "Contacted" if lead.campus_contacted else "New",
            "tone": "ready" if lead.id in converted or lead.campus_contacted else "review" if lead.id in due_ids else "new",
            "follow_up": str(min(deadlines[lead.id])) if deadlines[lead.id] else _("Not scheduled"),
            "owner": lead.user_id.name or _("Unassigned"), "kind": "enquiries"}
            for lead in leads.sorted(lambda r: (r.create_date, r.id), reverse=True)]
        document_rows = [{"id": doc.id, "name": doc.admission_id.name, "reference": doc.admission_id.application_number or str(doc.admission_id.id),
            "document": doc.name, "uploaded": self._local_date(doc.create_date), "file_status": _("File uploaded") if doc.file else _("No file"),
            "status": {"pending": "Pending", "verified": "Verified", "rejected": "Needs resubmission"}[doc.state],
            "tone": {"pending": "review", "verified": "ready", "rejected": "docs"}[doc.state],
            "owner": doc.verified_by.name or "—", "kind": "documents"} for doc in docs.sorted("create_date", reverse=True)]
        enrolled = apps.filtered(lambda r: r.campus_stage == "enrolled")
        cycle_rows = []
        for cycle in cycles.sorted("start_date", reverse=True):
            confirmed = len(enrolled.filtered(lambda r, intake=cycle: r.register_id == intake))
            is_open = cycle.state != "cancel" and cycle.start_date <= today <= cycle.end_date
            cycle_rows.append({"id": cycle.id, "name": cycle.name, "programme": cycle.course_id.name, "year": cycle.academic_years_id.name or "—",
                "window": f"{cycle.start_date} – {cycle.end_date}", "capacity": cycle.max_count or 0, "confirmed": confirmed,
                "fill": round(confirmed * 100 / cycle.max_count, 1) if cycle.max_count else None,
                "status": "Open" if is_open else "Cancelled" if cycle.state == "cancel" else "Closed / upcoming",
                "tone": "ready" if is_open else "new", "kind": "register"})
        departments = {}
        for cycle in cycles.filtered(lambda r: r.state != "cancel"):
            dept = cycle.course_id.department_id
            row = departments.setdefault(dept.id or 0, {"id": dept.id or 0, "name": dept.name or _("Unassigned department"), "code": dept.code or "—", "capacity": 0, "applications": 0, "confirmed": 0, "waiting": 0})
            row["capacity"] += max(0, cycle.max_count)
        for app in apps:
            dept = app.course_id.department_id
            row = departments.setdefault(dept.id or 0, {"id": dept.id or 0, "name": dept.name or _("Unassigned department"), "code": dept.code or "—", "capacity": 0, "applications": 0, "confirmed": 0, "waiting": 0})
            row["applications"] += 1
            row["confirmed"] += app.campus_stage == "enrolled"
            row["waiting"] += app.campus_stage == "waitlisted"
        for row in departments.values():
            row.update(fill=round(row["confirmed"] * 100 / row["capacity"], 1) if row["capacity"] else None,
                       remaining=max(0, row["capacity"] - row["confirmed"]) if row["capacity"] else None)
        department_cards = sorted(departments.values(), key=lambda r: r["name"])
        if len(department_cards) < 5 and not f["course_id"]:
            # Complete the snapshot row using actual college departments, without inventing intake data.
            for dept in self._records("op.department", [("company_id", "=", self.env.company.id), ("id", "not in", list(departments))]).sorted("id"):
                department_cards.append({"id": dept.id, "name": dept.name, "code": dept.code or "—", "capacity": 0,
                                         "confirmed": 0, "fill": None, "remaining": None, "no_intake": True})
                if len(department_cards) == 5:
                    break
        capacity = sum(r["capacity"] for r in departments.values())
        review = [r for r in application_rows if r["stage"] in {"submitted", "documents", "review"}]
        ready = [r for r in review if r["status"] == "Ready for review"]
        counts = {"enquiries": len(leads), "contacted": len(leads.filtered("campus_contacted")), "follow_up": len(due_ids - converted),
            "applications": len(apps), "review": len(review), "ready": len(ready), "enrolled": len(enrolled), "offers": len(apps.filtered(lambda r: r.campus_stage == "approved")),
            "documents": len(docs), "pending_documents": len(docs.filtered(lambda r: r.state == "pending")),
            "verified_week": len(docs.filtered(lambda r: r.state == "verified" and r.verified_on and r.verified_on.date() >= week_start)),
            "capacity": capacity, "cycles": sum(r["status"] == "Open" for r in cycle_rows), "waiting": len(apps.filtered(lambda r: r.campus_stage == "waitlisted"))}
        summary = {"enquiries": [("All enquiries", counts["enquiries"]), ("Follow-up due", counts["follow_up"]), ("Contacted enquiries", counts["contacted"])],
            "applications": [("Managed applications", counts["applications"]), ("Awaiting decision", counts["review"]), ("Ready for review", counts["ready"])],
            "documents": [("Documents submitted", counts["documents"]), ("Awaiting verification", counts["pending_documents"]), ("Verified this week", counts["verified_week"])],
            "register": [("Active admission cycles", counts["cycles"]), ("Configured seat capacity", capacity), ("Seats confirmed", counts["enrolled"])]}
        rows = {"overview": review[:6], "enquiries": lead_rows, "applications": application_rows, "documents": document_rows, "register": cycle_rows}[view]
        options = sorted({r["status"] for r in rows})
        term = query.casefold().strip()
        rows = [r for r in rows if (not status or r["status"] == status) and (not term or term in " ".join(str(v) for v in r.values()).casefold())]
        sources = Counter(lead.source_id.name or _("Not specified") for lead in leads)
        pipeline = [{"label": label, "count": sum(r["stage"] in stages for r in application_rows),
                     "rows": [r for r in application_rows if r["stage"] in stages][:2]}
                    for label, stages in [("New", {"new", "contacted", "started"}), ("In review", {"submitted", "documents", "review", "waitlisted"}), ("Offer", {"approved"}), ("Enrolled", {"enrolled"})]]
        allowed = {key: self.env[model].check_access_rights("read", raise_exception=False) for key, (_label, model, _original) in WORKSPACES.items()}
        create = {key: self.env[model].check_access_rights("create", raise_exception=False) for key, (_label, model, _original) in WORKSPACES.items()}
        return {"view": view, "company": self.env.company.name, "is_demo": self.env.company.campus_demo, "today": str(today), "counts": counts, "summary": summary.get(view, []),
            "conversion": round(len(enrolled) * 100 / len(apps), 1) if apps else None, "fill": round(len(enrolled) * 100 / capacity, 1) if capacity else None,
            "departments": sorted(departments.values(), key=lambda r: r["name"]), "department_cards": department_cards, "pipeline": pipeline,
            "journey": [{"label": label, "count": count, "tone": tone} for label, count, tone in [("Enquiries", len(leads), "blue"), ("Contacted leads", counts["contacted"], "blue"), ("Applications", len(apps), "purple"), ("Offer issued", counts["offers"], "purple"), ("Enrolled", len(enrolled), "green")]],
            "sources": [{"name": name, "count": count} for name, count in sources.most_common()], "rows": rows[page * 30:(page + 1) * 30], "total_rows": len(rows), "has_next": len(rows) > (page + 1) * 30,
            "statuses": options, "allowed": allowed, "create": create,
            "years": [{"id": r.id, "name": r.name} for r in self._records("op.academic.year", [("company_id", "=", self.env.company.id)])],
            "programmes": [{"id": r.id, "name": r.name} for r in self._records("op.course", [("company_id", "=", self.env.company.id)])]}

    def _local_date(self, value):
        return fields.Datetime.context_timestamp(self, value).strftime("%d %b %Y") if value else "—"

    @api.model
    def get_action(self, kind, record_id=None, create=False, filters=None):
        f = self._filters(filters)
        if kind not in WORKSPACES or kind == "overview":
            raise ValidationError(_("Choose a valid admissions register."))
        _label, model, original = WORKSPACES[kind]
        source = self.env[model]
        source.check_access_rights("read")
        action = self.env["campus.dashboard"].get_owner_action("ideastone_erp." + original)
        action["domain"] = self._domain(kind, f)
        action["context"].update(campus_module="admissions", default_company_id=self.env.company.id)
        if kind == "enquiries":
            action["context"].update(default_campus_year_id=f["year_id"] or False, default_campus_course_id=f["course_id"] or False)
        elif kind in {"applications", "register"} and f["course_id"]:
            action["context"]["default_course_id"] = f["course_id"]
        if create:
            source.check_access_rights("create")
        if record_id is not None:
            if isinstance(record_id, bool) or not isinstance(record_id, int) or not 1 <= record_id <= 2147483647:
                raise ValidationError(_("Choose a valid record."))
            if not source.search_count(action["domain"] + [("id", "=", record_id)]):
                raise AccessError(_("This record is outside the selected college or admissions scope."))
            action["res_id"] = record_id
        if create or record_id:
            action["views"] = [(view_id, mode) for view_id, mode in action.get("views", []) if mode == "form"] or [(False, "form")]
            action["view_mode"] = "form"
        return action
