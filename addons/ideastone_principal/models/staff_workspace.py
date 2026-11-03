from collections import defaultdict

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


def principal_access(env):
    if not env.user.has_group("ideastone_principal.group_principal"):
        raise AccessError(_("Principal permission is required to review staff records."))


class PrincipalStaffNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        modules = super()._owner_modules()
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            return modules
        entries = [("Staff directory", "ideastone_principal.action_staff_directory"),
                   ("New staff applications", "ideastone_principal.action_staff_applications")]
        return [(key, label, icon, entries if key == "staff" else items) for key, label, icon, items in modules]

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{
            "ideastone_principal.action_staff_directory": "op.faculty",
            "ideastone_principal.action_staff_applications": "ideastone.principal.staff.application"})


class PrincipalStaffWorkspace(models.AbstractModel):
    _name = "ideastone.principal.staff.workspace"
    _description = "Principal staff directory and recruitment oversight"

    @api.model
    def get_directory(self):
        principal_access(self.env)
        # Only this projected response is elevated: HR's general edit permissions stay unchanged.
        data = self.env["campus.owner.staff.ui"].sudo().with_context(active_test=False).get_directory()
        department_order = {row["key"]: index for index, row in enumerate(data["departments"])}
        company = self.env.company
        faculty = self.env["op.faculty"].sudo().with_context(active_test=False).search([
            ("company_id", "in", [False, company.id])])
        employees = self.env["hr.employee"].sudo().with_context(active_test=False).search([
            ("company_id", "=", company.id), ("id", "not in", faculty.emp_id.ids)], order="name")
        today = fields.Date.context_today(self)
        absent = self.env["hr.leave"].sudo().search([("company_id", "=", company.id),
            ("employee_id", "in", employees.ids), ("state", "=", "validate"),
            ("request_date_from", "<=", today), ("request_date_to", ">=", today)]).employee_id
        for employee in employees:
            department = employee.department_id
            data["rows"].append({"key": f"employee:{employee.id}", "model": "hr.employee", "id": employee.id,
                "name": employee.name, "code": employee.barcode or "—", "category": "non_teaching",
                "department_key": f"hr:{department.id}" if department else "unassigned",
                "department": department.name or _("Unassigned department"), "department_code": "—",
                "designation": employee.job_title or "—", "email": employee.work_email or "—",
                "phone": employee.work_phone or employee.mobile_phone or "—",
                "gender": dict(employee._fields["gender"].selection).get(employee.gender, "—"),
                "birth_date": str(employee.birthday or ""), "joining_date": "", "employment": "—",
                "status": "Inactive" if not employee.active else "On leave" if employee in absent else "Active"})
        departments = defaultdict(list)
        for row in data["rows"]:
            departments[row["department_key"]].append(row)
        data["departments"] = [{"key": key, "name": rows[0]["department"], "code": rows[0]["department_code"],
            "total": len(rows), "teaching": sum(r["category"] == "teaching" for r in rows),
            "non_teaching": sum(r["category"] == "non_teaching" for r in rows)}
            for key, rows in sorted(departments.items(), key=lambda item: (department_order.get(item[0], len(department_order)), item[1][0]["department"]))]
        data["demo"] = company.campus_demo
        return data

    @api.model
    def get_applications(self):
        principal_access(self.env)
        records = self.env["ideastone.principal.staff.application"].search([
            ("company_id", "=", self.env.company.id)], order="create_date desc, id desc")
        return {"today": str(fields.Date.context_today(self)), "company": self.env.company.name,
                "demo": self.env.company.campus_demo, "rows": records.read([
                    "name", "reference", "staff_type", "role", "department_id", "qualification", "experience",
                    "documents", "interview_date", "state", "review", "decision_note", "decided_by_id", "decided_on"])}

    @api.model
    def decide_application(self, record_id, decision, note=""):
        principal_access(self.env)
        if type(record_id) is not int or decision not in ("approved", "rejected") or not isinstance(note, str):
            raise ValidationError(_("Choose an application and a valid recruitment decision."))
        record = self.env["ideastone.principal.staff.application"].search([
            ("id", "=", record_id), ("company_id", "=", self.env.company.id)])
        if not record:
            raise AccessError(_("This application is outside the active college."))
        record._decide(decision, note)
        return True

    @api.model
    def get_payroll(self, year="", month=""):
        # Salary figures stay with the owner, HR and accounts; the Principal reviews staff
        # punctuality through the Attendance module instead.
        raise AccessError(_("Staff payroll is not available in the Principal workspace."))

