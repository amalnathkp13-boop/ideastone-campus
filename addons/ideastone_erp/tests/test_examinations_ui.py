import base64

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestExaminationsUI(OwnerMVPFixture, TransactionCase):
    def test_navigation_and_missing_marks_publication(self):
        student = self.enrolled().student_id
        exam = self.exam()
        exam.action_campus_roster()
        ui = self.env["campus.examinations.ui"].with_user(self.owner)
        data = ui.get_workspace("marks", {"year_id": self.year.id})
        self.assertEqual(data["counts"]["exams"], 1)
        self.assertEqual(data["counts"]["pass_mark"], 40)
        self.assertEqual(data["counts"]["missing"], 1)
        self.assertIsNone(data["counts"]["pass_rate"])
        self.assertEqual(data["rows"][0]["entered"], 0)
        exam.campus_result_ids.filtered(lambda r: r.student_id == student).write({"marks": 0})
        exam.action_campus_submit()
        exam.action_campus_lock()
        exam.action_campus_publish()
        data = ui.get_workspace("results", {"year_id": self.year.id})
        self.assertEqual(data["counts"]["missing"], 0)
        self.assertEqual(data["counts"]["pass_rate"], 0)
        self.assertEqual(data["counts"]["failure_rate"], 100)
        self.assertEqual(data["rows"][0]["failed"], 1)
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        module = next(m for m in dashboard.get_overview()["faculty_modules"] if m["key"] == "exams")
        self.assertEqual(len(module["items"]), 6)
        for item in module["items"]:
            self.assertEqual(dashboard.get_owner_action(item["action"])["tag"], "ideastone_erp.examinations")
            self.assertEqual(dashboard.get_owner_action(item["source_action"])["type"], "ir.actions.act_window")
        self.assertEqual(ui.get_record_action("marks", exam.id)["res_id"], exam.id)

    def test_active_college_permissions_and_input_validation(self):
        exam = self.exam()
        other = self.env["res.company"].create({"name": "Private examination college"})
        department = self.env["op.department"].create({"name": "Private examination department", "code": "EXPRIVATE", "company_id": other.id})
        self.owner.company_ids += other
        ui = self.env["campus.examinations.ui"].with_user(self.owner).with_context(allowed_company_ids=[self.env.company.id, other.id])
        self.assertEqual([r["id"] for r in ui.get_workspace("marks", {"year_id": self.year.id})["rows"]], [exam.id])
        foreign_grade = self.env["op.grade.configuration"].create({"min_per": 0, "max_per": 100, "result": "Private grade", "company_id": other.id})
        self.assertNotIn(foreign_grade.id, [r["id"] for r in ui.get_workspace("grades")["rows"]])
        with self.assertRaises(AccessError):
            ui.get_record_action("grades", foreign_grade.id)
        with self.assertRaises(AccessError):
            ui.get_workspace("papers", {"paper_department_id": department.id})
        with self.assertRaises(AccessError):
            self.env["campus.examinations.ui"].with_user(self.outsider).get_workspace()
        with self.assertRaises(AccessError):
            self.env["campus.examinations.ui"].with_user(self.readonly).get_record_action("marks")
        for filters in ({"session_id": True}, {"type_id": -1}, {"status": "invented"}, {"paper_period": "invented"}, {"paper_department_id": []}):
            with self.assertRaises(ValidationError):
                ui.get_workspace(filters=filters)
        with self.assertRaises(ValidationError):
            ui.get_record_action("marks", True)

    def test_search_pagination_and_native_create(self):
        exam = self.exam()
        session = exam.session_id
        for n in range(31):
            self.env["op.exam.session"].create({"name": f"Paged examination {n:02}", "exam_code": f"EXUIPG{n}", "course_id": self.course.id,
                "batch_id": self.section.id, "campus_year_id": self.year.id, "exam_type": session.exam_type.id,
                "start_date": self.today, "end_date": self.today})
        ui = self.env["campus.examinations.ui"].with_user(self.owner)
        data = ui.get_workspace("sessions", {"year_id": self.year.id}, "Paged examination")
        self.assertEqual(data["total_rows"], 31)
        self.assertEqual(len(data["rows"]), 30)
        self.assertEqual(len(ui.get_workspace("sessions", {"year_id": self.year.id}, "Paged examination", 1)["rows"]), 1)
        self.assertEqual(ui.get_workspace("sessions", {"year_id": self.year.id}, "Paged examination 30")["total_rows"], 1)
        before = self.env["op.exam"].search_count([])
        self.assertEqual(ui.get_record_action("marks")["views"][0][1], "form")
        self.assertEqual(self.env["op.exam"].search_count([]), before)

    def test_papers_keep_personal_document_permissions(self):
        faculty_group = self.env.ref("openeducat_core.group_op_faculty")
        self.owner.groups_id |= faculty_group
        self.teacher.groups_id |= faculty_group
        document = {"name": "Synthetic question paper", "kind": "question", "filename": "synthetic.pdf",
                    "document": base64.b64encode(b"Synthetic document access check")}
        own = self.env["campus.faculty.document"].with_user(self.owner).create(document)
        private = self.env["campus.faculty.document"].with_user(self.teacher).create(document)
        ui = self.env["campus.examinations.ui"].with_user(self.owner)
        data = ui.get_workspace("papers", {"paper_department_id": 0})
        self.assertEqual([r["id"] for r in data["rows"]], [own.id])
        self.assertFalse(data["rows"][0]["upcoming"])
        self.assertEqual(ui.get_workspace("papers", {"paper_period": "upcoming"})["total_rows"], 0)
        self.assertEqual(ui.get_record_action("papers", own.id)["res_id"], own.id)
        with self.assertRaises(AccessError):
            ui.get_record_action("papers", private.id)
