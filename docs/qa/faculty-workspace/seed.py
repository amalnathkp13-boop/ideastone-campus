"""Disposable CI database only; executed through Odoo shell, never installed as an addon."""
import os

from odoo.tests import new_test_user

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
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
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:18069")  # noqa: F821
env.cr.commit()  # noqa: F821
