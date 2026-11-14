from datetime import timedelta

from odoo.addons.ideastone_erp.tests.test_owner_mvp import OwnerMVPFixture
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPrincipalAttendance(OwnerMVPFixture, TransactionCase):
    def test_faculty_submission_is_visible_only_to_the_principal_in_scope(self):
        principal = new_test_user(self.env, login="attendance.principal", groups="ideastone_principal.group_principal")
        hod = new_test_user(self.env, login="attendance.hod", groups="ideastone_erp.group_od_hod_approver")
        dashboard = self.env["ideastone.principal.attendance"].with_user(principal)
        with self.assertRaises(AccessError):
            dashboard.with_user(self.teacher).get_workspace()
        with self.assertRaises(ValidationError):
            dashboard.get_workspace({"date_from": str(self.today + timedelta(days=1))})
        student = self.enrolled().student_id
        self.env["campus.student.leave.routing"].create({
            "name": "Attendance QA advisor", "student_id": student.id,
            "advisor_id": self.teacher.id, "hod_id": hod.id,
        })
        faculty_ui = self.env["campus.faculty.task.list"].with_user(self.teacher)
        day = str(self.today)
        daily = faculty_ui.get_sop_daily(False, day, "FN")
        values = {str(student.id): {"status": "late", "remark": "Private note"}}
        faculty_ui.save_sop_daily(daily["class_key"], day, "FN", values)
        scope = {"year_id": self.year.id, "department": f"a:{self.department.id}"}
        self.assertFalse(dashboard.get_workspace(scope)["students"])
        faculty_ui.save_sop_daily(daily["class_key"], day, "FN", values, submit=True)
        result = dashboard.get_workspace(scope)["students"]
        self.assertEqual([(row["name"], row["status"], row["source"]) for row in result],
                         [(student.name, "Late", "Mentorship register")])
        self.assertNotIn("Private note", str(result))
        self.assertFalse(dashboard.get_workspace({**scope, "department": "unassigned"})["students"])
