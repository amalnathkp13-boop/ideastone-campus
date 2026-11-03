from odoo.exceptions import AccessError

from odoo import _, api, fields, models

PRINCIPAL_FOCUS = {
    "admissions": ("Admissions oversight", {"Overview", "Applications & review", "Admission register"}),
    "students": ("Student affairs", {"Student directory", "Enrolments & transfers"}),
    "academics": ("Academic planning", {"Overview", "Departments", "Programmes", "Subjects & curriculum"}),
    "staff": ("Faculty oversight", {"Staff directory", "New staff applications", "Teaching allocation", "Faculty development and appraisal", "Leave Management"}),
    "attendance": ("Attendance oversight", {"Staff attendance", "Attendance register", "Student summary & shortage"}),
    "exams": ("Examination oversight", {"Overview", "Exam sessions", "Results & missing entries", "Question papers"}),
    "fees": ("Finance oversight", {"Financial overview", "Invoices & dues", "Overdue follow-up"}),
    "learning": ("Learning oversight", {"Assignments", "Review submissions"}),
    "calendar": ("Calendar", {"College calendar"}),
    "reports": ("Institutional reports", {"Admissions", "Students", "Attendance", "Fee collection", "Outstanding dues", "Results", "Faculty workload"}),
}


class PrincipalFinance(models.AbstractModel):
    _inherit = "campus.owner.fees"

    @api.model
    def get_workspace(self, year_id=0):
        data = super().get_workspace(year_id)
        if self.env.user.has_group("ideastone_principal.group_principal"):
            data.update(currency="INR", symbol="₹")
        return data


class PrincipalDashboard(models.AbstractModel):
    _name = "ideastone.principal.dashboard"
    _description = "Principal Dashboard Data"

    @api.model
    def get_overview(self):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            raise AccessError(_("Only a principal can view campus oversight data."))
        company = self.env.company
        counts = {}
        for key, model, domain in [
            ("students", "op.student", [("active", "=", True)]),
            ("faculty", "op.faculty", [("active", "=", True)]),
            ("applications", "op.admission", []),
            ("pending", "ideastone.principal.request", [("state", "=", "submitted")]),
            ("exams", "op.exam", []),
            ("notices", "ideastone.principal.notice", [("state", "=", "published")]),
        ]:
            source = self.env[model]
            if not source.check_access_rights("read", raise_exception=False):
                counts[key] = 0
                continue
            if "company_id" in source._fields:
                domain += [("company_id", "=", company.id)]
            counts[key] = source.search_count(domain)
        requests = self.env["ideastone.principal.request"].search(
            [("company_id", "=", company.id), ("state", "=", "submitted")],
            order="due_date, create_date", limit=8)
        notices = self.env["ideastone.principal.notice"].search(
            [("company_id", "=", company.id)], order="create_date desc", limit=8)
        leave = self.env["campus.student.leave"].search(
            [("company_id", "=", company.id), ("principal_id", "=", self.env.uid),
             ("state", "=", "principal")], order="create_date desc", limit=8)
        counts["student_leave"] = self.env["campus.student.leave"].search_count(
            [("company_id", "=", company.id), ("principal_id", "=", self.env.uid),
             ("state", "=", "principal")])
        return {
            "company": company.name, "user": self.env.user.name,
            "today": str(fields.Date.context_today(self)), "counts": counts,
            "requests": [{"id": row.id, "name": row.name, "type": dict(row._fields["request_type"].selection).get(row.request_type),
                          "requester": row.requester_id.name, "due": str(row.due_date or ""), "state": row.state}
                         for row in requests],
            "student_leave": [{"id": row.id, "student": row.student_id.name, "reason": row.reason or "",
                               "from": str(row.date or ""), "to": str(row.deadline or "")}
                              for row in leave],
            "notices": [{"id": row.id, "name": row.name, "audience": dict(row._fields["audience"].selection).get(row.audience),
                         "state": row.state, "date": str(row.published_on or row.create_date or "")[:10]}
                        for row in notices],
        }


class PrincipalNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _is_mvp_user(self):
        return super()._is_mvp_user() or self.env.user.has_group("ideastone_principal.group_principal")

    def _client_action_models(self):
        return dict(super()._client_action_models(),
                    **{"ideastone_principal.action_principal_overview": "ideastone.principal.request",
                       "ideastone_principal.action_principal_decisions": "ideastone.principal.request",
                       "ideastone_principal.action_principal_staff_leave": "ideastone.principal.request",
                       "ideastone_principal.action_principal_student_leave": "ideastone.principal.request",
                       "ideastone_principal.action_principal_events": "ideastone.principal.request",
                       "ideastone_principal.action_principal_notices_workspace": "ideastone.principal.notice"})

    def _owner_modules(self):
        modules = super()._owner_modules()
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            return modules
        modules = [
            (key, PRINCIPAL_FOCUS[key][0], icon,
             ([("Overview", "action_admissions_overview")] if key == "admissions" else [])
             + [(title, action) for title, action in entries if title in PRINCIPAL_FOCUS[key][1]])
            for key, _label, icon, entries in modules if key in PRINCIPAL_FOCUS
        ]
        return [
            ("home", "Principal overview", "home", [("Overview", "ideastone_principal.action_principal_overview")]),
            ("decisions", "Decisions", "check-square-o", [
                ("Pending decisions", "ideastone_principal.action_principal_decisions"),
                ("Staff leave approvals", "ideastone_principal.action_principal_staff_leave"),
                ("Student leave approvals", "ideastone_principal.action_principal_student_leave"),
                ("Event management", "ideastone_principal.action_principal_events")]),
            *modules,
            ("principal_notices", "Principal notices", "bullhorn", [("Notices & circulars", "ideastone_principal.action_principal_notices_workspace")]),
        ]

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self.env.user.has_group("ideastone_principal.group_principal"):
            for module in data["faculty_modules"]:
                if module["key"] in PRINCIPAL_FOCUS:
                    module["items"] = [item for item in module["items"]
                                       if item["label"] in PRINCIPAL_FOCUS[module["key"]][1]]
                for item in module["items"]:
                    item["group"] = module["label"]
            data["faculty_modules"] = [module for module in data["faculty_modules"]
                                       if module["items"] and module["key"] in {*PRINCIPAL_FOCUS, "home", "decisions", "principal_notices"}]
            data["navigation"] = [item for module in data["faculty_modules"] for item in module["items"]]
            data.update(is_principal_workspace=True, workspace_role="Principal", is_admin=False)
        return data
