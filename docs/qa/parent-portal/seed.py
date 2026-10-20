"""Synthetic Parent Portal scenario for a disposable CI database only."""
import base64
import os
from datetime import timedelta

from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
company = env["res.company"].search([("name", "=", "QA Demo College — sample data")])  # noqa: F821
assert len(company) == 1 and company.campus_demo
env = env(context=dict(env.context, allowed_company_ids=company.ids, tz="Asia/Kolkata", no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
arun = env["op.student"].search([("company_id", "=", company.id), ("last_name", "=", "Arun")])
meena = env["op.student"].search([("company_id", "=", company.id), ("last_name", "=", "Meena")])
kavin = env["op.student"].search([("company_id", "=", company.id), ("last_name", "=", "Kavin")])
assert len(arun) == len(meena) == len(kavin) == 1
env["res.users"].search([("login", "=", "owner.ui.qa")]).password = os.environ["PARENT_QA_PASSWORD"]
relation = env["op.parent.relationship"].create({"name": "QA Guardian"})
for login, name, children in [("parent.ui.qa", "Demo Parent", arun | meena), ("parent.other.qa", "Other Parent", kavin)]:
    account = new_test_user(env, login=login, name=name, password=os.environ["PARENT_QA_PASSWORD"], tz="Asia/Kolkata",
        company_id=company.id, company_ids=[(6, 0, company.ids)], groups="base.group_portal", is_parent=True)
    env["op.parent"].create({"name": account.partner_id.id, "user_id": account.id, "relationship_id": relation.id, "student_ids": [(6, 0, children.ids)]})
notice = env["campus.circular"].create({"name": "Parent meeting and academic updates", "reference": "PARENT-QA", "body": "<p>Use the parent request centre to arrange a meeting with the college.</p>", "audience": "parent", "campus_managed": True, "parent_pinned": True})
notice.action_campus_publish()
placement = arun.course_detail_ids
kind = env["grading.assignment.type"].create({"name": "QA homework"})
faculty = env["op.faculty"].search([("campus_staff_code", "=", "OWNERQA"), ("company_id", "=", company.id)])
task = env["op.assignment"].create({"name": "Programming exercise for QA Arun", "course_id": placement.course_id.id,
    "batch_id": placement.batch_id.id, "subject_id": placement.course_id.subject_ids[:1].id, "faculty_id": faculty.id,
    "assignment_type": kind.id, "description": "Review the published course guide and complete the programming exercise.",
    "issued_date": fields.Datetime.now(), "submission_date": fields.Datetime.now() + timedelta(days=2), "allocation_ids": [(6, 0, arun.ids)]})
task.act_publish()
env["op.assignment.sub.line"].create({"assignment_id": task.id, "student_id": arun.id,
    "company_id": company.id,
    "description": "PRIVATE STUDENT DRAFT", "note": "PRIVATE FACULTY DRAFT",
    "campus_file": base64.b64encode(b"Private student coursework"), "campus_filename": "private-coursework.txt"})
requirement = env["campus.admission.requirement"].create({"name": "Parent-released college letter", "required": False})
admission = env["op.admission"].search([("student_id", "=", arun.id)], limit=1)
doc = env["campus.admission.document"].create({"admission_id": admission.id, "requirement_id": requirement.id,
    "filename": "college-letter.txt", "file": base64.b64encode(b"Synthetic verified college letter for the linked guardian.")})
doc.action_verify()
doc.action_parent_share()
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:18069")
env.cr.commit()
print("Parent QA scenario seeded with two linked children and a separate unrelated parent.")
