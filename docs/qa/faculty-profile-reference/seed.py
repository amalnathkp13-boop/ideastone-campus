"""Synthetic, one-time preview data. Run only in the named local preview database."""
import base64
import calendar
import io
import os
from datetime import datetime, time, timedelta

import pytz
from reportlab.pdfgen import canvas

from odoo import fields

assert env.cr.dbname == "faculty_profile_reference_preview"
assert not env["res.users"].search_count([("login", "=", "faculty.profile.preview")])
company = env["res.company"].create({"name": "VCET Faculty Profile Preview", "campus_demo": True,
    "currency_id": env.ref("base.INR").id, "country_id": env.ref("base.in").id})
env = env(context=dict(env.context, allowed_company_ids=company.ids, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
today = fields.Date.today()
staff = env["res.users"].create({"name": "Andre Santos", "login": "faculty.profile.preview", "email": "andre.santos@example.test", "password": os.environ["FACULTY_PROFILE_PREVIEW_PASSWORD"],
    "company_id": company.id, "company_ids": [(6, 0, company.ids)], "tz": "Asia/Kolkata",
    "groups_id": [(6, 0, [env.ref("openeducat_core.group_op_faculty").id])]})
reviewer = env["res.users"].create({"name": "Sample HR Reviewer", "login": "faculty.profile.hr.audit", "email": "profile.hr@example.test", "company_id": company.id,
    "company_ids": [(6, 0, company.ids)], "groups_id": [(6, 0, [env.ref(key).id for key in [
        "ideastone_erp.group_manager", "ideastone_erp.group_people", "hr_holidays.group_hr_holidays_manager"]])]})
department = env["op.department"].create({"name": "Electronics & Communication Engineering", "code": "PROFILE-ECE", "company_id": company.id})
hod = env["op.faculty"].create({"first_name": "Sample", "last_name": "HOD", "birth_date": "1980-01-01", "gender": "male",
    "partner_id": env["res.partner"].create({"name": "Sample HOD", "company_id": company.id}).id,
    "company_id": company.id, "main_department_id": department.id})
faculty = env["op.faculty"].create({"first_name": "Andre", "last_name": "Santos", "birth_date": "1988-02-14", "gender": "male",
    "partner_id": env["res.partner"].create({"name": "Andre Santos", "user_id": staff.id, "company_id": company.id}).id,
    "company_id": company.id, "main_department_id": department.id, "campus_staff_code": "FAC-PREVIEW-0248",
    "campus_designation": "Assistant Professor", "campus_service_type": "permanent", "campus_joining_date": "2020-06-15",
    "campus_reporting_id": hod.id, "email": "andre.santos@example.test", "mobile": "+91 90000 00248",
    "campus_emergency_phone": "+91 90000 00418", "campus_communication_address": "Sample address, Erode, Tamil Nadu",
    "campus_profile_review_date": today + timedelta(days=20)})
manager = env["hr.employee"].create({"name": "Sample HOD", "company_id": company.id})
work_calendar = env["resource.calendar"].create({"name": "Faculty profile preview · 9 AM", "company_id": company.id, "tz": "Asia/Kolkata",
    "attendance_ids": [(5, 0, 0)] + [(0, 0, {"name": f"{day}-{period}", "dayofweek": str(day), "day_period": period,
        "hour_from": start, "hour_to": end}) for day in range(5) for period, start, end in [("morning", 9, 13), ("afternoon", 14, 18)]]})
employee = env["hr.employee"].create({"name": "Andre Santos", "user_id": staff.id, "company_id": company.id, "parent_id": manager.id,
    "resource_calendar_id": work_calendar.id})
output = io.BytesIO()
pdf = canvas.Canvas(output)
pdf.drawString(50, 780, "SYNTHETIC FACULTY PREVIEW · NOT AN OFFICIAL DOCUMENT")
pdf.drawString(50, 750, "Sample evidence for profile, document and appraisal interface review.")
pdf.save()
evidence = base64.b64encode(output.getvalue()).decode()
doc_names = [("Ph.D. / highest qualification", "academic"), ("M.E. degree certificate", "academic"), ("B.E. degree certificate", "academic"),
    ("Sample identity proof", "identity"), ("Recent faculty development certificate", "professional"), ("Professional membership", "membership")]
for index, (name, category) in enumerate(doc_names):
    document = env["campus.faculty.detail"].create({"name": name, "faculty_id": faculty.id, "company_id": company.id,
        "kind": "document", "campus_category": category, "document": evidence, "filename": f"sample-faculty-document-{index+1}.pdf",
        "campus_expiry_date": today + timedelta(days=12) if category == "membership" else False})
    if index != 4:
        document.with_user(reviewer).action_verify()
activity_names = [("Journal publication — embedded systems", "paper", 0), ("Institutional research proposal", "patent", 0),
    ("Outcome-based education workshop", "fdp", 12), ("AI-assisted teaching tools seminar", "training", 12),
    ("Department academic review participation", "review", 0), ("Online course — learning analytics", "mooc", 0)]
for index, (name, kind, hours) in enumerate(activity_names):
    activity = env["campus.faculty.achievement"].create({"name": name, "faculty_id": faculty.id, "company_id": company.id,
        "kind": kind, "date_from": today - timedelta(days=20-index*3), "campus_hours": hours,
        "description": "Synthetic portfolio record for UI demonstration.", "evidence": evidence if index != 3 else False,
        "filename": f"sample-activity-{index+1}.pdf" if index != 3 else False})
    if index in (0, 2, 4):
        activity.action_submit()
        activity.with_user(reviewer).action_approve()
    elif index in (1, 5):
        activity.action_submit()
zone = pytz.timezone("Asia/Kolkata")
for offset in (2, 1, 0):
    number = today.year * 12 + today.month - 1 - offset
    year, month0 = divmod(number, 12)
    first = today.replace(year=year, month=month0+1, day=1)
    last = min(today, first.replace(day=calendar.monthrange(first.year, first.month)[1]))
    agreement = env["campus.salary.agreement"].create({"name": f"SAL-PREVIEW-{first:%Y-%m}", "employee_id": employee.id,
        "company_id": company.id, "date_from": first, "date_to": last if offset else False, "basic": 58000, "allowance": 12000,
        "fixed_deduction": 550, "tds": 3000 if offset == 0 else 2700, "pf_base": 40000, "pf_rate": 10, "daily_hours": 8})
    agreement.action_submit()
    agreement.with_user(reviewer).action_approve()
    working_days = [first+timedelta(days=i) for i in range((last-first).days+1) if (first+timedelta(days=i)).weekday()<5]
    late_count = 3 if offset == 0 else 2 if offset == 2 else 0
    for index, day in enumerate(working_days):
        start = zone.localize(datetime.combine(day, time(9, 10 if index < late_count else 0))).astimezone(pytz.utc).replace(tzinfo=None)
        end = zone.localize(datetime.combine(day, time(18))).astimezone(pytz.utc).replace(tzinfo=None)
        env["hr.attendance"].create({"employee_id": employee.id, "check_in": start, "check_out": end})
    slip = env["campus.payslip"].create({"name": f"PAY-PREVIEW-{first:%Y-%m}", "company_id": company.id, "agreement_id": agreement.id,
        "date_from": first, "date_to": last, "working_days": len(working_days)})
    slip.with_user(reviewer).action_compute()
    slip.action_submit()
    slip.with_user(reviewer).action_approve()
    slip.with_user(reviewer).write({"payment_reference": f"DEMO-ONLY-{first:%Y-%m}"})
    slip.with_user(reviewer).action_done()
leave_type = env["hr.leave.type"].create({"name": "Casual Leave · Profile Preview", "company_id": company.id, "requires_allocation": "yes",
    "allocation_validation_type": "no", "leave_validation_type": "hr", "request_unit": "half_day", "sequence": -999})
allocation = env["hr.leave.allocation"].create({"name": "Synthetic preview entitlement", "employee_id": employee.id,
    "holiday_status_id": leave_type.id, "number_of_days": 8, "date_from": today.replace(month=1, day=1), "date_to": today.replace(month=12, day=31)})
if allocation.state == "draft":
    allocation.action_confirm()
if allocation.state != "validate":
    allocation.with_user(reviewer).action_validate()
for index in range(2):
    day = today + timedelta(days=7+index*7)
    day += timedelta(days=(7-day.weekday())%7)
    leave = env["hr.leave"].create({"employee_id": employee.id, "holiday_status_id": leave_type.id, "request_date_from": day,
        "request_date_to": day, "private_name": "Synthetic preview personal commitment"})
    if leave.state == "draft":
        leave.action_confirm()
    if index == 0:
        leave.with_user(reviewer).action_approve()
action = env.ref("ideastone_erp.action_faculty_profile_myprofile")
staff.action_id = action.id
env.cr.commit()
data = env["campus.faculty.workspace"].with_user(staff).get_workspace()
print({"company": company.id, "faculty": faculty.id, "profile_action": action.id, "documents": len(data["documents"]),
    "activities": len(data["activities"]), "payroll": [(str(r["date_from"]), r["net"], r["late_days"], r["late_deducted_days"]) for r in data["payroll"]]})
