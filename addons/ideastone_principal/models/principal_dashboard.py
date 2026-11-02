from odoo.exceptions import AccessError

from odoo import _, api, fields, models


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
                       "ideastone_principal.action_principal_notices_workspace": "ideastone.principal.notice"})

    def _owner_modules(self):
        modules = super()._owner_modules()
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            return modules
        selected = {"admissions", "students", "academics", "staff", "attendance",
                    "exams", "fees", "learning", "calendar", "communication", "reports"}
        modules = [(key, label, icon, entries) for key, label, icon, entries in modules if key in selected]
        return [
            ("home", "Principal overview", "home", [("Overview", "ideastone_principal.action_principal_overview")]),
            ("decisions", "Decisions", "check-square-o", [
                ("Pending decisions", "ideastone_principal.action_principal_decisions"),
                ("Student leave approvals", "ideastone_erp.action_student_leave")]),
            *modules,
            ("principal_notices", "Principal notices", "bullhorn", [("Notices & circulars", "ideastone_principal.action_principal_notices_workspace")]),
        ]

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self.env.user.has_group("ideastone_principal.group_principal"):
            data.update(is_principal_workspace=True, workspace_role="Principal", is_admin=False)
        return data
