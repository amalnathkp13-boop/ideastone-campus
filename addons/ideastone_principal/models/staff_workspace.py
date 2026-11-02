from collections import defaultdict
from datetime import timedelta

import pytz
from odoo.addons.ideastone_erp.models.late_punch import LATE_CUTOFF, late_punch_dates
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
                   ("New staff applications", "ideastone_principal.action_staff_applications"),
                   ("Payroll History", "ideastone_principal.action_staff_payroll")]
        return [(key, label, icon, entries if key == "staff" else items) for key, label, icon, items in modules]

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{
            "ideastone_principal.action_staff_directory": "op.faculty",
            "ideastone_principal.action_staff_applications": "ideastone.principal.staff.application",
            "ideastone_principal.action_staff_payroll": "ideastone.principal.staff.application"})


class PrincipalStaffWorkspace(models.AbstractModel):
    _name = "ideastone.principal.staff.workspace"
    _description = "Principal staff directory, recruitment and payroll oversight"

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
        principal_access(self.env)
        if str(year) not in ("", "all") and (not str(year).isdigit() or not 2000 <= int(year) <= 2100):
            raise ValidationError(_("Choose a valid year."))
        if str(month) not in ("", "all") and (not str(month).isdigit() or not 1 <= int(month) <= 12):
            raise ValidationError(_("Choose a valid month."))
        year, month = int(year) if str(year).isdigit() else 0, int(month) if str(month).isdigit() else 0
        company, today = self.env.company, fields.Date.context_today(self)
        employees = self.env["hr.employee"].sudo().search([("company_id", "=", company.id)], order="name")
        faculty = self.env["op.faculty"].sudo().search([("company_id", "=", company.id), ("emp_id", "in", employees.ids)])
        academic = {p.emp_id.id: p.main_department_id for p in faculty
                    if not p.main_department_id.company_id or p.main_department_id.company_id == company}
        slips = self.env["campus.payslip"].sudo().search([("company_id", "=", company.id),
            ("employee_id", "in", employees.ids), ("state", "in", ["approved", "done"])])
        punches = self.env["hr.attendance"].sudo().search([("employee_id", "in", employees.ids)], order="check_in asc")
        by_employee = defaultdict(dict)
        years = {today.year} | {s.date_from.year for s in slips}
        for punch in punches:
            timezone = pytz.timezone(punch.employee_id.resource_calendar_id.tz or "UTC")
            local = pytz.UTC.localize(punch.check_in).astimezone(timezone)
            years.add(local.year)
            entries = by_employee[punch.employee_id.id]
            day = entries.setdefault(local.date(), {"in": local, "out": None})
            if punch.check_out:
                out = pytz.UTC.localize(punch.check_out).astimezone(timezone)
                day["out"] = max(out, day["out"]) if day["out"] else out

        def in_period(day):
            return (not year or day.year == year) and (not month or day.month == month)

        rows, present, late_today = [], 0, 0
        week_start = today - timedelta(days=today.weekday())
        trend = [{"day": str(week_start + timedelta(days=i)), "label": label, "late": 0, "on_time": 0}
                 for i, label in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"])]
        for employee in employees:
            entries = by_employee[employee.id]
            months = {day.replace(day=1) for day in entries if in_period(day) or week_start <= day <= today}
            months.add(today.replace(day=1))
            late = {day for start in months for day in late_punch_dates(self.sudo().env, employee, start)}
            present += today in entries
            late_today += today in late
            for point in trend:
                day = fields.Date.to_date(point["day"])
                if day in entries:
                    point["late" if day in late else "on_time"] += 1
            selected_days = sorted(day for day in entries if in_period(day))
            latest = entries[selected_days[-1]] if selected_days else {}
            payroll = slips.filtered(lambda s, employee=employee: s.employee_id == employee and in_period(s.date_from))
            late_count = sum(in_period(day) for day in late)
            department = academic.get(employee.id)
            rows.append({"id": employee.id, "name": employee.name,
                "department": (department.code or department.name) if department else employee.department_id.name or "—",
                "check_in": latest["in"].strftime("%I:%M %p") if latest else "—",
                "check_out": latest["out"].strftime("%I:%M %p") if latest and latest["out"] else "—",
                "date": str(selected_days[-1]) if selected_days else "", "late_count": late_count,
                "deducted_days": sum(payroll.mapped("late_deducted_days")), "deduction": sum(payroll.mapped("late_deduction")),
                "gross": sum(payroll.mapped("gross")), "net": sum(payroll.mapped("net")),
                "pf": sum(payroll.mapped("pf")), "tds": sum(payroll.mapped("tds")),
                "approved_periods": len(payroll), "status": "Late" if selected_days and selected_days[-1] in late else "On time" if latest else "No punch"})
        return {"rows": rows, "today": str(today), "company": company.name, "demo": company.campus_demo,
            "years": sorted(years, reverse=True), "currency": company.currency_id.symbol,
            "present": present, "total": len(employees), "late_today": late_today,
            "deductions": sum(r["deduction"] for r in rows), "repeated": sum(r["late_count"] >= 3 for r in rows),
            "trend": trend, "threshold": LATE_CUTOFF.strftime("%I:%M %p")}
