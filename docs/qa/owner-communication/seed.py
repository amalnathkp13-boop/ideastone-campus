"""Disposable localhost preview data; run inside an Odoo shell on the named clone only."""
import os
from datetime import datetime, time, timedelta

import pytz

from odoo import fields
from odoo.tests import new_test_user

assert env.cr.dbname == "campus_owner_communication_preview"  # noqa: F821
password = os.environ["OWNER_COMMUNICATION_PREVIEW_PASSWORD"]
company = env["res.company"].browse(13)  # noqa: F821
assert company.exists() and company.name == "VCET Question Paper Preview College"
env = env(context=dict(env.context, allowed_company_ids=[company.id], no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
owner = env["res.users"].search([("login", "=", "owner.communication.preview@example.test")], limit=1)
if not owner:
    owner = new_test_user(env, login="owner.communication.preview@example.test", name="Communication Preview Owner",
                          password=password, company_id=company.id, company_ids=[(6, 0, company.ids)],
                          groups="ideastone_erp.group_mvp_owner", tz="Asia/Kolkata")
today = fields.Date.context_today(owner)

students = env["op.student"]
for index, (name, number) in enumerate([
    ("Sample Arun", "VC26ECE014"), ("Sample Meena", "VC25CSE027"),
    ("Sample Kavin", "VC24IT009"), ("Sample Priya", "VC25EEE032"),
    ("Sample Hari", "VC26MECH016"),
]):
    student = env["op.student"].search([("company_id", "=", company.id), ("gr_no", "=", number)], limit=1)
    if not student:
        portal = new_test_user(env, login=f"communication.student{index}@example.test", name=name,
                               password=password, company_id=company.id, company_ids=[(6, 0, company.ids)],
                               groups="base.group_portal", tz="Asia/Kolkata")
        partner = env["res.partner"].create({"name": name, "company_id": company.id})
        student = env["op.student"].create({"first_name": name.split()[0], "last_name": name.split()[1],
            "gender": "o", "birth_date": "2006-01-01", "gr_no": number, "partner_id": partner.id,
            "company_id": company.id, "user_id": portal.id})
    students |= student

ui = env["campus.owner.communication.ui"].with_user(owner).with_company(company)
notices = [
    ("Internal Assessment timetable", "Examination", "student", 1, 9, "scheduled"),
    ("Semester fee reminder", "Finance", "student", 2, 10, "attention"),
    ("Technical Symposium registration", "Events", "student", 2, 12, "draft"),
    ("Faculty meeting — agenda and venue", "General", "faculty", 0, 8, "published"),
    ("Library working hours — festival week", "General", "all", 0, 8, "published"),
    ("Transport route update", "General", "student", 0, 8, "published"),
]
for index, (title, category, audience, offset, hour, status) in enumerate(notices):
    publish_at = pytz.timezone("Asia/Kolkata").localize(datetime.combine(today + timedelta(days=offset), time(hour, 0))).astimezone(pytz.UTC).replace(tzinfo=None)
    existing = env["campus.circular"].search([("company_id", "=", company.id), ("name", "=", title)], limit=1)
    if existing:
        if existing.campus_status in {"draft", "scheduled"}:
            existing.write({"date_from": today + timedelta(days=offset), "communication_publish_at": publish_at})
        continue
    rec = env["campus.circular"].with_user(owner).with_company(company).create({"name": title,
        "reference": f"COM-{261-index:04d}", "campus_managed": True, "campus_category": category,
        "audience": audience, "date_from": today + timedelta(days=offset), "communication_publish_at": publish_at,
        "body": f"<p>Sample message for {title}.</p>"})
    if status == "attention":
        rec.action_submit()
    elif status in {"published", "scheduled"}:
        rec.action_campus_publish()

types = env["campus.student.request.type"].with_company(company).search(["|", ("company_id", "=", False), ("company_id", "=", company.id)])
support = types.filtered(lambda rec: rec.code == "support")[:1] or types[:1]
certificate = types.filtered(lambda rec: rec.code == "bonafide")[:1] or support
requests = [
    ("Bonafide certificate", certificate, students[0], "affairs", "time_sensitive", "submitted", "documents"),
    ("Scholarship clarification", support, students[1], "accounts", "deadline", "information", "fees"),
    ("Portal access issue", support, students[2], "it", "normal", "approved", "it"),
    ("ID card correction", support, students[3], "affairs", "normal", "done", "affairs"),
    ("Transfer certificate query", certificate, students[4], "academic", "normal", "information", "documents"),
]
for title, request_type, student, office, priority, status, category in requests:
    due_at = pytz.timezone("Asia/Kolkata").localize(datetime.combine(today + timedelta(days=0 if status == "information" else 1), time(17, 0))).astimezone(pytz.UTC).replace(tzinfo=None)
    existing = env["campus.service.request"].search([("company_id", "=", company.id), ("name", "=", title)], limit=1)
    if existing:
        existing._set_system_values({"communication_category": category, "communication_due_at": due_at})
        continue
    rec_id = ui.log_request({"name": title, "description": f"Sample support details for {title}.",
                             "student_id": student.id, "type_id": request_type.id, "office": office, "priority": priority, "category": category,
                             "due_at": due_at.isoformat() + "+00:00"})
    if status == "information":
        ui.respond_request(rec_id, "Please provide the supporting information.", "information")
    elif status == "approved":
        ui.respond_request(rec_id, "Your request is being processed.", "approved")
    elif status == "done":
        ui.respond_request(rec_id, "Your request has been completed.", "approved")
        ui.respond_request(rec_id, "Your request has been completed.", "done")

env.cr.commit()
print("Communication preview ready:", company.name, len(students), "students",
      env["campus.circular"].search_count([("company_id", "=", company.id), ("campus_managed", "=", True)]), "notices")
