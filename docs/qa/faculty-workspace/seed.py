"""Disposable CI database only; executed through Odoo shell, never installed as an addon."""
import os

from odoo.tests import new_test_user

assert env.cr.dbname == "ci", "Disposable CI database required"  # noqa: F821
user = new_test_user(env, login="faculty.ui.qa", name="QA Faculty",  # noqa: F821
                     password=os.environ["FACULTY_QA_PASSWORD"],
                     groups="openeducat_core.group_op_faculty,openeducat_attendance.group_op_attendance_user,openeducat_exam.group_op_exam_user")
partner = env["res.partner"].create({"name": "QA Faculty", "user_id": user.id, "company_id": env.company.id})  # noqa: F821
env["op.faculty"].create({"first_name": "QA", "last_name": "Faculty", "gender": "male",  # noqa: F821
                          "birth_date": "1990-01-01", "partner_id": partner.id})
env.cr.commit()  # noqa: F821
