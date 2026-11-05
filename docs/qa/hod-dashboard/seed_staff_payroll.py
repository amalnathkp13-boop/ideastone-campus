"""Seed Staff & Payroll in the existing disposable HOD preview."""

from datetime import date, timedelta

import pytz
from odoo.exceptions import AccessError

from odoo import fields
from odoo.addons.ideastone_erp.models.faculty_profile_workspace import HOD_LABELS, PAGES
from odoo.addons.ideastone_erp.models.late_punch import local_bounds


def seed(env):
    assert env.cr.dbname == "hod_dashboard_reference", "Disposable HOD preview only"
    env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True))
    hod = env["res.users"].search([("login", "=", "exam.hod.preview")], limit=1)
    peer = env["res.users"].search([("login", "=", "exam.faculty.preview")], limit=1)
    assert hod and peer
    hod.partner_id.email = "hod.sample@example.test"
    env = env["res.users"].with_company(hod.company_id).env
    company = env.company
    env["ir.config_parameter"].set_param("report.url", "http://127.0.0.1:8069")
    today = fields.Date.context_today(hod.with_context(tz=hod.tz))
    faculty = env["op.faculty"].search([("user_id", "=", hod.id)], limit=1)
    colleague = env["op.faculty"].search([("user_id", "=", peer.id)], limit=1)
    assert faculty and colleague

    def ensure(model, domain, values):
        return env[model].search(domain, limit=1) or env[model].create(values)

    reviewer = ensure("res.users", [("login", "=", "hod.staff.qa.reviewer")], {
        "name": "Sample HR reviewer", "login": "hod.staff.qa.reviewer", "company_id": company.id,
        "company_ids": [(6, 0, company.ids)],
        "groups_id": [(6, 0, [env.ref("ideastone_erp.group_people").id, env.ref("ideastone_erp.group_manager").id])],
    })
    if not faculty.campus_staff_code:
        faculty.write({
            "campus_staff_code": "FAC-0248", "campus_designation": "Head of Department", "campus_service_type": "permanent",
            "campus_joining_date": "2020-06-15", "campus_profile_review_date": today + timedelta(days=9),
            "campus_emergency_phone": "+91 55555 01002", "campus_communication_address": "Erode, Tamil Nadu, India",
            "email": "hod.sample@example.test", "mobile": "+91 55555 01001",
        })
    employee = ensure("hr.employee", [("user_id", "=", hod.id), ("company_id", "=", company.id)], {
        "name": faculty.name, "user_id": hod.id, "company_id": company.id, "job_title": "Head of Department",
    })
    direct_report = env["hr.employee"].search([("user_id", "=", peer.id), ("company_id", "=", company.id)], limit=1)
    assert direct_report
    direct_report.leave_manager_id = hod
    for staff, title, category, verify in [
        (faculty, "Ph.D. / highest qualification", "academic", True),
        (faculty, "M.E. degree certificate", "academic", True),
        (faculty, "Recent faculty development certificate", "professional", False),
        (faculty, "Professional membership", "membership", False),
        (colleague, "Faculty Sample · Academic qualification", "academic", True),
        (colleague, "Sample confidential identity title", "identity", False),
    ]:
        document = ensure("campus.faculty.detail", [("name", "=", title), ("faculty_id", "=", staff.id)], {
            "name": title, "faculty_id": staff.id, "kind": "qualification", "campus_category": category,
            "campus_expiry_date": today + timedelta(days=14) if category == "membership" else False,
        })
        if verify and document.verification != "verified":
            document.with_user(reviewer).sudo().action_verify()

    for staff, title, kind, hours in [
        (faculty, "Journal publication — embedded systems", "paper", 8),
        (faculty, "Outcome-based education workshop", "fdp", 12),
        (faculty, "Online course — learning analytics", "mooc", 4),
        (faculty, "Sample M.Phil supervision", "mphil", 0),
        (colleague, "Sample department teaching workshop", "fdp", 6),
    ]:
        activity = ensure("campus.faculty.achievement", [("name", "=", title), ("faculty_id", "=", staff.id)], {
            "name": title, "faculty_id": staff.id, "kind": kind, "campus_hours": hours,
            "date_from": today - timedelta(days=20), "description": "Synthetic appraisal evidence for the local preview.",
        })
        if activity.state == "draft" and kind != "mphil":
            activity.action_submit()
        if activity.state == "submitted" and kind in ("paper", "fdp"):
            activity.with_user(reviewer).sudo().action_approve()

    year = today.year if today.month >= 4 else today.year - 1
    effective = date(year, 4, 1)
    agreement = ensure("campus.salary.agreement", [("name", "=", "SAL-HOD-SAMPLE"), ("employee_id", "=", employee.id)], {
        "name": "SAL-HOD-SAMPLE", "employee_id": employee.id, "date_from": effective,
        "basic": 58000, "allowance": 12000, "tds": 650, "pf_rate": 12, "pf_base": 15000,
    })
    if agreement.state == "draft":
        agreement.action_submit()
    if agreement.state == "submitted":
        agreement.with_user(reviewer).sudo().action_approve()
    for offset in (1, 2, 3):
        end = today.replace(day=1)
        for _index in range(offset):
            end = (end - timedelta(days=1)).replace(day=1)
        start = end
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if start < agreement.date_from:
            continue
        workdays = [start + timedelta(days=n) for n in range((end - start).days + 1)
                    if (start + timedelta(days=n)).weekday() < 5]
        zone = pytz.timezone(employee.resource_calendar_id.tz or "UTC")
        for day in workdays:
            check_in = local_bounds(day, zone)[0] + timedelta(hours=9)
            ensure("hr.attendance", [("employee_id", "=", employee.id), ("check_in", "=", check_in)], {
                "employee_id": employee.id, "check_in": check_in, "check_out": check_in + timedelta(hours=9),
            })
        slip = ensure("campus.payslip", [("employee_id", "=", employee.id), ("date_from", "=", start), ("date_to", "=", end)], {
            "name": f"Sample HOD payroll · {start:%B %Y}", "agreement_id": agreement.id,
            "date_from": start, "date_to": end, "working_days": len(workdays), "payment_reference": f"QA-HOD-{start:%Y%m}",
        })
        if slip.state == "draft":
            slip.with_user(reviewer).sudo().action_compute()
            slip.action_submit()
        if slip.state == "submitted":
            slip.with_user(reviewer).sudo().action_approve()
        if slip.state == "approved":
            slip.with_user(reviewer).sudo().action_done()

    leave_type = ensure("hr.leave.type", [("name", "=", "HOD sample staff leave"), ("company_id", "=", company.id)], {
        "name": "HOD sample staff leave", "company_id": company.id, "requires_allocation": "no",
        "leave_validation_type": "manager", "sequence": 1,
    })
    leave_day = today + timedelta(days=10)
    while leave_day.weekday() > 4:
        leave_day += timedelta(days=1)
    request = ensure("hr.leave", [("private_name", "=", "Sample department leave"), ("employee_id", "=", direct_report.id)], {
        "name": "Sample department leave", "employee_id": direct_report.id, "holiday_status_id": leave_type.id,
        "request_date_from": leave_day, "request_date_to": leave_day,
    })
    if request.state == "draft":
        request.action_confirm()
    api = env["campus.faculty.workspace"].with_user(hod)
    overview = env["campus.dashboard"].with_user(hod).get_overview()
    staff = next(module for module in overview["faculty_modules"] if module["key"] == "staff")
    assert [item["label"] for item in staff["items"]] == [HOD_LABELS.get(key, label) for key, label in PAGES]
    monthly = api.get_workspace("monthly")
    assert monthly["currency"] == "INR" and monthly["currency_symbol"] == "₹"
    assert monthly["payroll"]
    assert any(row["id"] == request.id for row in api.get_workspace("leave")["hod"]["leave"]["requests"])
    documents = api.get_workspace("qualifications")["documents"]
    assert any(row.get("peer") and row["name"] == "Identity document" and "filename" not in row for row in documents)
    try:
        env["campus.faculty.workspace"].with_user(peer)._own_agreements([agreement.id])
    except AccessError:
        pass
    else:
        raise AssertionError("A different faculty account read the HOD salary agreement")
    env.cr.commit()
    print("HOD staff payroll sample records and access checks passed")


seed(env)  # noqa: F821
