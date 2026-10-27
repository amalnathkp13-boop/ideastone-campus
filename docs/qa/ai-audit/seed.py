"""Synthetic AI-pack HTTP/browser fixture. Odoo shell, disposable databases only."""
import os
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests import new_test_user

assert env.cr.dbname in {"ci", "campus_ai_audit_20261027"}, "Disposable QA database required"
assert not env["res.users"].search_count([("login", "=", "ai.owner.qa")]), "Already seeded"
company = env["res.company"].create({"name": "AI QA Synthetic College", "campus_demo": True,
    "currency_id": env.ref("base.INR").id, "country_id": env.ref("base.in").id,
    "campus_ai_enabled": True, "campus_ai_endpoint": os.environ["AI_QA_ENDPOINT"],
    "campus_ai_model": "qa-protocol-model", "campus_ai_monthly_limit": 100})
env = env(context=dict(env.context, allowed_company_ids=company.ids, no_reset_password=True,
    mail_create_nosubscribe=True, mail_notrack=True))

def user(login, groups):
    return new_test_user(env, login=login, name=login, password=os.environ["AI_QA_PASSWORD"], groups=groups,
        company_id=company.id, company_ids=[(6, 0, company.ids)], tz="Asia/Kolkata")

owner = user("ai.owner.qa", "ideastone_erp.group_mvp_owner")
mentor = user("ai.mentor.qa", "openeducat_core.group_op_faculty")
hod = user("ai.hod.qa", "ideastone_erp.group_od_hod_approver")
department = env["op.department"].create({"name": "AI QA Computing", "code": "AIQA"})
hod.dept_id = department
course = env["op.course"].create({"name": "AI QA Computer Science", "code": "AIQA", "department_id": department.id})
today = fields.Date.context_today(owner)
year = env["op.academic.year"].create({"name": "AI QA year", "code": "AIQA",
    "start_date": today - timedelta(days=60), "end_date": today + timedelta(days=60)})
term = env["op.academic.term"].create({"name": "AI QA term", "academic_year_id": year.id,
    "term_start_date": year.start_date, "term_end_date": year.end_date})
batch = env["op.batch"].create({"name": "AI QA Section A", "code": "AIQA", "course_id": course.id,
    "campus_year_id": year.id, "campus_term_id": term.id, "start_date": year.start_date, "end_date": year.end_date})
subject = env["op.subject"].create({"name": "AI QA Programming", "code": "AIQA", "department_id": department.id})
course.subject_ids = subject
partner = env["res.partner"].create({"name": "AI QA Mentor", "user_id": mentor.id, "company_id": company.id})
faculty = env["op.faculty"].create({"first_name": "AI QA", "last_name": "Mentor", "gender": "female",
    "birth_date": "1988-01-01", "partner_id": partner.id, "main_department_id": department.id})
students = env["op.student"]
for n in range(1, 4):
    partner = env["res.partner"].create({"name": "PRIVATE_STUDENT_%s" % n,
        "email": "private%s@example.test" % n, "company_id": company.id})
    student = env["op.student"].create({"first_name": "PRIVATE", "last_name": "STUDENT_%s" % n,
        "partner_id": partner.id, "gender": "o", "birth_date": "2007-01-01", "gr_no": "PRIVATE-ID-%s" % n})
    env["op.student.course"].create({"student_id": student.id, "course_id": course.id, "batch_id": batch.id,
        "academic_years_id": year.id, "academic_term_id": term.id,
        "campus_date_from": year.start_date, "state": "running"})
    students |= student
env["campus.student.leave.routing"].create({"name": "AI QA mentor route", "student_id": students[0].id,
    "advisor_id": mentor.id, "hod_id": hod.id})
student_user = user("ai.student.qa", "base.group_portal")
students[0].user_id = student_user
parent = user("ai.parent.qa", "base.group_portal")
parent.is_parent = True
relation = env["op.parent.relationship"].create({"name": "AI QA guardian"})
env["op.parent"].create({"name": parent.partner_id.id, "user_id": parent.id,
    "relationship_id": relation.id, "student_ids": [(6, 0, students[:1].ids)]})
register = env["op.attendance.register"].create({"name": "AI QA attendance", "code": "AIQA", "course_id": course.id, "batch_id": batch.id})
for offset in range(1, 7):
    day = today - timedelta(days=offset)
    session = env["op.session"].create({"course_id": course.id, "batch_id": batch.id, "subject_id": subject.id,
        "faculty_id": faculty.id, "start_datetime": datetime.combine(day, time(9)),
        "end_datetime": datetime.combine(day, time(10)), "state": "confirm"})
    sheet = env["op.attendance.sheet"].create({"register_id": register.id, "session_id": session.id,
        "faculty_id": faculty.id, "attendance_date": day, "campus_managed": True})
    sheet.action_campus_roster()
    sheet.attendance_line.filtered(lambda line: line.student_id == students[0]).write({"campus_status": "absent"})
    sheet.attendance_done()
env["campus.feedback"].create({"name": "AI QA private feedback", "respondent_id": student_user.id,
    "student_id": students[0].id, "kind": "student", "period": "AI QA term", "score": 2,
    "comments": "PRIVATE_PERSON, private.feedback@example.test: library hours and laboratory equipment need review."})
env.cr.commit()
print("AI audit fixture ready; all records synthetic")
