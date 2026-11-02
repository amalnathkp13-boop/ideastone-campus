"""Synthetic circulars for the isolated local Accountant preview only."""
from datetime import datetime, time, timedelta

from odoo import fields

assert env.cr.dbname == "accountant_ui_preview", "Use only the isolated local preview database."
company = env["res.company"].browse(13)
e = env(context=dict(env.context, allowed_company_ids=company.ids))
marker = e["ir.config_parameter"].sudo()
if marker.get_param("accountant_fee_circular_sample"):
    print("Fee circular samples already exist")
else:
    accountant = e["res.users"].search([("login", "=", "college.accountant")], limit=1)
    accountant.tz = "Asia/Kolkata"
    service = e["campus.dashboard"].with_user(accountant)
    today = fields.Date.context_today(service)
    cs = e["op.department"].search([("company_id", "=", company.id), ("code", "=", "CS")], limit=1)
    commerce = e["op.department"].search([("company_id", "=", company.id), ("code", "=", "COM")], limit=1)
    samples = [
        ("016", "Semester fee payment schedule", "Payment windows and installment guidance", "fees", "student", "all", "published", today.replace(day=1), today + timedelta(days=28)),
        ("015", "Fee reminder – Semester 3", "Reminder for outstanding semester balances", "fees", "student_parent", "all", "scheduled", today + timedelta(days=3), today + timedelta(days=10)),
        ("014", "Examination fee notification", "Exam fee amount, eligibility and payment deadline", "exam", "student", "all", "draft", today, today + timedelta(days=18)),
        ("013", "Annual day contribution notice", "Optional contribution and event information", "event", "student_parent", "all", "published", today - timedelta(days=9), today + timedelta(days=13)),
        ("009", "Fee counter timing update", "Revised counter hours for collection support", "general", "faculty", "accounts", "archived", today - timedelta(days=53), today - timedelta(days=33)),
        ("017", "Transport fee reminder", "Annual transport payment and receipt instructions", "fees", "student", "all", "draft", today, today + timedelta(days=14)),
        ("018", "Scholarship fee adjustment", "Approved scholarship adjustments and payment guidance", "fees", "student_parent", str(cs.id), "published", today - timedelta(days=2), today + timedelta(days=15)),
        ("019", "Library dues collection window", "Confirm pending library-related dues before payment", "fees", "student_parent", str(commerce.id), "scheduled", today + timedelta(days=4), today + timedelta(days=16)),
        ("020", "Accounts office reconciliation", "Fee receipt matching and counter support instructions", "general", "faculty", "accounts", "draft", today, today + timedelta(days=7)),
        ("021", "Examination refund guidance", "Supporting documents required for approved exam fee refunds", "exam", "student", "all", "published", today - timedelta(days=1), today + timedelta(days=12)),
        ("022", "Cultural event contribution", "Voluntary event contribution and receipt procedure", "event", "student_parent", "all", "scheduled", today + timedelta(days=5), today + timedelta(days=20)),
        ("023", "Installment receipt helpdesk", "Where to submit fee receipts and payment references", "fees", "student", "all", "draft", today, today + timedelta(days=21)),
    ]
    created = []
    for code, title, message, category, audience, scope, status, first, last in samples:
        values = {"name": title, "reference": f"FC/{today.year}/{code}", "body": message + ". Please contact the accounts office for assistance.",
            "category": category, "audience": audience, "scope": scope, "effective_from": str(first), "due_date": str(last),
            "academic_scope": f"{today.year}–{str(today.year + 1)[-2:]} / Semester 3", "status": "draft" if status == "archived" else status}
        if status == "scheduled":
            values["publish_at"] = datetime.combine(first, time(9)).isoformat(timespec="minutes")
        notice_id = service.save_fee_circular(values)
        notice = e["campus.circular"].browse(notice_id)
        if status in {"published", "archived"}:
            # Reconstruct historical sample evidence; never run this fixture on the working college.
            notice._set_system_values({"approved_by": accountant.id, "approved_on": datetime.combine(first, time(9))})
        if status == "archived":
            service.archive_fee_circular(notice_id)
        created.append(notice)
    student = e["op.student"].search([("company_id", "=", company.id)], limit=1)
    if student:
        e["campus.student.notice.read"].create({"student_id": student.id, "notice_id": created[0].id})
    e.ref("ideastone_erp.sequence_fee_circular").number_next_actual = 100
    marker.set_param("accountant_fee_circular_sample", str(today))
    e.cr.commit()
    print("Fee circular sample drafts, releases, schedules, archive and acknowledgement saved")
