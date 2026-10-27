from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAcademicsUI(OwnerMVPFixture, TransactionCase):
    def test_navigation_and_saved_records_use_the_academic_workspace(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        module = next(m for m in dashboard.get_overview()["faculty_modules"] if m["key"] == "academics")
        self.assertEqual(len(module["items"]), 7)
        for item in module["items"]:
            action = dashboard.get_owner_action(item["action"])
            self.assertEqual(action["tag"], "ideastone_erp.academics")
            self.assertEqual(action["context"]["campus_module"], "academics")
            if item.get("source_action"):
                self.assertEqual(dashboard.get_owner_action(item["source_action"])["type"], "ir.actions.act_window")
        ui = self.env["campus.academics.ui"].with_user(self.owner)
        before = len(ui.get_workspace()["rows"]["departments"])
        dept = ui.save_record("departments", {"name": "Saved academic department", "code": "ACS-QA", "campus_academic_area": "engineering", "active": True})
        course = ui.save_record("programmes", {"name": "Saved academic programme", "code": "ACS-QA", "department_id": dept, "campus_level": "undergraduate", "campus_duration": 8})
        year = ui.save_record("years", {"name": "Saved academic year", "code": "ACS-QA", "start_date": "2027-07-01", "end_date": "2028-06-30", "campus_current": False})
        term = ui.save_record("semesters", {"name": "Semester I", "academic_year_id": year, "campus_course_id": course, "campus_sequence": 1, "term_start_date": "2027-07-01", "term_end_date": "2027-12-31"})
        section = ui.save_record("sections", {"name": "Saved academic section", "code": "ACS-QA", "course_id": course, "campus_year_id": year, "campus_term_id": term, "start_date": "2027-07-01", "end_date": "2028-06-30"})
        subject = ui.save_record("curriculum", {"name": "Saved academic subject", "code": "ACS-QA", "department_id": dept, "campus_term_id": term, "campus_credits": 3.5})
        ui.save_record("curriculum", {"campus_credits": 4}, subject)
        data = ui.get_workspace()
        self.assertEqual(len(data["rows"]["departments"]), before + 1)
        for key, record_id in (("years", year), ("programmes", course), ("semesters", term), ("sections", section), ("curriculum", subject)):
            self.assertIn(record_id, [r["id"] for r in data["rows"][key]])
        self.assertEqual(next(r for r in data["rows"]["curriculum"] if r["id"] == subject)["credits"], 4)
        self.assertTrue(next(r for r in data["rows"]["sections"] if r["id"] == section)["mapped"])

    def test_current_year_changes_are_atomic_and_counts_use_saved_sources(self):
        ui = self.env["campus.academics.ui"].with_user(self.owner)
        ui.save_record("years", {"campus_current": True}, self.year.id)
        app = self.enrolled()
        data = ui.get_workspace()
        self.assertEqual(data["current"]["id"], self.year.id)
        self.assertIn(app.student_id.id, self.env["op.student.course"].search([("academic_years_id", "=", self.year.id)]).student_id.ids)
        dept = next(r for r in data["rows"]["departments"] if r["id"] == self.department.id)
        self.assertEqual((dept["students"], dept["capacity"], dept["sections"]), (1, 100, 1))
        self.assertEqual(dept["section_rows"][0]["students"], 1)
        year = ui.save_record("years", {"name": "Next current year", "code": "ACS-NEXT", "start_date": "2030-01-01", "end_date": "2030-12-31", "campus_current": True})
        self.assertEqual(ui.get_workspace()["current"]["id"], year)
        self.assertFalse(self.year.campus_current)
        self.assertEqual(ui.get_workspace()["counts"]["students"], 0)

    def test_active_college_scope_permissions_and_input_validation(self):
        foreign_company = self.env["res.company"].create({"name": "Foreign academic college"})
        foreign = self.env["op.department"].create({"name": "Private foreign department", "code": "ACS-FOREIGN", "company_id": foreign_company.id})
        self.owner.company_ids += foreign_company
        ui = self.env["campus.academics.ui"].with_user(self.owner).with_context(allowed_company_ids=[self.env.company.id, foreign_company.id])
        self.assertNotIn(foreign.id, [r["id"] for r in ui.get_workspace()["rows"]["departments"]])
        with self.assertRaises(AccessError):
            ui.save_record("departments", {"name": "Changed"}, foreign.id)
        with self.assertRaises(AccessError):
            ui.save_record("programmes", {"name": "Cross college", "code": "ACS-CROSS", "department_id": foreign.id})
        for user in (self.outsider, self.teacher):
            with self.assertRaises(AccessError):
                self.env["campus.academics.ui"].with_user(user).get_workspace()
        readonly = self.env["campus.academics.ui"].with_user(self.readonly)
        self.assertFalse(readonly.get_workspace()["can_edit"])
        with self.assertRaises(AccessError):
            readonly.save_record("departments", {"name": "Denied", "code": "DENIED"})
        for invalid in (True, "1", -1, 2147483648):
            with self.assertRaises(ValidationError):
                ui.save_record("departments", {"name": "Invalid"}, invalid)
        for view, vals in (("unknown", {}), ("curriculum", {"company_id": foreign_company.id}), ("curriculum", {"campus_credits": -1}), ("departments", {"campus_academic_area": "invented"})):
            with self.assertRaises(ValidationError):
                ui.save_record(view, vals)

    def test_missing_delivery_is_not_invented_and_invalid_mapping_rolls_back(self):
        ui = self.env["campus.academics.ui"].with_user(self.owner)
        ui.save_record("years", {"campus_current": True}, self.year.id)
        data = ui.get_workspace()
        self.assertIsNone(data["counts"]["coverage"])
        self.assertTrue(all(r["progress"] is None for r in data["trend"]))
        self.owner.groups_id += self.env.ref("ideastone_erp.group_academic")
        self.env["campus.teaching.plan"].create({"name": "Recorded academic delivery", "faculty_id": self.faculty.id,
            "subject_id": self.subject.id, "batch_id": self.section.id, "term_id": self.term.id,
            "planned_date": self.today, "unit": "1", "topic": "Recorded topic", "planned_hours": 5,
            "execution_date": self.today, "actual_hours": 2.5, "notes": "Recorded execution"})
        self.assertEqual(ui.get_workspace()["counts"]["coverage"], 50)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            ui.save_record("semesters", {"name": "Invalid dates", "academic_year_id": self.year.id, "term_start_date": "1990-01-01", "term_end_date": "1990-12-31"})
        with self.assertRaises(ValidationError):
            ui.save_record("semesters", {"name": "Invalid sequence", "academic_year_id": self.year.id, "campus_course_id": self.course.id, "campus_sequence": 9, "term_start_date": str(self.year.start_date), "term_end_date": str(self.year.end_date)})
