import base64
from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestOwnerMVP(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
        cls.today = fields.Date.today()
        cls.owner = new_test_user(cls.env, login="mvp_owner", groups="ideastone_erp.group_mvp_owner")
        cls.admissions = new_test_user(cls.env, login="mvp_admissions", groups="ideastone_erp.group_mvp_admissions")
        cls.accountant = new_test_user(cls.env, login="mvp_accountant", groups="ideastone_erp.group_mvp_accountant")
        cls.examiner = new_test_user(cls.env, login="mvp_examiner", groups="ideastone_erp.group_mvp_exams")
        cls.readonly = new_test_user(cls.env, login="mvp_readonly", groups="ideastone_erp.group_mvp_readonly")
        cls.outsider = new_test_user(cls.env, login="mvp_outsider", groups="base.group_user")
        cls.teacher = new_test_user(cls.env, login="mvp_teacher", groups="openeducat_attendance.group_op_attendance_user,openeducat_exam.group_op_exam_user")
        cls.year = cls.env["op.academic.year"].create({"name": "MVP academic year", "code": "MVP-QA", "start_date": cls.today.replace(month=1, day=1), "end_date": cls.today.replace(month=12, day=31)})
        cls.department = cls.env["op.department"].create({"name": "MVP department", "code": "MVPQA"})
        cls.course = cls.env["op.course"].create({"name": "MVP programme", "code": "MVPQA", "department_id": cls.department.id})
        cls.term = cls.env["op.academic.term"].create({"name": "MVP semester", "academic_year_id": cls.year.id, "campus_course_id": cls.course.id, "term_start_date": cls.year.start_date, "term_end_date": cls.year.end_date})
        cls.section = cls.env["op.batch"].create({"name": "MVP section", "code": "MVPQA", "course_id": cls.course.id, "campus_year_id": cls.year.id, "campus_term_id": cls.term.id, "start_date": cls.year.start_date, "end_date": cls.year.end_date})
        cls.subject = cls.env["op.subject"].create({"name": "MVP subject", "code": "MVPQA", "department_id": cls.department.id})
        cls.course.subject_ids = cls.subject
        cls.faculty = cls.env["op.faculty"].create({"first_name": "MVP", "last_name": "Faculty", "gender": "male", "birth_date": "1990-01-01", "main_department_id": cls.department.id,
            "partner_id": cls.env["res.partner"].create({"name": "MVP Faculty", "user_id": cls.teacher.id, "company_id": cls.env.company.id}).id})
        cls.income = cls.env["account.account"].create({"name": "MVP fee income", "code": "MVP9701", "account_type": "income", "company_id": cls.env.company.id})
        cls.receivable = cls.env["account.account"].create({"name": "MVP receivable", "code": "MVP9702", "account_type": "asset_receivable", "reconcile": True, "company_id": cls.env.company.id})
        cls.cash_account = cls.env["account.account"].create({"name": "MVP cash", "code": "MVP9703", "account_type": "asset_cash", "company_id": cls.env.company.id})
        cls.sales_journal = cls.env["account.journal"].create({"name": "MVP sales", "code": "MQAS", "type": "sale", "default_account_id": cls.income.id})
        cls.cash_journal = cls.env["account.journal"].create({"name": "MVP cash", "code": "MQAC", "type": "cash", "default_account_id": cls.cash_account.id})
        cls.cash_journal.inbound_payment_method_line_ids.payment_account_id = cls.cash_account
        cls.product = cls.env["product.product"].create({"name": "MVP tuition", "type": "service", "campus_fee_head": True, "property_account_income_id": cls.income.id, "taxes_id": [(5, 0, 0)]})
        cls.intake = cls.env["op.admission.register"].create({"name": "MVP intake", "course_id": cls.course.id, "academic_years_id": cls.year.id, "academic_term_id": cls.term.id,
            "product_id": cls.product.id, "start_date": cls.year.start_date, "end_date": cls.year.end_date, "max_count": 100})

    def application(self):
        return self.env["op.admission"].with_user(self.admissions).create({"name": "MVP Applicant", "first_name": "MVP", "last_name": "Applicant", "email": "applicant@example.test", "phone": "9000000000",
            "birth_date": "2005-01-01", "gender": "o", "course_id": self.course.id, "batch_id": self.section.id, "register_id": self.intake.id, "campus_managed": True})

    def enrolled(self):
        app = self.application()
        app.action_campus_submit()
        app.action_campus_review()
        app.action_campus_approve()
        app.enroll_student()
        return app.sudo()

    def session(self, hour=10, **changes):
        vals = {"course_id": self.course.id, "batch_id": self.section.id, "subject_id": self.subject.id, "faculty_id": self.faculty.id,
                "start_datetime": datetime.combine(self.today, time(hour, 0)), "end_datetime": datetime.combine(self.today, time(hour + 1, 0)), "state": "confirm"}
        vals.update(changes)
        return self.env["op.session"].create(vals)

    def sheet(self, session):
        register = self.env["op.attendance.register"].create({"name": "MVP register", "code": "MVPQA", "course_id": self.course.id, "batch_id": self.section.id})
        return self.env["op.attendance.sheet"].with_user(self.teacher).create({"register_id": register.id, "session_id": session.id, "faculty_id": self.faculty.id, "campus_managed": True})

    def fee(self, student, amount=500):
        student.partner_id.property_account_receivable_id = self.receivable
        return self.env["op.student.fees.details"].with_user(self.accountant).create({"student_id": student.id, "amount": amount, "product_id": self.product.id,
            "course_id": self.course.id, "batch_id": self.section.id, "campus_year_id": self.year.id, "date": self.today, "campus_managed": True, "state": "draft"})

    def payment(self, invoice, amount):
        wizard = self.env["campus.fee.payment.wizard"].with_user(self.accountant).create({"invoice_id": invoice.id, "amount": amount, "journal_id": self.cash_journal.id})
        wizard.action_pay()
        return wizard

    def exam(self):
        kind = self.env["op.exam.type"].create({"name": "MVP internal", "code": "MVPQA"})
        session = self.env["op.exam.session"].create({"name": "MVP exam session", "exam_code": "MVPQA", "course_id": self.course.id, "batch_id": self.section.id,
            "campus_year_id": self.year.id, "exam_type": kind.id, "start_date": self.today, "end_date": self.today})
        grades = self.env["op.grade.configuration"].create([{"min_per": 0, "max_per": 39, "result": "F"}, {"min_per": 40, "max_per": 100, "result": "P"}])
        return self.env["op.exam"].create({"name": "MVP exam", "exam_code": "MVPQA", "session_id": session.id, "subject_id": self.subject.id, "total_marks": 100, "min_marks": 40,
            "start_time": datetime.combine(self.today, time(14, 0)), "end_time": datetime.combine(self.today, time(15, 0)),
            "responsible_id": [(6, 0, self.faculty.ids)], "campus_managed": True, "campus_grade_ids": [(6, 0, grades.ids)]})

    def test_admission_document_gate_conversion_retry_and_audit(self):
        requirement = self.env["campus.admission.requirement"].create({"name": "School certificate"})
        app = self.application()
        with self.assertRaises(ValidationError):
            app.enroll_student()
        app.action_campus_submit()
        app.action_campus_review()
        with self.assertRaises(ValidationError):
            app.action_campus_approve()
        doc = self.env["campus.admission.document"].with_user(self.admissions).create({"admission_id": app.id, "requirement_id": requirement.id, "filename": "certificate.txt", "file": base64.b64encode(b"Synthetic QA document")})
        doc.action_verify()
        app.action_campus_approve()
        app.enroll_student()
        student, enrolment = app.student_id, app.campus_enrolment_id
        app.enroll_student()
        self.assertEqual(app.student_id, student)
        self.assertEqual(app.campus_enrolment_id, enrolment)
        self.assertTrue(student.gr_no.startswith("STU/"))
        self.assertEqual(enrolment.academic_years_id, self.year)
        self.assertEqual(len(student.course_detail_ids), 1)
        self.assertTrue(self.env["campus.mvp.audit"].search([("model_name", "=", "op.admission"), ("record_id", "=", app.id)]))
        with self.assertRaises(AccessError):
            app.write({"campus_stage": "enrolled"})
        with self.assertRaises(ValidationError):
            student.unlink()

    def test_timetable_conflict_and_adjacent_session(self):
        self.session()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.session(start_datetime=datetime.combine(self.today, time(9, 30)), end_datetime=datetime.combine(self.today, time(10, 30)))
        self.assertTrue(self.session(hour=11))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.session(hour=12, end_datetime=datetime.combine(self.today, time(12, 0)))

    def test_attendance_submission_correction_and_history(self):
        student = self.enrolled().student_id
        sheet = self.sheet(self.session())
        sheet.action_campus_roster()
        sheet.action_campus_roster()
        self.assertEqual(sheet.attendance_line.student_id, student)
        self.assertEqual(len(sheet.attendance_line), 1)
        sheet.attendance_line.write({"campus_status": "late"})
        sheet.attendance_done()
        with self.assertRaises(ValidationError):
            sheet.attendance_line.write({"present": False})
        with self.assertRaises(AccessError):
            sheet.attendance_draft()
        corrected = sheet.with_user(self.owner)
        corrected.campus_correction_reason = "Student was excused after medical review"
        corrected.attendance_draft()
        corrected.attendance_line.write({"campus_status": "excused"})
        corrected.attendance_done()
        self.assertEqual(sheet.attendance_line.campus_status, "excused")
        summary = self.env["campus.dashboard"].with_user(self.owner)._attendance_rows(sheet.attendance_line)
        self.assertFalse(summary)  # default policy excludes excused sessions
        self.env.company.campus_excused_policy = "present"
        self.assertEqual(self.env["campus.dashboard"]._attendance_rows(sheet.attendance_line)[0]["rate"], 100)
        with self.assertRaises(ValidationError):
            student.course_detail_ids.write({"batch_id": False})

    def test_partial_final_payment_reversal_and_unique_receipts(self):
        fee = self.fee(self.enrolled().student_id)
        fee.action_campus_post()
        invoice = fee.invoice_id
        self.assertEqual(invoice.amount_residual, 500)
        first = self.payment(invoice, 300)
        self.assertEqual(invoice.amount_residual, 200)
        first.action_pay()  # retry cannot create a second payment
        self.assertEqual(invoice.amount_residual, 200)
        second = self.payment(invoice, 200)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertNotEqual(first.payment_id.campus_receipt_number, second.payment_id.campus_receipt_number)
        with self.assertRaises(ValidationError):
            first.payment_id.write({"amount": 1})
        first.payment_id.campus_reversal_reason = "Duplicate collection corrected"
        first.payment_id.action_campus_reverse()
        self.assertEqual(invoice.amount_residual, 300)
        first.payment_id.action_campus_reverse()
        self.assertEqual(invoice.amount_residual, 300)
        html, _ = self.env["ir.actions.report"]._render_qweb_html("ideastone_erp.mvp_receipt_document", first.payment_id.ids)
        self.assertIn(b"REVERSED RECEIPT", html)
        with self.assertRaises(ValidationError):
            first.payment_id.unlink()

    def test_overpayment_and_concession_authority(self):
        fee = self.fee(self.enrolled().student_id)
        fee.write({"campus_concession": 50, "campus_concession_reason": "Approved scholarship"})
        with self.assertRaises(AccessError):
            fee.action_campus_concession()
        fee.with_user(self.owner).action_campus_concession()
        fee.action_campus_post()
        self.assertEqual(fee.invoice_id.amount_total, 450)
        with self.assertRaises(ValidationError):
            self.payment(fee.invoice_id, 451)

    def test_exam_missing_marks_lock_publish_and_reasoned_reopen(self):
        self.enrolled()
        exam = self.exam().with_user(self.teacher)
        exam.action_campus_roster()
        self.assertFalse(exam.campus_result_ids.campus_entered)
        self.assertFalse(exam.campus_result_ids.status)
        with self.assertRaises(ValidationError):
            exam.action_campus_submit()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            exam.campus_result_ids.write({"marks": 101})
        exam.campus_result_ids.write({"marks": 75})
        exam.action_campus_submit()
        with self.assertRaises(ValidationError):
            exam.campus_result_ids.write({"marks": 90})
        with self.assertRaises(AccessError):
            exam.action_campus_lock()
        officer = exam.with_user(self.examiner)
        officer.action_campus_lock()
        officer.action_campus_publish()
        self.assertEqual(exam.campus_result_ids.grade, "P")
        with self.assertRaises(ValidationError):
            officer.campus_grade_ids[:1].write({"result": "Changed after publication"})
        with self.assertRaises(ValidationError):
            officer.campus_result_ids.write({"marks": 60})
        officer.campus_reopen_reason = "Approved revaluation request"
        officer.action_campus_reopen()
        exam.campus_result_ids.write({"marks": 80})
        self.assertEqual(exam.campus_result_ids.marks, 80)
        self.assertTrue(self.env["campus.mvp.audit"].search([("name", "=", "Examination reopened"), ("record_id", "=", exam.id)]))

    def test_foreign_college_and_unassigned_faculty_are_denied(self):
        self.enrolled()
        exam = self.exam()
        teacher = new_test_user(self.env, login="mvp_unassigned_teacher", groups="openeducat_exam.group_op_exam_user")
        with self.assertRaises(AccessError):
            exam.with_user(teacher).read(["name"])
        other = self.env["res.company"].create({"name": "MVP foreign college"})
        foreign = self.env["op.academic.year"].with_company(other).create({"name": "Foreign academic year", "start_date": self.year.start_date, "end_date": self.year.end_date})
        with self.assertRaises(AccessError):
            foreign.with_user(self.owner).with_context(allowed_company_ids=[self.env.company.id]).read(["name"])

    def test_role_boundaries_and_readonly_dashboard(self):
        app = self.enrolled()
        with self.assertRaises(AccessError):
            app.with_user(self.accountant).write({"name": "Unauthorized edit"})
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.outsider).get_owner_metrics()
        with self.assertRaises(AccessError):
            app.student_id.with_user(self.readonly).write({"first_name": "Changed"})
        with self.assertRaises(AccessError):
            self.env["op.result.line"].with_user(self.accountant).create({"marks": 50})
        overview = self.env["campus.dashboard"].with_user(self.readonly).get_overview()
        self.assertEqual(overview["faculty_modules"][0]["label"], "Dashboard")
        self.env["campus.dashboard"].with_user(self.readonly).get_owner_metrics()
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.readonly).get_owner_action("base.action_res_users")

    def test_dashboard_kpi_reconciles_with_saved_records_and_source(self):
        app = self.enrolled()
        fee = self.fee(app.student_id)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 300)
        dash = self.env["campus.dashboard"].with_user(self.owner)
        filters = {"date_from": str(self.today), "date_to": str(self.today), "year_id": self.year.id}
        metrics = dash.get_owner_metrics(filters)
        cards = {s["label"]: s for s in metrics["stats"]}
        self.assertEqual(cards["Active students"]["value"], 1)
        self.assertEqual(cards["Applications"]["value"], 1)
        self.assertIn("300.00", cards["Net fees collected"]["value"])
        self.assertIn("200.00", cards["Outstanding fees"]["value"])
        action = dash.get_owner_source_action("active_students", filters)
        self.assertEqual(self.env[action["res_model"]].search_count(action["domain"]), 1)
        self.assertEqual(sum(p["value"] for p in metrics["programmes"]), 1)

    def test_import_preview_duplicates_and_atomic_commit(self):
        payload = "student_number,first_name,last_name,phone,section_code\nMVP-IMPORT,QA,Imported,9000000001,MVPQA\n"
        wizard = self.env["campus.student.import"].with_user(self.owner).create({"file": base64.b64encode(payload.encode())})
        with self.assertRaises(ValidationError):
            wizard.action_commit()
        wizard.action_preview()
        self.assertTrue(wizard.checksum)
        wizard.action_commit()
        wizard.action_commit()
        self.assertEqual(self.env["op.student"].search_count([("gr_no", "=", "MVP-IMPORT")]), 1)
        duplicate = self.env["campus.student.import"].with_user(self.owner).create({"file": base64.b64encode(payload.encode())})
        duplicate.action_preview()
        self.assertFalse(duplicate.checksum)
        self.assertIn("duplicate", duplicate.preview)

    def test_notice_publication_schedule_and_csv_permissions(self):
        notice = self.env["campus.circular"].with_user(self.owner).create({"name": "MVP notice", "reference": "MVPQA", "body": "<p>In-app QA notice</p>", "campus_managed": True})
        notice.action_campus_publish()
        self.assertEqual(notice.campus_status, "published")
        report = self.env["campus.mvp.report"].with_user(self.readonly).create({"kind": "admissions"})
        report.action_csv()
        self.assertIn(b"No records", base64.b64decode(report.file))
        future = notice.sudo().copy({"reference": "MVPQA-F", "date_from": self.today + timedelta(days=1)})
        future.action_campus_publish()
        self.assertEqual(future.campus_status, "scheduled")
        restricted = notice.copy({"reference": "MVPQA-G", "campus_group_id": self.env.ref("ideastone_erp.group_mvp_accountant").id})
        restricted.action_campus_publish()
        with self.assertRaises(AccessError):
            restricted.with_user(self.outsider).read(["body"])
        self.assertEqual(restricted.with_user(self.accountant).read(["name"])[0]["name"], restricted.name)
        with self.assertRaises(AccessError):
            future.with_user(self.outsider).read(["body"])
