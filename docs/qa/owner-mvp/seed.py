"""Synthetic Owner demo: run only against the disposable CI database, never production."""
import os
from datetime import datetime, time, timedelta

from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
company = env["res.company"].create({  # noqa: F821
    "name": "QA Demo College — sample data", "campus_demo": True,
    "currency_id": env.ref("base.INR").id, "country_id": env.ref("base.in").id,  # noqa: F821
})
env = env(context=dict(env.context, allowed_company_ids=[company.id], no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
owner = new_test_user(env, login="owner.ui.qa", name="College Owner", password=os.environ["FACULTY_QA_PASSWORD"],
                     company_id=company.id, company_ids=[(6, 0, company.ids)], groups="ideastone_erp.group_mvp_owner,event.group_event_manager")
today = fields.Date.today()
year = env["op.academic.year"].create({"name": str(today.year) + " Academic Year", "code": "OWNERQA", "start_date": today.replace(month=1, day=1), "end_date": today.replace(month=12, day=31), "campus_current": True})
department = env["op.department"].create({"name": "Computer Science", "code": "OWNERQA"})
course = env["op.course"].create({"name": "B.E. Computer Science", "code": "OWNERQA", "department_id": department.id})
term = env["op.academic.term"].create({"name": "Semester I", "academic_year_id": year.id, "term_start_date": year.start_date, "term_end_date": year.end_date})
section = env["op.batch"].create({"name": "CSE A", "code": "OWNERQA", "course_id": course.id, "campus_year_id": year.id, "campus_term_id": term.id, "start_date": year.start_date, "end_date": year.end_date})
subject = env["op.subject"].create({"name": "Programming fundamentals", "code": "OWNERQA", "department_id": department.id})
course.subject_ids = subject
faculty = env["op.faculty"].create({"first_name": "QA", "last_name": "Faculty", "birth_date": "1990-01-01", "gender": "male", "campus_staff_code": "OWNERQA", "main_department_id": department.id,
    "partner_id": env["res.partner"].create({"name": "QA Faculty", "company_id": company.id}).id})
income = env["account.account"].create({"name": "QA Tuition income", "code": "Q9701", "account_type": "income", "company_id": company.id})
receivable = env["account.account"].create({"name": "QA Fees receivable", "code": "Q9702", "account_type": "asset_receivable", "reconcile": True, "company_id": company.id})
cash_account = env["account.account"].create({"name": "QA Cash", "code": "Q9703", "account_type": "asset_cash", "company_id": company.id})
env["account.journal"].create({"name": "QA Tuition invoices", "code": "QAS", "type": "sale", "default_account_id": income.id})
cash = env["account.journal"].create({"name": "QA Cash receipts", "code": "QAC", "type": "cash", "default_account_id": cash_account.id})
cash.inbound_payment_method_line_ids.payment_account_id = cash_account
product = env["product.product"].create({"name": "Tuition installment", "type": "service", "campus_fee_head": True, "property_account_income_id": income.id, "taxes_id": [(5, 0, 0)]})
intake = env["op.admission.register"].create({"name": "CSE intake", "course_id": course.id, "product_id": product.id, "academic_years_id": year.id, "academic_term_id": term.id, "start_date": year.start_date, "end_date": year.end_date, "max_count": 30})
app_model = env["op.admission"].with_user(owner)
students = env["op.student"]
for first, last in [("QA", "Arun"), ("QA", "Meena"), ("QA", "Kavin")]:
    app = app_model.create({"name": first + " " + last, "first_name": first, "last_name": last, "gender": "o", "birth_date": "2005-01-01", "email": last.lower() + "@example.test", "phone": "9000000000",
        "register_id": intake.id, "course_id": course.id, "batch_id": section.id, "campus_managed": True})
    app.action_campus_submit()
    app.action_campus_review()
    app.action_campus_approve()
    app.enroll_student()
    students |= app.student_id
pending = app_model.create({"name": "QA Pending Applicant", "first_name": "QA", "last_name": "Pending", "gender": "o", "birth_date": "2005-01-01", "email": "pending@example.test",
    "register_id": intake.id, "course_id": course.id, "batch_id": section.id, "campus_managed": True})
pending.action_campus_submit()
pending.action_campus_review()
retry = app_model.create({"name": "QA Concurrent Applicant", "first_name": "QA", "last_name": "Concurrent", "gender": "o", "birth_date": "2005-01-01", "email": "concurrent@example.test",
    "register_id": intake.id, "course_id": course.id, "batch_id": section.id, "campus_managed": True})
retry.action_campus_submit()
retry.action_campus_review()
retry.action_campus_approve()
structure = env["op.fees.terms"].create({"name": "CSE first installment", "campus_managed": True, "campus_course_id": course.id, "campus_year_id": year.id,
    "line_ids": [(0, 0, {"campus_product_id": product.id, "campus_amount": 500, "due_date": today + timedelta(days=7)})]})
env["campus.fee.assignment.wizard"].with_user(owner).create({"enrolment_id": students[0].course_detail_ids.id, "structure_id": structure.id}).action_assign()
fee = env["op.student.fees.details"].search([("student_id", "=", students[0].id), ("campus_managed", "=", True)])
students[0].partner_id.property_account_receivable_id = receivable
fee.with_user(owner).action_campus_post()
payment = env["campus.fee.payment.wizard"].with_user(owner).create({"invoice_id": fee.invoice_id.id, "journal_id": cash.id, "amount": 300})
payment.action_pay()
register = env["op.attendance.register"].create({"name": "CSE attendance", "code": "OWNERQA", "course_id": course.id, "batch_id": section.id})
session = env["op.session"].create({"course_id": course.id, "batch_id": section.id, "subject_id": subject.id, "faculty_id": faculty.id,
    "start_datetime": datetime.combine(today, time(10, 0)), "end_datetime": datetime.combine(today, time(11, 0)), "state": "confirm"})
sheet = env["op.attendance.sheet"].with_user(owner).create({"register_id": register.id, "session_id": session.id, "faculty_id": faculty.id, "campus_managed": True})
sheet.action_campus_roster()
sheet.attendance_line[-1].write({"campus_status": "absent"})
sheet.attendance_done()
exam_type = env["op.exam.type"].create({"name": "Internal test", "code": "OWNERQA"})
exam_session = env["op.exam.session"].create({"name": "First internal assessment", "exam_code": "OWNERQA", "course_id": course.id, "batch_id": section.id, "campus_year_id": year.id, "exam_type": exam_type.id, "start_date": today, "end_date": today + timedelta(days=14)})
exam = env["op.exam"].create({"name": "Programming internal assessment", "exam_code": "OWNERQA", "session_id": exam_session.id, "subject_id": subject.id, "campus_managed": True, "responsible_id": [(6, 0, faculty.ids)],
    "total_marks": 100, "min_marks": 40, "start_time": datetime.combine(today + timedelta(days=7), time(14, 0)), "end_time": datetime.combine(today + timedelta(days=7), time(15, 0))})
notice = env["campus.circular"].with_user(owner).create({"name": "Welcome to the new academic year", "reference": "OWNERQA", "body": "<p>Synthetic demo notice. Complete admission and fee formalities before your first class.</p>", "campus_managed": True})
notice.action_campus_publish()

venue = env["res.partner"].create({"name": "QA Main Auditorium", "company_id": company.id})
for offset, name, category in [(4, "QA Freshers’ Day", "Student life"), (9, "QA Innovation Expo", "Technology"),
                               (18, "QA Cultural Fest", "Cultural"), (25, "QA Sports Meet", "Sports")]:
    template = env["event.type"].create({"name": category})
    env["event.event"].create({"name": name, "company_id": company.id, "event_type_id": template.id,
        "date_begin": datetime.combine(today + timedelta(days=offset), time(9, 30)),
        "date_end": datetime.combine(today + timedelta(days=offset), time(16, 0)), "address_id": venue.id,
        "description": "<p>Synthetic campus event for layout verification. Student performances, club showcases and community activities.</p>"})
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:18069")
env.cr.commit()
print("Owner QA demo seeded in company", company.id)
