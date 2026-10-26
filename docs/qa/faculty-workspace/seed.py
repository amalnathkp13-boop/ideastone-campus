"""Disposable CI database only; executed through Odoo shell, never installed as an addon."""
import os
from datetime import timedelta

from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
# Odoo demo data declares a mandatory working day next month; the browser check requests
# leave on the next Monday a week out, which collides with it one week a month.
env["hr.leave.mandatory.day"].sudo().search([]).unlink()  # noqa: F821
user = new_test_user(env, login="faculty.ui.qa", name="QA Faculty",  # noqa: F821
                     password=os.environ["FACULTY_QA_PASSWORD"],
                     groups="openeducat_core.group_op_faculty,openeducat_attendance.group_op_attendance_user,openeducat_exam.group_op_exam_user")
partner = env["res.partner"].create({"name": "QA Faculty", "user_id": user.id, "company_id": env.company.id})  # noqa: F821
faculty = env["op.faculty"].create({"first_name": "QA", "last_name": "Faculty", "gender": "male",  # noqa: F821
                                    "birth_date": "1990-01-01", "partner_id": partner.id})
course = env["op.course"].search([], limit=1)  # noqa: F821
batch = env["op.batch"].create({"name": "QA browser batch", "code": "BROWSERQA",  # noqa: F821
                                "course_id": course.id, "end_date": "2035-12-31"})
subject = env["op.subject"].create({"name": "QA teaching methods", "code": "BROWSERQA"})  # noqa: F821
env["op.session"].create({"course_id": course.id, "batch_id": batch.id, "faculty_id": faculty.id,  # noqa: F821
                           "subject_id": subject.id, "start_datetime": "2035-01-01 10:00:00", "end_datetime": "2035-01-01 11:00:00"})
student_partner = env["res.partner"].create({"name": "QA Learner", "company_id": env.company.id})  # noqa: F821
student = env["op.student"].create({"first_name": "QA", "last_name": "Learner", "gender": "o",  # noqa: F821
                                    "gr_no": "BROWSERQA", "partner_id": student_partner.id})
env["op.student.course"].create({"student_id": student.id, "course_id": course.id, "batch_id": batch.id})  # noqa: F821
assessment = env["campus.faculty.assessment"].with_user(user).create({  # noqa: F821
    "name": "QA Internal Assessment", "student_id": student.id, "subject_id": subject.id,
    "academic_year": "2035-36", "semester": "I", "output_maximum": 25,
    "component_ids": [(0, 0, {"name": "Institution test", "score": 75, "maximum": 100, "weight": 40}),
                      (0, 0, {"name": "Practical", "score": 45, "maximum": 50, "weight": 60})],
})
assessment.write({"state": "done"})
employee = env["hr.employee"].create({"name": "QA Faculty employee", "user_id": user.id})
leave_type = env["hr.leave.type"].create({"name": "QA Casual leave", "sequence": -999,
    "requires_allocation": "yes", "allocation_validation_type": "no", "leave_validation_type": "hr"})
today = fields.Date.today()
for days, first, last in [(10, today - timedelta(days=500), today - timedelta(days=100)),
                          (5, today - timedelta(days=10), today + timedelta(days=365))]:
    allocation = env["hr.leave.allocation"].create({"name": "QA leave allocation", "employee_id": employee.id,
        "holiday_status_id": leave_type.id, "number_of_days": days, "date_from": first, "date_to": last})
    if allocation.state == "draft":
        allocation.action_confirm()
    if allocation.state != "validate":
        allocation.action_validate()
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:18069")  # noqa: F821
env.cr.commit()  # noqa: F821
