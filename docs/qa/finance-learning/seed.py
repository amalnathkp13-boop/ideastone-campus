"""Add real finance/coursework scenarios after the disposable Owner/Student/Parent seeds."""
import json
import os
from datetime import timedelta

from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
company = env["res.company"].search([("name", "=", "QA Demo College — sample data")])  # noqa: F821
assert len(company) == 1 and company.campus_demo
env = env(context=dict(env.context, allowed_company_ids=company.ids, tz="Asia/Kolkata", no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
for login in ["owner.ui.qa", "student.ui.qa", "parent.ui.qa"]:
    env["res.users"].search([("login", "=", login)]).password = os.environ["MVP_QA_PASSWORD"]
students = env["op.student"].search([("company_id", "=", company.id), ("last_name", "in", ["Arun", "Meena"])], order="last_name")
assert len(students) == 2
owner = env["res.users"].search([("login", "=", "owner.ui.qa")])
faculty = env["op.faculty"].search([("company_id", "=", company.id), ("campus_staff_code", "=", "OWNERQA")])
teacher = new_test_user(env, login="learning.faculty.qa", name="QA Learning Faculty", password=os.environ["MVP_QA_PASSWORD"],
    tz="Asia/Kolkata", company_id=company.id, company_ids=[(6, 0, company.ids)], groups="openeducat_core.group_op_faculty")
faculty.partner_id.user_id = teacher
placement = students[0].course_detail_ids
kind = env["grading.assignment.type"].create({"name": "QA assessed exercise"})
task = env["op.assignment"].with_user(teacher).create({"name": "MVP secure programming assignment", "course_id": placement.course_id.id,
    "batch_id": placement.batch_id.id, "subject_id": placement.course_id.subject_ids[:1].id, "faculty_id": faculty.id,
    "assignment_type": kind.id, "description": "Provide an explanation and a tested solution.", "marks": 10, "campus_learning": True,
    "issued_date": fields.Datetime.now() - timedelta(days=1), "submission_date": fields.Datetime.now() + timedelta(days=2), "allocation_ids": [(6, 0, students[:1].ids)]})
task.act_publish()
bank_account = env["account.account"].create({"name": "QA settlement bank", "code": "Q9709", "account_type": "asset_cash", "company_id": company.id})
bank = env["account.journal"].create({"name": "QA settlement bank", "code": "QSB", "type": "bank", "default_account_id": bank_account.id})
bank.inbound_payment_method_line_ids.payment_account_id = bank_account
product = env["product.product"].search([("name", "=", "Tuition installment")], limit=1)
invoices = env["account.move"]
for student in students:
    fee = env["op.student.fees.details"].with_user(owner).create({"student_id": student.id, "amount": 500, "product_id": product.id,
        "course_id": placement.course_id.id, "batch_id": placement.batch_id.id, "campus_year_id": placement.academic_years_id.id,
        "date": fields.Date.today() - timedelta(days=1), "campus_managed": True, "state": "draft"})
    fee.action_campus_post()
    invoices |= fee.invoice_id
env["ir.config_parameter"].sudo().set_param("ideastone.mvp_qa_scenario", json.dumps({"task": task.id, "invoices": invoices.ids, "bank": bank.id, "student": students[0].id}))
env.cr.commit()
print("Finance/coursework QA scenario saved with real invoices, faculty allocation and a published assignment.")
