"""Synthetic payroll preview only; run through Odoo shell after installation."""
import calendar
import os
from datetime import datetime

import pytz
from odoo.tests import new_test_user

assert env.cr.dbname == "payroll_parity_preview", "Synthetic preview database only"
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
assert not env["res.users"].search_count([("login", "=", "payroll.faculty.preview")]), "Already seeded"
env["ir.cron"].search([]).write({"active": False})
env["ir.mail_server"].search([]).write({"active": False})
env["auth.oauth.provider"].search([]).write({"enabled": False})
currency = env["res.currency"].with_context(active_test=False).search([("name", "=", "INR")], limit=1)
currency.active = True
company = env["res.company"].create({"name": "VCET Synthetic Payroll Preview", "currency_id": currency.id})
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
password = os.environ["PAYROLL_QA_PASSWORD"]
admin = new_test_user(env, login="payroll.admin.preview", name="Sample Payroll Admin", password=password,
                      groups="ideastone_erp.group_manager", company_id=company.id, company_ids=[(6, 0, company.ids)])
faculty = new_test_user(env, login="payroll.faculty.preview", name="Sample Faculty", password=password,
                        groups="openeducat_core.group_op_faculty", company_id=company.id, company_ids=[(6, 0, company.ids)])
partner = env["res.partner"].create({"name": "Sample Faculty", "user_id": faculty.id, "company_id": env.company.id})
env["op.faculty"].create({"first_name": "Sample", "last_name": "Faculty", "gender": "female",
                         "birth_date": "1990-01-01", "partner_id": partner.id})
schedule = env["resource.calendar"].create({"name": "Synthetic payroll Mon-Sat 09:00-17:00", "tz": "Asia/Kolkata",
    "attendance_ids": [(5, 0, 0)] + [(0, 0, {"name": "Sample workday", "dayofweek": str(n),
        "hour_from": 9, "hour_to": 17, "day_period": "morning"}) for n in range(6)]})
employee = env["hr.employee"].create({"name": "Sample Faculty", "user_id": faculty.id,
                                     "resource_calendar_id": schedule.id})
agreement = env["campus.salary.agreement"].with_user(admin).create({"name": "SAMPLE ONLY - payroll parity terms",
    "employee_id": employee.id, "date_from": "2026-08-01", "date_to": "2026-09-30", "basic": 26000, "daily_hours": 8})
agreement.action_submit()
agreement.action_approve()
timezone = pytz.timezone("Asia/Kolkata")
for month, late_days in [(8, {1}), (9, {1, 2, 3, 4})]:
    working = 0
    last = calendar.monthrange(2026, month)[1]
    for day in range(1, last + 1):
        date = datetime(2026, month, day)
        if date.weekday() == 6:
            continue
        working += 1
        late = day in late_days
        start = datetime(2026, month, day, 9, 10) if late else datetime(2026, month, day, 8, 50)
        end = datetime(2026, month, day, 17, 10 if late else 0)
        env["hr.attendance"].create({"employee_id": employee.id,
            "check_in": timezone.localize(start).astimezone(pytz.UTC).replace(tzinfo=None),
            "check_out": timezone.localize(end).astimezone(pytz.UTC).replace(tzinfo=None)})
    slip = env["campus.payslip"].with_user(admin).create({"name": "SAMPLE ONLY - " + date.strftime("%B %Y"),
        "agreement_id": agreement.id, "date_from": f"2026-{month:02d}-01", "date_to": f"2026-{month:02d}-{last}",
        "working_days": working})
    slip.action_compute()
    slip.action_submit()
    slip.action_approve()
    expected = (1, 1, 0, 0, 26000) if month == 8 else (4, 2, 2, 2000, 24000)
    assert (slip.late_days, slip.late_grace_days, slip.late_deducted_days, slip.late_deduction, slip.net) == expected
    print({"month": month, "late_days": slip.late_days, "paid_permissions": slip.late_grace_days,
           "deducted_days": slip.late_deducted_days, "deduction": slip.late_deduction, "net": slip.net})
env.cr.commit()
assert env["campus.payslip"].with_user(admin).get_history_data(employee.id)["records"] == env["campus.payslip"].with_user(faculty).get_history_data()["records"]
print({"employee_id": employee.id, "payroll_action": env.ref("ideastone_erp.action_payroll_history_page").id})
