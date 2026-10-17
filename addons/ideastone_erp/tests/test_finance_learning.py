import base64
from datetime import timedelta
from unittest.mock import patch

from odoo.addons.ideastone_lms.models.lms_client import LmsClient
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestFinanceLearning(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.session()
        self.user = new_test_user(self.env, login="learning_student", groups="base.group_portal", tz="Asia/Kolkata", partner_id=self.student.partner_id.id)
        self.student.user_id = self.user
        self.portal = self.env["campus.student.portal"].with_user(self.user)
        self.bank = self.env["account.journal"].create({"name": "QA bank", "code": "LQAB", "type": "bank", "default_account_id": self.cash_account.id})
        self.bank.inbound_payment_method_line_ids.payment_account_id = self.cash_account

    def task(self, **changes):
        kind = self.env["grading.assignment.type"].create({"name": "MVP coursework"})
        vals = {"name": "MVP programming exercise", "course_id": self.course.id, "batch_id": self.section.id,
                "subject_id": self.subject.id, "faculty_id": self.faculty.id, "assignment_type": kind.id,
                "description": "Explain and test your solution.", "issued_date": fields.Datetime.now() - timedelta(days=2),
                "submission_date": fields.Datetime.now() + timedelta(days=2), "marks": 10,
                "allocation_ids": [(6, 0, self.student.ids)], "campus_learning": True}
        vals.update(changes)
        return self.env["op.assignment"].with_user(self.teacher).create(vals)

    def collection(self, invoice, reference, amount=100, journal=None):
        return self.env["campus.fee.payment.wizard"].with_user(self.accountant).create({"invoice_id": invoice.id, "amount": amount,
            "journal_id": (journal or self.bank).id, "method": "upi", "reference": reference})

    def test_duplicate_transaction_new_forms_and_method_changes_do_not_collect_twice(self):
        fee = self.fee(self.student, 1000)
        fee.action_campus_post()
        first = self.collection(fee.invoice_id, " Txn-123 ")
        first.action_pay()
        self.assertEqual(fee.invoice_id.amount_residual, 900)
        second = self.collection(fee.invoice_id, "txn-123")
        second.method = "bank"
        count = self.env["account.payment"].search_count([("campus_invoice_id", "=", fee.invoice_id.id)])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.action_pay()
        fee.invoice_id.invalidate_recordset()
        self.assertEqual(fee.invoice_id.amount_residual, 900)
        self.assertEqual(count, self.env["account.payment"].search_count([("campus_invoice_id", "=", fee.invoice_id.id)]))
        self.assertEqual(first.payment_id.campus_transaction_key, f"{self.env.company.id}:{self.bank.id}:TXN-123")
        with self.assertRaises(AccessError):
            first.payment_id.write({"campus_transaction_key": "FORGED"})

    def test_native_bank_form_needs_actual_reference_and_cash_receipts_remain_independent(self):
        fee = self.fee(self.student, 1000)
        fee.action_campus_post()
        register = self.env["account.payment.register"].with_user(self.accountant).with_context(active_model="account.move", active_ids=fee.invoice_id.ids)
        wizard = register.create({"amount": 100, "journal_id": self.bank.id, "communication": fee.invoice_id.name})
        with self.assertRaises(ValidationError):
            wizard._create_payments()
        wizard.campus_transaction_reference = "BANK-REAL-123"
        payment = wizard._create_payments()
        self.assertEqual(payment.campus_reference, "BANK-REAL-123")
        first = self.payment(fee.invoice_id, 100).payment_id
        second = self.payment(fee.invoice_id, 100).payment_id
        self.assertNotEqual(first.campus_receipt_number, second.campus_receipt_number)
        self.assertFalse(first.campus_transaction_key)
        self.assertEqual(fee.invoice_id.amount_residual, 700)

    def test_reversal_preserves_reference_and_restores_dues(self):
        fee = self.fee(self.student, 500)
        fee.action_campus_post()
        request = self.collection(fee.invoice_id, "UPI-REVERSED")
        request.action_pay()
        payment = request.payment_id
        payment.campus_reversal_reason = "Synthetic wrong allocation corrected"
        payment.action_campus_reverse()
        self.assertEqual(fee.invoice_id.amount_residual, 500)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.collection(fee.invoice_id, "upi-reversed").action_pay()
        self.assertEqual(payment.campus_transaction_key, f"{self.env.company.id}:{self.bank.id}:UPI-REVERSED")

    def test_coursework_submission_review_revision_and_explicit_zero(self):
        task = self.task()
        self.assertFalse(self.portal.snapshot()["assignments"])
        task.act_publish()
        payload = {"assignment_id": task.id, "description": "My original explanation", "file": base64.b64encode(b"Synthetic coursework"), "filename": "exercise.txt"}
        result = self.portal.act("assignment", payload)
        work = self.env["op.assignment.sub.line"].browse(result["submission_id"])
        self.assertEqual(work.campus_submitted_by, self.user)
        self.assertFalse(work.campus_marks_entered)
        self.assertEqual(result, self.portal.act("assignment", dict(payload, description="Retry must not overwrite submitted work")))
        self.assertEqual(work.description, "My original explanation")
        self.assertEqual(self.portal._download("assignment", work.id)[0], b"Synthetic coursework")
        reviewer = work.with_user(self.teacher)
        reviewer.note = "Private draft review"
        self.assertFalse(self.portal.snapshot()["assignments"][0]["feedback"])
        with self.assertRaises(ValidationError):
            reviewer.act_accept()
        reviewer.write({"marks": 7, "note": "Add more edge cases"})
        reviewer.act_change_req()
        self.assertEqual(self.portal.snapshot()["assignments"][0]["feedback"], "Add more edge cases")
        self.portal.act("assignment", dict(payload, description="Revised solution"))
        self.assertFalse(work.campus_marks_entered)
        self.assertFalse(self.portal.snapshot()["assignments"][0]["feedback"])
        reviewer.write({"marks": 0, "note": "Reviewed: zero is an entered grade."})
        reviewer.act_accept()
        row = self.portal.snapshot()["assignments"][0]
        self.assertEqual(row["marks"], 0)
        self.assertFalse(row["can_submit"])
        with self.assertRaises(ValidationError):
            reviewer.write({"marks": 9})
        with self.assertRaises(ValidationError):
            reviewer.write({"note": "Unaudited overwrite"})

    def test_learning_scope_raw_rpc_and_published_identity_are_protected(self):
        task = self.task()
        task.act_publish()
        for model, values in [("op.assignment", {"name": "Forged"}), ("grading.assignment", {"name": "Forged"}), ("op.assignment.sub.line", {"description": "Forged"})]:
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.user).create(values)
        with self.assertRaises(AccessError):
            task.with_user(self.user).read(["description"])
        with self.assertRaises(ValidationError):
            task.grading_assignment_id.with_user(self.teacher).write({"faculty_id": self.faculty.id})
        other = new_test_user(self.env, login="learning_other", groups="openeducat_assignment.group_op_assignment_user")
        with self.assertRaises(AccessError):
            task.with_user(other).act_cancel()
        with self.assertRaises(AccessError):
            self.portal.act("assignment", {"assignment_id": task.id, "description": "Forgery", "student_id": self.student.id})
        foreign = self.enrolled().student_id
        self.student.user_id = False
        foreign.user_id = self.user
        with self.assertRaises(AccessError):
            self.portal.act("assignment", {"assignment_id": task.id, "description": "Wrong allocation"})

    def test_deadline_and_parent_read_only_released_feedback(self):
        late = self.task(submission_date=fields.Datetime.now() - timedelta(days=1))
        late.act_publish()
        with self.assertRaises(ValidationError):
            self.portal.act("assignment", {"assignment_id": late.id, "description": "Too late"})
        task = self.task(campus_allow_late=True, submission_date=fields.Datetime.now() - timedelta(days=1))
        task.act_publish()
        result = self.portal.act("assignment", {"assignment_id": task.id, "description": "Permitted late work"})
        work = self.env["op.assignment.sub.line"].browse(result["submission_id"]).with_user(self.teacher)
        parent = new_test_user(self.env, login="learning_parent", groups="base.group_portal", is_parent=True)
        relation = self.env["op.parent.relationship"].create({"name": "Coursework QA guardian"})
        self.env["op.parent"].create({"name": parent.partner_id.id, "user_id": parent.id, "relationship_id": relation.id, "student_ids": [(6, 0, self.student.ids)]})
        portal = self.env["campus.parent.portal"].with_user(parent)
        work.write({"marks": 8, "note": "Draft comment"})
        self.assertFalse(portal.snapshot()["homework"][-1]["feedback"])
        work.act_accept()
        entry = next(row for row in portal.snapshot()["homework"] if row["id"] == task.id)
        self.assertEqual(entry["score"], 8)
        self.assertEqual(entry["feedback"], "Draft comment")
        with self.assertRaises(AccessError):
            portal.act("assignment", self.student.id, {"assignment_id": task.id, "description": "Parent impersonation"})

    def test_partial_lms_enrolment_is_visible_and_retryable(self):
        self.course.lms_course_key = "QA-COURSE"
        fake = LmsClient("https://lms.example.test", "qa", "synthetic-test-secret")
        with patch.object(type(self.student), "_lms_client", return_value=fake), patch.object(fake, "ensure_user", return_value=({"key": "QA-ID", "login": "qa.student"}, False)), patch.object(fake, "add_participant", side_effect=RuntimeError("Synthetic enrolment error")):
            self.student.action_provision_lms()
        self.assertEqual(self.student.lms_identity_key, "QA-ID")
        self.assertFalse(self.student.lms_synced_on)
        self.assertIn("QA-COURSE", self.student.lms_sync_error)
        with patch.object(type(self.student), "_lms_client", return_value=fake), patch.object(fake, "ensure_user", return_value=({"key": "QA-ID", "login": "qa.student"}, False)), patch.object(fake, "add_participant") as enrolled:
            self.student.action_provision_lms()
            enrolled.assert_called_once_with("QA-COURSE", "QA-ID")
        self.assertTrue(self.student.lms_synced_on)
        self.assertFalse(self.student.lms_sync_error)
        self.assertFalse(self.student.lms_enrolment_pending)
        self.course.lms_course_key = "QA-NEXT-COURSE"
        self.assertTrue(self.student.lms_enrolment_pending)
        with self.assertRaises(AccessError):
            self.student.with_user(self.user).action_provision_lms()

    def test_learning_frame_exposes_only_public_url_to_faculty(self):
        self.env["ir.config_parameter"].sudo().set_param("ideastone.lms_url", "/lms/")
        self.assertEqual(self.env["ideastone.lms.workspace"].with_user(self.teacher).configuration(), {"url": "/lms/"})
        with self.assertRaises(AccessError):
            self.env["ideastone.lms.workspace"].with_user(self.user).configuration()
        self.env["ir.config_parameter"].sudo().set_param("ideastone.lms_url", "javascript:alert(1)")
        with self.assertRaises(ValidationError):
            self.env["ideastone.lms.workspace"].with_user(self.teacher).configuration()
