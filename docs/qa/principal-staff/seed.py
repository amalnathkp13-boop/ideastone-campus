"""Run with odoo shell in principal_staff_preview only; never installs production demo data."""
import json
import secrets
from calendar import monthrange
from datetime import datetime, time, timedelta

import pytz

from odoo import fields

assert env.cr.dbname == "principal_staff_preview"
samples = json.load(open("/tmp/principal-staff-sample.json", encoding="utf-8-sig"))
company = env["res.company"].search([("name", "=", "VCET Principal Staff Preview")], limit=1)
if not company:
    company = env["res.company"].create({"name": "VCET Principal Staff Preview", "campus_demo": True,
        "currency_id": env.ref("base.INR").id})
env = env(context=dict(env.context, allowed_company_ids=[company.id], tz="Asia/Kolkata", no_reset_password=True,
                       mail_create_nosubscribe=True, mail_notrack=True))
principal = env["res.users"].search([("login", "=", "principal.staff@campus.local")], limit=1)
password = secrets.token_urlsafe(18)
values = {"name": "Principal Staff Preview", "login": "principal.staff@campus.local", "password": password,
    "tz": "Asia/Kolkata", "company_id": company.id, "company_ids": [(6, 0, company.ids)],
    "groups_id": [(6, 0, [env.ref("ideastone_principal.group_principal").id])]}
if principal:
    principal.write(values)
else:
    principal = env["res.users"].create(values)
hr = env["res.users"].search([("login", "=", "hr.staff.seed@campus.local")], limit=1) or env["res.users"].create({
    "name": "Preview HR Manager", "login": "hr.staff.seed@campus.local", "company_id": company.id,
    "company_ids": [(6, 0, company.ids)], "groups_id": [(6, 0, [env.ref("ideastone_erp.group_manager").id,
        env.ref("ideastone_erp.group_people").id])]})
today = fields.Date.context_today(env["ideastone.principal.staff.workspace"].with_user(principal))
timezone = pytz.timezone("Asia/Kolkata")
calendar = env["resource.calendar"].search([("name", "=", "Preview staff 9 to 5"), ("company_id", "=", company.id)], limit=1)
if not calendar:
    calendar = env["resource.calendar"].create({"name": "Preview staff 9 to 5", "company_id": company.id,
        "tz": "Asia/Kolkata", "attendance_ids": [(5, 0, 0)] + [(0, 0, {"name": "Campus workday", "dayofweek": str(day),
            "hour_from": 9, "hour_to": 17, "day_period": "morning"}) for day in range(5)]})
departments, hr_departments = {}, {}
for row in samples["departments"] + [{"id": "LIB", "name": "Library"}]:
    department = env["op.department"].search([("company_id", "=", company.id), ("code", "=", row["id"])], limit=1)
    departments[row["id"]] = department or env["op.department"].create({"name": row["name"], "code": row["id"], "company_id": company.id})
    hr_departments[row["id"]] = env["hr.department"].search([("company_id", "=", company.id), ("name", "=", row["name"])], limit=1) or env["hr.department"].create({"name": row["name"], "company_id": company.id})
staff = {}
for p in samples["people"]:
    code = "PS-" + p[4]
    faculty = env["op.faculty"].with_context(active_test=False).search([("campus_staff_code", "=", code)], limit=1)
    if not faculty:
        employee = env["hr.employee"].create({"name": p[0], "company_id": company.id, "department_id": hr_departments[p[1]].id,
            "job_title": p[2], "work_email": p[5], "work_phone": p[6], "gender": p[7].lower(), "birthday": p[8],
            "resource_calendar_id": calendar.id})
        partner = env["res.partner"].create({"name": p[0], "company_id": company.id, "email": p[5], "phone": p[6]})
        first, _, last = p[0].rpartition(" ")
        faculty = env["op.faculty"].create({"first_name": first, "last_name": last, "partner_id": partner.id,
            "gender": p[7].lower(), "birth_date": p[8], "main_department_id": departments[p[1]].id,
            "campus_staff_code": code, "campus_designation": p[2], "campus_category": "teaching" if p[3] == "Teaching" else "non_teaching",
            "campus_service_type": p[10].lower(), "campus_joining_date": p[9], "emp_id": employee.id})
    staff[p[0]] = faculty.emp_id

leave_type = env["hr.leave.type"].search([("name", "=", "Preview staff leave")], limit=1) or env["hr.leave.type"].create({
    "name": "Preview staff leave", "requires_allocation": "no", "leave_validation_type": "no_validation", "company_id": company.id})
for p in samples["people"]:
    if p[11] != "On leave":
        continue
    employee = staff[p[0]]
    if not env["hr.leave"].search_count([("employee_id", "=", employee.id), ("request_date_from", "=", today)]):
        leave = env["hr.leave"].create({"name": "Preview approved leave", "employee_id": employee.id,
            "holiday_status_id": leave_type.id, "request_date_from": today, "request_date_to": today})
        if leave.state == "draft":
            leave.action_confirm()

late_counts = {"Dr. Julie Wilson": 1, "Dr. S. Kumar": 4, "Maria C Daniel": 3, "Arun Prakash": 0,
    "Kavitha R": 6, "Ramesh Babu": 2, "Anitha S": 5}
for name, employee in staff.items():
    count = late_counts.get(name, 0)
    for offset in (3, 2, 1):
        start = fields.Date.subtract(today.replace(day=1), months=offset)
        end = start.replace(day=monthrange(start.year, start.month)[1])
        workdays = [start + timedelta(days=i) for i in range((end - start).days + 1) if (start + timedelta(days=i)).weekday() < 5]
        for position, day in enumerate(workdays):
            arrival = time(9, 12 + position % 15) if position < count else time(8, 48)
            check_in = timezone.localize(datetime.combine(day, arrival)).astimezone(pytz.UTC).replace(tzinfo=None)
            check_out = timezone.localize(datetime.combine(day, time(17, 5))).astimezone(pytz.UTC).replace(tzinfo=None)
            if not env["hr.attendance"].search_count([("employee_id", "=", employee.id), ("check_in", "=", check_in)]):
                env["hr.attendance"].create({"employee_id": employee.id, "check_in": check_in, "check_out": check_out})
        if name not in late_counts:
            continue
        agreement = env["campus.salary.agreement"].search([("employee_id", "=", employee.id)], limit=1)
        if not agreement:
            agreement = env["campus.salary.agreement"].create({"name": "Preview salary " + name, "employee_id": employee.id,
                "company_id": company.id, "date_from": fields.Date.subtract(today.replace(day=1), months=4),
                "basic": 26950, "pf_base": 33333.33, "pf_rate": 12, "tds": 3000})
            agreement.with_user(hr).action_submit()
            agreement.with_user(hr).action_approve()
        if not env["campus.payslip"].search_count([("employee_id", "=", employee.id), ("date_from", "=", start)]):
            slip = env["campus.payslip"].create({"name": "Preview payroll " + name + " " + str(start), "company_id": company.id,
                "agreement_id": agreement.id, "date_from": start, "date_to": end, "working_days": len(workdays)})
            slip.with_user(hr).action_compute()
            slip.with_user(hr).action_submit()
            slip.with_user(hr).action_approve()
    for day in (today - timedelta(days=today.weekday()), today):
        if employee.name in ("Mohan Raj", "Vijay Anand"):
            continue
        arrival = time(9, 17) if count >= 3 else time(8, 48)
        check_in = timezone.localize(datetime.combine(day, arrival)).astimezone(pytz.UTC).replace(tzinfo=None)
        if not env["hr.attendance"].search_count([("employee_id", "=", employee.id), ("check_in", "=", check_in)]):
            env["hr.attendance"].create({"employee_id": employee.id, "check_in": check_in,
                "check_out": timezone.localize(datetime.combine(day, time(17, 5))).astimezone(pytz.UTC).replace(tzinfo=None)})

for index, app in enumerate(samples["applications"]):
    if env["ideastone.principal.staff.application"].search_count([("company_id", "=", company.id), ("name", "=", app["name"])]):
        continue
    code = ["CSE", "ECE", "EEE", "MECH", "ADMIN", "CIVIL", "LIB"][index]
    record = env["ideastone.principal.staff.application"].with_user(principal).create({"name": app["name"],
        "company_id": company.id, "staff_type": "teaching" if app["type"] == "Teaching" else "non_teaching", "role": app["role"],
        "department_id": departments[code].id, "qualification": app["qualification"], "experience": app["experience"],
        "documents": "verified" if app["docs"] == "Verified" else "incomplete", "review": app["review"],
        "interview_date": datetime.combine(today + timedelta(days=-4 if app["status"] in ("Approved", "Rejected") else 3 + index), time(5, 0)) if app["interview"] != "Not scheduled" else False})
    if app["status"] == "Interview":
        record.action_schedule_interview()
    if app["status"] in ("Approved", "Rejected"):
        record._decide(app["status"].lower(), app["review"])
env["ir.attachment"].search([("url", "=like", "/web/assets/%")]).unlink()
env.cr.commit()
json.dump({"login": values["login"], "password": password, "company_id": company.id}, open("/tmp/principal-staff-credentials.json", "w"))
print("Principal staff preview ready:", company.id, len(staff), "staff; actions:",
      [env.ref("ideastone_principal.action_staff_" + key).id for key in ("directory", "applications", "payroll")])
