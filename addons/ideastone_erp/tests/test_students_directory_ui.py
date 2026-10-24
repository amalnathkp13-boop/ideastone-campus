from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestStudentsDirectoryUI(OwnerMVPFixture, TransactionCase):
    def test_navigation_keeps_native_workflows(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        module = next(m for m in dashboard.get_overview()["faculty_modules"] if m["key"] == "students")
        self.assertEqual([i["label"] for i in module["items"]], ["Student directory", "Enrolments & transfers"])
        for item in module["items"]:
            action = dashboard.get_owner_action(item["action"])
            self.assertEqual(action["tag"], "ideastone_erp.students_directory")
            self.assertEqual(dashboard.get_owner_action(item["source_action"])["type"], "ir.actions.act_window")
        with self.assertRaises(AccessError):
            self.env["campus.students.ui"].with_user(self.outsider).get_workspace()

    def test_counts_and_search_use_distinct_saved_students(self):
        app = self.enrolled()
        student = app.student_id
        second = self.env["op.batch"].create({"name": "Other section", "code": "UIQA2", "course_id": self.course.id,
            "campus_year_id": self.year.id, "campus_term_id": self.term.id, "start_date": self.year.start_date, "end_date": self.year.end_date})
        self.env["op.student.course"].create({"student_id": student.id, "course_id": self.course.id, "batch_id": second.id,
            "academic_years_id": self.year.id, "academic_term_id": self.term.id})
        ui = self.env["campus.students.ui"].with_user(self.owner)
        data = ui.get_workspace(filters={"year_id": self.year.id})
        self.assertEqual(data["counts"]["total"], 1)
        dept = next(r for r in data["departments"] if r["id"] == self.department.id)
        self.assertEqual(dept["count"], 1)
        self.assertEqual(dept["capacity"], 100)
        self.assertEqual(dept["sections"], 2)
        self.assertEqual(len(data["rows"]), 1)
        data = ui.get_workspace(filters={"year_id": self.year.id, "department_id": self.department.id, "batch_id": second.id}, query=student.gr_no)
        self.assertEqual(data["rows"][0]["section"], second.name)
        self.assertEqual(len(ui.get_workspace("enrolments", data["filters"])["rows"]), 1)

    def test_status_attention_and_form_permissions(self):
        app = self.enrolled()
        student = app.student_id
        student.write({"phone": False, "mobile": False, "email": False, "campus_status": "on_hold", "campus_status_reason": "Synthetic status check"})
        ui = self.env["campus.students.ui"].with_user(self.owner)
        data = ui.get_workspace(filters={"year_id": self.year.id, "attention": True, "status": "on_hold"})
        self.assertEqual(data["counts"]["attention"], 1)
        self.assertEqual(data["rows"][0]["tone"], "pending")
        self.assertIn("Email", data["rows"][0]["missing"])
        action = ui.get_record_action("student", student.id)
        self.assertEqual(action["res_id"], student.id)
        self.assertEqual(action["views"][0][1], "form")
        before = self.env["op.student.course"].search_count([])
        ui.get_record_action("enrolment", create=True)
        self.assertEqual(self.env["op.student.course"].search_count([]), before)
        with self.assertRaises(AccessError):
            self.env["campus.students.ui"].with_user(self.readonly).get_record_action("enrolment", create=True)

    def test_active_college_isolation_and_filter_validation(self):
        local = self.enrolled().student_id
        other = self.env["res.company"].create({"name": "Other directory college"})
        self.owner.company_ids += other
        foreign = self.env["op.student"].create({"first_name": "Private", "last_name": "Student", "company_id": other.id,
            "partner_id": self.env["res.partner"].create({"name": "Private Student", "company_id": other.id}).id})
        dept = self.env["op.department"].create({"name": "Private department", "code": "UIFOREIGN", "company_id": other.id})
        ui = self.env["campus.students.ui"].with_user(self.owner).with_context(allowed_company_ids=[self.env.company.id,other.id])
        self.assertEqual([r["id"] for r in ui.get_workspace(filters={"year_id": self.year.id})["rows"]], [local.id])
        self.assertNotIn(foreign.id, [r["id"] for r in ui.get_workspace(filters={"year_id": 0}, export=True)["rows"]])
        with self.assertRaises(AccessError):
            ui.get_record_action("student", foreign.id)
        with self.assertRaises(AccessError):
            ui.get_workspace(filters={"department_id": dept.id})
        for filters in ({"study_year": True}, {"capacity": "bad"}, {"attention": "true"}):
            with self.assertRaises(ValidationError):
                ui.get_workspace(filters=filters)
        with self.assertRaises(ValidationError):
            ui.get_record_action("student", True)
