from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestFacultyHome(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        years = self.env["op.academic.year"].search([("company_id", "=", self.env.company.id), ("campus_current", "=", True)])
        years.write({"campus_current": False})
        years.flush_recordset(["campus_current"])
        self.year.campus_current = True
        self.ui = self.env["campus.faculty.home"].with_user(self.teacher)

    def test_navigation_and_unlinked_accounts(self):
        data = self.env["campus.dashboard"].with_user(self.teacher).get_overview()
        self.assertTrue(data["faculty_home_enabled"])
        home = next(module for module in data["faculty_modules"] if module["key"] == "home")
        self.assertIn("My departments", [r["label"] for r in home["items"]])
        self.assertFalse(self.env["campus.dashboard"].with_user(self.owner).get_overview().get("faculty_home_enabled"))
        with self.assertRaises(AccessError):
            self.env["campus.faculty.home"].with_user(self.outsider).get_home()
        self.assertEqual(self.ui.get_home()["counts"]["classes"], 0)
        self.assertEqual(self.ui.get_directory()["students"], [])

    def test_new_allocations_and_enrolments_refresh_in_the_same_directory(self):
        self.session()
        self.assertEqual(self.ui.get_home()["counts"]["students"], 0)
        app = self.enrolled()
        home = self.ui.get_home()
        self.assertEqual((home["counts"]["students"], home["counts"]["subjects"], home["counts"]["classes"]), (1, 1, 1))
        directory = self.ui.get_directory()
        self.assertEqual([r["id"] for r in directory["departments"]], self.department.ids)
        self.assertFalse(directory["students"])
        self.assertEqual(self.ui.get_directory(self.department.id)["years"][0]["id"], 1)
        cohort = self.ui.get_directory(self.department.id, 1)
        self.assertEqual(cohort["sections"][0]["students"], 1)
        roster = self.ui.get_directory(self.department.id, 1, self.section.id)
        self.assertEqual(roster["students"][0]["name"], app.student_id.name)
        self.session(hour=12, state="cancel")
        self.assertEqual(self.ui.get_home()["counts"]["classes"], 1)
        app.student_id.write({"active": False, "campus_status_reason": "Synthetic archive check"})
        self.assertEqual(self.ui.get_directory(self.department.id, 1, self.section.id)["students"], [])

    def test_unallocated_departments_years_sections_and_foreign_colleges_are_denied(self):
        self.session()
        other_department = self.env["op.department"].create({"name": "Unallocated department", "code": "HOME-OTHER"})
        other_section = self.section.copy({"name": "Unallocated section", "code": "HOME-OTHER"})
        other_company = self.env["res.company"].create({"name": "Other faculty home college"})
        foreign = self.env["op.department"].create({"name": "Foreign department", "code": "HOME-FOREIGN", "company_id": other_company.id})
        self.teacher.company_ids += other_company
        ui = self.ui.with_context(allowed_company_ids=[self.env.company.id, other_company.id])
        for args in ((other_department.id,), (foreign.id,), (self.department.id, 4), (self.department.id, 1, other_section.id)):
            with self.assertRaises(AccessError):
                ui.get_directory(*args)
        for invalid in (True, "1", -2, 2147483648):
            with self.assertRaises(ValidationError):
                ui.get_directory(invalid)
        with self.assertRaises(AccessError):
            ui.get_action("take_attendance", 2147483647)
        for kind in ("timetable", "results", "attendance", "tasks", "papers"):
            self.assertIn(ui.get_action(kind)["type"], {"ir.actions.act_window", "ir.actions.client"})

    def test_attendance_and_published_marks_use_existing_workflows(self):
        self.teacher.tz = "Asia/Kolkata"
        app = self.enrolled()
        session = self.session(hour=4)
        with patch("odoo.fields.Datetime.now", return_value=datetime.combine(self.today, time(12))):
            self.assertEqual(self.ui.get_home()["counts"]["pending"], 1)
            sheet = self.sheet(session)
            sheet.action_campus_roster()
            sheet.attendance_done()
            home = self.ui.get_home()
            self.assertEqual(home["counts"]["pending"], 0)
            self.assertEqual(home["attendance"][0]["rate"], 100)
        exam = self.exam()
        exam.action_campus_roster()
        exam.campus_result_ids.write({"marks": 72, "campus_entered": True})
        self.assertEqual(self.ui.get_home()["assessments"], [])
        exam.action_campus_submit()
        exam.action_campus_lock()
        exam.action_campus_publish()
        self.assertEqual(self.ui.get_home()["assessments"][0]["average"], 72)
        self.assertEqual(exam.campus_result_ids.student_id, app.student_id)

    def test_tasks_stay_private_and_stale_academic_years_are_excluded(self):
        self.session()
        self.env["campus.faculty.task"].with_user(self.teacher).create({"name": "Home teaching task"})
        other = new_test_user(self.env, login="home_other_teacher", groups="openeducat_core.group_op_faculty")
        self.env["campus.faculty.task"].with_user(other).create({"name": "Private other task"})
        data = self.ui.get_home()
        self.assertEqual(data["counts"]["tasks"], 1)
        self.assertEqual([r["name"] for r in data["tasks"]], ["Home teaching task"])
        old_year = self.year.copy({"name": "Historic faculty year", "code": "HOME-OLD", "campus_current": False,
            "start_date": self.today - timedelta(days=730), "end_date": self.today - timedelta(days=365)})
        old_section = self.section.copy({"name": "Historic class", "code": "HOME-OLD", "campus_year_id": old_year.id, "campus_term_id": False})
        self.session(hour=15, batch_id=old_section.id)
        self.assertEqual(self.ui.get_home()["counts"]["classes"], 1)
