"""Add synthetic student portal scenarios to the disposable Owner CI fixture."""
import base64
import os
from datetime import datetime, time, timedelta

from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
company = env["res.company"].search([("name", "=", "QA Demo College — sample data")])  # noqa: F821
assert len(company) == 1 and company.campus_demo
env = env(context=dict(env.context, allowed_company_ids=company.ids, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
company.write({"campus_student_contact_edit": True, "email": "office@example.test", "phone": "+91 90000 00000"})
students = env["op.student"].search([("company_id", "=", company.id), ("last_name", "in", ["Arun", "Meena"])], order="last_name")
assert len(students) == 2
for login, student in zip(["student.ui.qa", "student.other.qa"], students, strict=True):
    user = new_test_user(env, login=login, name=student.name, partner_id=student.partner_id.id,
                         password=os.environ["STUDENT_QA_PASSWORD"], tz="Asia/Kolkata",
                         company_id=company.id, company_ids=[(6, 0, company.ids)], groups="base.group_portal")
    student.user_id = user
owner = env["res.users"].search([("login", "=", "owner.ui.qa")])
owner.password = os.environ["STUDENT_QA_PASSWORD"]
student = students[0]
placement = student.course_detail_ids
subject = placement.course_id.subject_ids[:1]
faculty = env["op.faculty"].search([("campus_staff_code", "=", "OWNERQA"), ("company_id", "=", company.id)])
today = fields.Date.today()
# A future class on the current day makes the dashboard's drilldown reproducible.
start = datetime.combine(today, time(12, 0))
env["op.session"].create({"course_id": placement.course_id.id, "batch_id": placement.batch_id.id,
    "subject_id": subject.id, "faculty_id": faculty.id, "start_datetime": start, "end_datetime": start + timedelta(minutes=30), "state": "confirm"})
exam = env["op.exam"].search([("exam_code", "=", "OWNERQA"), ("company_id", "=", company.id)])
exam.with_user(owner).action_campus_release_schedule()
grades = env["op.grade.configuration"].create([{"min_per": 0, "max_per": 39, "result": "F"}, {"min_per": 40, "max_per": 100, "result": "P"}])
published = env["op.exam"].create({"name": "Programming foundations — published assessment", "exam_code": "STUDENT-QA",
    "session_id": exam.session_id.id, "subject_id": subject.id, "campus_managed": True,
    "responsible_id": [(6, 0, faculty.ids)], "total_marks": 100, "min_marks": 40,
    "start_time": datetime.combine(today, time(8, 0)), "end_time": datetime.combine(today, time(9, 0)), "campus_grade_ids": [(6, 0, grades.ids)]})
published = published.with_user(owner)
published.action_campus_release_schedule()
published.action_campus_roster()
published.campus_result_ids.write({"marks": 75})
published.action_campus_submit()
published.action_campus_lock()
published.action_campus_publish()
notice = env["campus.circular"].with_user(owner).create({"name": "Student support and certificate desk", "reference": "STUDENT-QA", "audience": "student",
    "body": "<p>The student portal now shows your published attendance, fee receipts and certificate requests. Contact the college office for official record corrections.</p>", "campus_managed": True})
notice.action_campus_publish()
private = env["campus.circular"].with_user(owner).create({"name": "PRIVATE STAFF ONLY", "reference": "STUDENT-QA-PRIVATE", "audience": "faculty", "body": "Internal content", "campus_managed": True})
private.action_campus_publish()
resource = env["campus.digital.resource"].create({"name": "Programming foundations — course guide", "subject_id": subject.id, "batch_ids": [(6, 0, placement.batch_id.ids)],
    "document": base64.b64encode(b"Synthetic approved course guide for student portal QA."), "filename": "course-guide.txt"})
resource.action_submit()
publisher = new_test_user(env, login="student.materials.qa", name="QA Materials Publisher", password=os.environ["STUDENT_QA_PASSWORD"],
    company_id=company.id, company_ids=[(6, 0, company.ids)], groups="ideastone_erp.group_manager")
resource.with_user(publisher).action_approve()
requirement = env["campus.admission.requirement"].create({"name": "QA admission confirmation"})
admission = env["op.admission"].search([("student_id", "=", student.id)], limit=1)
env["campus.admission.document"].create({"admission_id": admission.id, "requirement_id": requirement.id, "filename": "admission-confirmation.txt", "file": base64.b64encode(b"Synthetic admission confirmation.")})
env.cr.commit()
print("Student QA scenarios saved; no production accounts or data used.")
