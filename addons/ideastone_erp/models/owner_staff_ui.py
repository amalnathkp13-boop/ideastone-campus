from collections import defaultdict

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

STAFF_VIEWS = [
    ("Staff directory", "action_owner_staff_directory", "op.faculty"),
    ("Leave Management", "action_owner_staff_leave", "hr.leave"),
    ("Payroll History", "action_owner_staff_payroll", "campus.payslip"),
    ("OD Staffs", "action_owner_staff_od", "hr.leave"),
]


class OwnerStaffNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            return super()._owner_modules()
        tabs = [("Staff directory", "action_owner_staff_directory"),
                ("Leave Management", "action_owner_staff_leave"),
                ("Payroll History", "action_owner_staff_payroll"),
                ("Staff Profile", "action_staff_profile"),
                ("OD Management", "action_staff_od_management"),
                ("OD Staffs", "action_owner_staff_od")]
        return [(key, title, icon, tabs if key == "staff" else entries)
                for key, title, icon, entries in super()._owner_modules()]

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{action: model for _label, action, model in STAFF_VIEWS})

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if data.get("is_owner_workspace"):
            for module in data.get("faculty_modules", []):
                if module["key"] == "staff":
                    for item in module["items"]:
                        if item.get("action") == "ideastone_erp.action_owner_staff_directory":
                            item["source_action"] = "ideastone_erp.mvp_faculty"
        return data

    def _mvp_module_for(self, xmlid):
        if xmlid == "ideastone_erp.mvp_faculty":
            return "staff"
        return super()._mvp_module_for(xmlid)


class OwnerStaffUI(models.AbstractModel):
    _name = "campus.owner.staff.ui"
    _description = "Owner staff directory and leave review"

    def _check_owner(self):
        if not self.env.user.has_group("base.group_user") or not self.env["campus.dashboard"]._is_mvp_user():
            raise AccessError(_("College workspace permission is required."))

    @api.model
    def get_directory(self):
        self._check_owner()
        faculty_model = self.env["op.faculty"]
        faculty_model.check_access_rights("read")
        company_domain = [("company_id", "in", [False, self.env.company.id])]
        faculties = faculty_model.search(company_domain + ["|", ("main_department_id", "=", False),
            ("main_department_id.company_id", "in", [False, self.env.company.id])], order="name, id")
        employees = self.env["hr.employee"].with_context(active_test=False)
        employees = employees.search(company_domain, order="name, id") if employees.check_access_rights("read", raise_exception=False) else employees.browse()
        employee_map = {employee.id: employee for employee in employees}
        today = fields.Date.context_today(self)
        leave_model = self.env["hr.leave"]
        on_leave = set()
        if leave_model.check_access_rights("read", raise_exception=False):
            on_leave = set(leave_model.search([("employee_id", "in", employees.ids),
                ("company_id", "=", self.env.company.id), ("state", "=", "validate"),
                ("request_date_from", "<=", today), ("request_date_to", ">=", today)]).employee_id.ids)
        rows = []
        service_labels = dict(faculty_model._fields["campus_service_type"].selection)
        for faculty in faculties:
            employee = employee_map.get(faculty.emp_id.id)
            department = faculty.main_department_id
            rows.append({"key": f"faculty:{faculty.id}", "model": "op.faculty", "id": faculty.id,
                "name": faculty.name or "—", "code": faculty.campus_staff_code or faculty.id_number or "—",
                "category": "teaching" if faculty.campus_category in (False, "teaching") else "non_teaching",
                "department_key": f"academic:{department.id}" if department else "unassigned",
                "department": department.name or _("Unassigned department"), "department_code": department.code or "—",
                "designation": faculty.campus_designation or (employee.job_title if employee else False) or "—",
                "email": faculty.email or "—", "phone": faculty.phone or faculty.mobile or "—",
                "gender": dict(faculty._fields["gender"].selection).get(faculty.gender, "—"),
                "birth_date": str(faculty.birth_date or ""), "joining_date": str(faculty.campus_joining_date or ""),
                "employment": service_labels.get(faculty.campus_service_type, "—"),
                "status": "Inactive" if not faculty.active else "On leave" if employee and employee.id in on_leave else "Active"})
        departments = defaultdict(list)
        for row in rows:
            departments[row["department_key"]].append(row)
        return {"today": str(today), "company": self.env.company.name, "rows": rows,
            "departments": [{"key": key, "name": items[0]["department"], "code": items[0]["department_code"],
                "total": len(items), "teaching": sum(item["category"] == "teaching" for item in items),
                "non_teaching": sum(item["category"] == "non_teaching" for item in items)}
                for key, items in sorted(departments.items(), key=lambda entry: (entry[0] == "unassigned", int(entry[0].partition(":")[2] or 0)))]}

    @api.model
    def get_leave_queue(self):
        self._check_owner()
        leaves = self.env["hr.leave"].search([("company_id", "=", self.env.company.id),
            ("state", "in", ["confirm", "validate1"])], order="request_date_from, id")
        return [{"id": leave.id, "name": leave.employee_id.name, "type": leave.holiday_status_id.name,
            "from": str(leave.request_date_from), "to": str(leave.request_date_to),
            "days": leave.number_of_days_display, "reason": leave.name or "—",
            "status": "Second approval" if leave.state == "validate1" else "Pending",
            "can_approve": leave.can_approve} for leave in leaves]

    @api.model
    def get_profile(self, faculty_id):
        self._check_owner()
        if type(faculty_id) is not int or faculty_id <= 0:
            raise ValidationError(_("Choose a valid staff member."))
        faculty = self.env["op.faculty"].search([("id", "=", faculty_id),
            ("company_id", "in", [False, self.env.company.id])], limit=1)
        if not faculty or (faculty.main_department_id.company_id and
                           faculty.main_department_id.company_id != self.env.company):
            raise AccessError(_("This staff member is outside your college."))
        detail_model = self.env["campus.faculty.detail"]
        details = detail_model.search([("faculty_id", "=", faculty.id),
            ("company_id", "=", self.env.company.id)], order="kind, date_from desc, id desc") \
            if detail_model.check_access_rights("read", raise_exception=False) else detail_model.browse()
        kind_labels = dict(details._fields["kind"].selection)
        return {"fields": [
            {"title": "Employment details", "items": [["Reporting to", faculty.campus_reporting_id.name or "—"],
                ["Work location", faculty.campus_work_location or "—"],
                ["Registration reference", faculty.campus_registration_reference or "—"],
                ["Profile review date", str(faculty.campus_profile_review_date or "—")]]},
            {"title": "Contact & background", "items": [["Mobile", faculty.mobile or "—"],
                ["Alternate email", faculty.campus_alternate_email or "—"],
                ["Alternate mobile", faculty.campus_alternate_mobile or "—"],
                ["Emergency phone", faculty.campus_emergency_phone or "—"],
                ["Communication address", faculty.campus_communication_address or "—"],
                ["Previous education", faculty.campus_previous_education or "—"]]},
        ], "records": [{"kind": kind_labels.get(row.kind, row.kind), "name": row.name or "—",
            "detail": " · ".join(str(value) for value in (row.specialization, row.institution, row.year,
                row.designation, row.nature) if value),
            "status": dict(row._fields["verification"].selection).get(row.verification, "—")}
            for row in details]}

    @api.model
    def get_od_staff(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            raise AccessError(_("Owner access is required for staff On Duty records."))
        today = fields.Date.context_today(self)
        leaves = self.env["hr.leave"].search([("company_id", "=", self.env.company.id)],
            order="request_date_from desc, id desc")
        leaves = leaves.filtered(lambda row: "".join(c for c in row.holiday_status_id.name.lower() if c.isalpha())
            in {"od", "onduty", "officialduty"})
        state_labels = {"draft": "Draft", "confirm": "Pending", "validate1": "Second approval",
            "validate": "Approved", "refuse": "Refused", "cancel": "Cancelled"}
        rows = [{"id": row.id, "name": row.employee_id.name or "—",
            "department": row.employee_id.department_id.name or "—",
            "from": str(row.request_date_from or ""), "to": str(row.request_date_to or ""),
            "days": row.number_of_days_display, "reason": row.name or "—",
            "state": row.state, "status": state_labels.get(row.state, row.state.title())}
            for row in leaves]
        return {"today": str(today), "rows": rows,
            "active": sum(row["state"] == "validate" and row["from"] <= str(today) <= row["to"] for row in rows),
            "pending": sum(row["state"] in {"confirm", "validate1"} for row in rows),
            "approved": sum(row["state"] == "validate" for row in rows)}

    @api.model
    def review_leave(self, leave_id, decision):
        self._check_owner()
        if isinstance(leave_id, bool) or not isinstance(leave_id, int) or decision not in ("approve", "refuse"):
            raise ValidationError(_("Choose a valid leave request and decision."))
        leave = self.env["hr.leave"].search([("id", "=", leave_id), ("company_id", "=", self.env.company.id),
            ("state", "in", ["confirm", "validate1"])])
        if not leave:
            raise AccessError(_("This request is no longer pending or is outside your college."))
        if decision == "refuse":
            leave.action_refuse()
        elif leave.state == "validate1":
            leave.action_validate()
        else:
            leave.action_approve()
        return True
