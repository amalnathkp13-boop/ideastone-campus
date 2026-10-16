from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestVcetWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
        cls.admin = new_test_user(cls.env, login="vcet_qa_admin", groups="ideastone_erp.group_college_admin,ideastone_erp.group_role_approver")
        cls.approver = new_test_user(cls.env, login="vcet_qa_approver", groups="ideastone_erp.group_role_approver")
        cls.teacher = new_test_user(cls.env, login="vcet_qa_teacher", groups="openeducat_attendance.group_op_attendance_user,openeducat_exam.group_op_exam_user")
        cls.other_teacher = new_test_user(cls.env, login="vcet_qa_other", groups="openeducat_attendance.group_op_attendance_user")
        cls.faculty = cls.env["op.faculty"].create({"first_name": "VCET QA", "last_name": "Faculty", "gender": "male", "birth_date": "1990-01-01", "partner_id": cls.env["res.partner"].create({"name": "VCET QA Faculty", "user_id": cls.teacher.id, "company_id": cls.env.company.id}).id})
        cls.collection = cls.env["op.media.type"].create({"name": "QA permitted collection", "code": "QA-A"})
        cls.other_collection = cls.env["op.media.type"].create({"name": "QA other collection", "code": "QA-B"})
        author = cls.env["op.author"].create({"name": "QA author"})
        publisher = cls.env["op.publisher"].create({"name": "QA publisher"})
        book = cls.env["op.media"].create({"name": "QA scoped book", "media_type_id": cls.collection.id, "author_ids": [(4, author.id)], "publisher_ids": [(4, publisher.id)]})
        cls.unit = cls.env["op.media.unit"].create({"name": "QA copy", "media_id": book.id})
        cls.student = cls.env["op.student"].create({"first_name": "QA", "last_name": "Student", "gender": "o", "gr_no": "=FORMULA", "partner_id": cls.env["res.partner"].create({"name": "=QA Student", "company_id": cls.env.company.id}).id})
        kind = cls.env["op.library.card.type"].create({"name": "QA one loan", "allow_media": 1, "duration": 7, "penalty_amt_per_day": 1})
        cls.card = cls.env["op.library.card"].create({"partner_id": cls.student.partner_id.id, "student_id": cls.student.id, "type": "student", "library_card_type_id": kind.id})

    def appointment(self, **changes):
        today = fields.Date.context_today(self.env.user)
        vals = {"faculty_id": self.faculty.id, "media_type_ids": [(6, 0, self.collection.ids)], "date_from": today, "date_to": today + timedelta(days=10), "justification": "QA appointment authority"}
        vals.update(changes)
        return self.env["campus.responsibility"].with_user(self.admin).create(vals)

    def approve(self, rec):
        rec.action_request()
        rec.with_user(self.approver).action_approve()
        return rec

    def test_approval_is_independent_and_cannot_be_forged(self):
        with self.assertRaises(AccessError):
            self.env["campus.responsibility"].with_user(self.teacher).create({"faculty_id": self.faculty.id})
        with self.assertRaises(AccessError):
            self.appointment(state="approved")
        rec = self.appointment()
        rec.action_request()
        with self.assertRaises(AccessError):
            rec.action_approve()
        rec.with_user(self.approver).action_approve()
        self.assertEqual(rec.approved_by, self.approver)
        with self.assertRaises(ValidationError):
            rec.write({"date_to": fields.Date.today()})
        with self.assertRaises(AccessError):
            rec.write({"approved_by": self.admin.id})
        with self.assertRaises(ValidationError):
            rec.unlink()
        self.assertFalse(self.teacher.has_group("account.group_account_invoice"))
        self.assertFalse(self.teacher.has_group("ideastone_erp.group_people"))

    def test_expiry_revocation_and_college_boundaries(self):
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        with self.assertRaises(AccessError):
            desk.get_desk()
        rec = self.approve(self.appointment())
        self.assertTrue(rec.effective)
        self.assertIn(self.unit.id, [u["id"] for u in desk.get_desk()["units"]])
        rec.action_revoke()
        with self.assertRaises(AccessError):
            desk.get_desk()
        yesterday = fields.Date.today() - timedelta(days=1)
        expired = self.approve(self.appointment(date_from=yesterday, date_to=yesterday))
        self.assertFalse(expired.effective)
        with self.assertRaises(AccessError):
            desk.get_desk()
        other = self.env["res.company"].create({"name": "QA other college"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.appointment(company_id=other.id)

    def test_circulation_persists_without_broad_permissions(self):
        self.approve(self.appointment())
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        matches = desk.get_desk("QA scoped book", 0, self.card.number)
        self.assertIn(self.unit.id, [u["id"] for u in matches["units"]])
        self.assertEqual([c["id"] for c in matches["cards"]], self.card.ids)
        desk.issue(self.unit.id, self.card.id)
        self.assertEqual(self.unit.state, "issue")
        loan = self.env["op.media.movement"].search([("media_unit_id", "=", self.unit.id)])
        self.assertEqual(loan.company_id, self.env.company)
        self.assertEqual(loan.state, "issue")
        with self.assertRaises(ValidationError):
            desk.issue(self.unit.id, self.card.id)
        with self.assertRaises(AccessError):
            desk.return_loan(99999999)
        desk.return_loan(loan.id)
        self.assertEqual(self.unit.state, "available")
        self.assertEqual(loan.state, "return_done")
        rec = self.env["campus.responsibility"].search([("faculty_id", "=", self.faculty.id)])
        rec.with_user(self.admin).action_revoke()
        with self.assertRaises(AccessError):
            desk.return_loan(loan.id)

    def test_out_of_scope_collection_and_college_rejected(self):
        self.approve(self.appointment())
        book = self.unit.media_id.copy({"name": "Other collection", "media_type_id": self.other_collection.id})
        unit = self.env["op.media.unit"].create({"name": "Other copy", "media_id": book.id})
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        with self.assertRaises(AccessError):
            desk.issue(unit.id, self.card.id)
        other = self.env["res.company"].create({"name": "QA foreign library"})
        foreign = self.unit.copy({"name": "Foreign copy", "campus_company_id": other.id})
        with self.assertRaises(AccessError):
            desk.issue(foreign.id, self.card.id)
        self.assertNotIn(foreign.id, [u["id"] for u in desk.get_desk()["units"]])

    def test_attendance_export_scope_snapshot_and_csv(self):
        course = self.env["op.course"].search([], limit=1)
        batch = self.env["op.batch"].create({"name": "QA batch", "code": "VCETQA", "course_id": course.id, "end_date": fields.Date.today() + timedelta(days=30)})
        register = self.env["op.attendance.register"].create({"name": "QA register", "code": "VCET-QA", "course_id": course.id, "batch_id": batch.id})
        for faculty_id, present, state in [(self.faculty.id, True, "done"), (False, False, "done"), (self.faculty.id, False, "draft")]:
            sheet = self.env["op.attendance.sheet"].create({"register_id": register.id, "faculty_id": faculty_id, "attendance_date": fields.Date.today(), "state": state})
            self.env["op.attendance.line"].create({"attendance_id": sheet.id, "student_id": self.student.id, "present": present})
        wizard = self.env["campus.attendance.export.wizard"].with_user(self.teacher).create({"date_from": fields.Date.today(), "date_to": fields.Date.today(), "academic_year": "2026-27", "semester": "V"})
        export = wizard._snapshot().with_user(self.teacher)
        self.assertEqual(export.snapshot["sessions"], 1)
        self.assertEqual(export.snapshot["present"], 1)
        self.assertEqual(export.snapshot["shortage"], 0)
        import base64
        csv = base64.b64decode(export.csv_file).decode("utf-8-sig")
        self.assertIn("'=FORMULA", csv)
        with self.assertRaises(AccessError):
            export.with_user(self.other_teacher).read(["snapshot"])
        with self.assertRaises(AccessError):
            export.write({"name": "Forged"})
        with self.assertRaises(AccessError):
            self.env["campus.attendance.export"].with_user(self.teacher).create({"name": "Forged"})
        html, _kind = self.env["ir.actions.report"].with_user(self.teacher)._render_qweb_html("ideastone_erp.report_attendance_export", export.ids)
        self.assertIn(b"Attendance Shortage Report", html)
        self.assertIn(b"DRAFT", html)

    def test_faculty_cannot_publish_or_edit_other_attendance(self):
        exam = self.env["op.exam"].search([], limit=1)
        self.assertTrue(exam)
        with self.assertRaises(AccessError):
            exam.with_user(self.teacher).act_done()
        exam.write({"state": "done"})
        result = self.env["op.result.line"].create({"exam_id": exam.id, "student_id": self.student.id, "marks": exam.min_marks})
        with self.assertRaises(AccessError):
            result.with_user(self.teacher).write({"marks": exam.total_marks})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            result.write({"marks": exam.total_marks + 1})
        sheet = self.env["op.attendance.sheet"].search([], limit=1)
        self.assertTrue(sheet)
        with self.assertRaises(AccessError):
            sheet.with_user(self.teacher).write({"state": "done"})

    def test_workspace_uses_authenticated_role(self):
        overview = self.env["campus.dashboard"].with_user(self.teacher).get_overview()
        self.assertEqual(overview["workspace_role"], "Faculty")
        self.assertFalse(overview["is_admin"])
        self.assertNotIn("access", [p["key"] for p in overview["pages"]])
        self.assertFalse(overview["library_allowed"])
        with self.assertRaises(AccessError):
            self.env["campus.library.desk"].with_user(self.other_teacher).get_desk()
