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
    "body": "<p><span style='color:#ff00ff;font-family:Courier New;font-size:30px'>The student portal now shows your published attendance, fee receipts and certificate requests.</span> Contact the college office for official record corrections.</p>", "campus_category": "Event", "campus_managed": True, "campus_portal_priority": "important"})
notice.action_campus_publish()
private = env["campus.circular"].with_user(owner).create({"name": "PRIVATE STAFF ONLY", "reference": "STUDENT-QA-PRIVATE", "audience": "faculty", "body": "Internal content", "campus_managed": True})
private.action_campus_publish()
event_start = datetime.combine(today + timedelta(days=1), time(12))
env["event.event"].create({"name": "Student campus cultural event QA", "company_id": company.id, "website_id": False,
    "date_begin": event_start, "date_end": event_start + timedelta(hours=2), "is_published": True,
    "description": "<p>Published student event for calendar QA.</p>"})
env["event.event"].create({"name": "PRIVATE DRAFT EVENT QA", "company_id": company.id, "website_id": False,
    "date_begin": event_start, "date_end": event_start + timedelta(hours=2), "is_published": False})
resource = env["campus.digital.resource"].create({"name": "Programming foundations — course guide", "subject_id": subject.id, "batch_ids": [(6, 0, placement.batch_id.ids)],
    "document": base64.b64encode(b"Synthetic approved course guide for student portal QA."), "filename": "course-guide.txt"})
resource.action_submit()
publisher = new_test_user(env, login="student.materials.qa", name="QA Materials Publisher", password=os.environ["STUDENT_QA_PASSWORD"],
    company_id=company.id, company_ids=[(6, 0, company.ids)], groups="ideastone_erp.group_manager")
resource.with_user(publisher).action_approve()
requirement = env["campus.admission.requirement"].create({"name": "QA admission confirmation"})
admission = env["op.admission"].search([("student_id", "=", student.id)], limit=1)
env["campus.admission.document"].create({"admission_id": admission.id, "requirement_id": requirement.id, "filename": "admission-confirmation.txt", "file": base64.b64encode(b"Synthetic admission confirmation.")})
# Physical library records for the student-facing catalogue and renewal checks.
library_author = env["op.author"].create({"name": "Student Library QA Author"})
library_publisher = env["op.publisher"].create({"name": "Student Library QA Publisher"})
library_books = env["op.media"].create([{"name": title, "internal_code": code,
    "author_ids": [(4, library_author.id)], "publisher_ids": [(4, library_publisher.id)], "subject_ids": [(4, subject.id)]}
    for title, code in [("Student Library QA Programming", "STUDENT-LIB-1"), ("Student Library QA Reference", "STUDENT-LIB-2")]])
library_units = env["op.media.unit"].create([{"name": book.name + " copy", "media_id": book.id, "campus_company_id": company.id} for book in library_books])
library_card_type = env["op.library.card.type"].create({"name": "Student Library QA Card", "allow_media": 3, "duration": 7, "penalty_amt_per_day": 1})
library_card = env["op.library.card"].create({"partner_id": student.partner_id.id, "student_id": student.id,
    "type": "student", "library_card_type_id": library_card_type.id})
library_loan = env["op.media.movement"].create({"media_id": library_books[0].id, "media_unit_id": library_units[0].id,
    "library_card_id": library_card.id, "type": "student", "student_id": student.id, "company_id": company.id,
    "issued_date": today - timedelta(days=10), "return_date": today - timedelta(days=3)})
library_loan.issue_media()

env.cr.commit()
print("Student QA scenarios saved; no production accounts or data used.")
