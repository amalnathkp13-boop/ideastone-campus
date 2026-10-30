from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestOwnerFees(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.ui = self.env["campus.owner.fees"].with_user(self.owner)
        self.term.campus_sequence = 1

    def plan(self, amount=1000):
        plan_id = self.ui.save_plan({"name": "Audit GQ structure", "year_id": self.year.id, "course_id": self.course.id,
            "term_id": self.term.id, "quota": "gq", "study_year": 1, "effective": str(self.today),
            "lines": [{"product_id": self.product.id, "amount": amount, "date": str(self.today - timedelta(days=7))}]})
        return self.env["op.fees.terms"].browse(plan_id)

    def publish(self, plan):
        self.ui.plan_action(plan.id, "review")
        self.ui.plan_action(plan.id, "publish")

    def test_navigation_and_college_permissions(self):
        overview = self.env["campus.dashboard"].with_user(self.owner).get_overview()
        module = next(m for m in overview["faculty_modules"] if m["key"] == "fees")
        self.assertEqual(len(module["items"]), 8)
        self.assertEqual(module["items"][0]["label"], "Financial overview")
        self.assertIn("source_action", module["items"][1])
        with self.assertRaises(AccessError):
            self.ui.with_user(self.outsider).get_workspace()
        other = self.env["res.company"].create({"name": "Other fee college"})
        foreign = self.env["product.product"].create({"name": "Private foreign head", "company_id": other.id, "campus_fee_head": True})
        self.assertNotIn(foreign.id, [r["id"] for r in self.ui.get_workspace(self.year.id)["heads"]])
        with self.assertRaises(AccessError):
            self.ui.save_head({"name": "Changed"}, foreign.id)

    def test_publication_and_assignment_are_scoped_and_idempotent(self):
        app = self.enrolled()
        plan = self.plan()
        values = {"plan_id": plan.id, "date": str(self.today)}
        with self.assertRaises(ValidationError):
            self.ui.preview_assignment(values)
        self.publish(plan)
        self.assertEqual(self.ui.preview_assignment(values)["eligible"], 0)
        app.campus_enrolment_id.campus_fee_quota = "gq"
        self.assertEqual(self.ui.preview_assignment(values)["amount"], 1000)
        self.ui.commit_assignment(values)
        self.ui.commit_assignment(values)
        charges = self.env["op.student.fees.details"].search([("fees_line_id", "in", plan.line_ids.ids), ("student_id", "=", app.student_id.id)])
        self.assertEqual(len(charges), 1)
        self.assertEqual(self.ui.preview_assignment(values)["installments"], 0)
        with self.assertRaises(ValidationError):
            plan.write({"name": "Changed after publication"})
        with self.assertRaises(ValidationError):
            plan.line_ids.write({"campus_amount": 1})
        with self.assertRaises(AccessError):
            plan.write({"campus_plan_state": "published"})

    def test_payment_retries_preserve_native_balances_and_receipts(self):
        app = self.enrolled()
        app.student_id.partner_id.property_account_receivable_id = self.receivable
        fee = self.fee(app.student_id, 1000)
        fee.date = self.today - timedelta(days=7)
        fee.action_campus_post()
        before = self.ui.get_workspace(self.year.id)["summary"]["income"]
        draft = self.ui.prepare_payment({"invoice_id": fee.invoice_id.id, "amount": 100, "method": "cash", "journal_id": self.cash_journal.id, "note": "Synthetic QA payment"})
        self.ui.post_payment(draft)
        self.ui.post_payment(draft)
        self.assertEqual(fee.invoice_id.amount_residual, 900)
        receipts = self.env["account.payment"].search([("campus_invoice_id", "=", fee.invoice_id.id)])
        self.assertEqual(len(receipts), 1)
        self.assertTrue(receipts.campus_receipt_number)
        self.assertEqual(receipts.campus_fee_note, "Synthetic QA payment")
        data = self.ui.get_workspace(self.year.id)
        self.assertEqual(data["summary"]["income"] - before, 100)
        account = next(r for r in data["accounts"] if r["id"] == app.student_id.id)
        self.assertEqual((account["assessed"], account["paid"], account["balance"]), (1000, 100, 900))
        with self.assertRaises(ValidationError):
            self.ui.prepare_payment({"invoice_id": fee.invoice_id.id, "amount": 901, "method": "cash", "journal_id": self.cash_journal.id})

    def test_contact_log_is_internal_and_immutable(self):
        app = self.enrolled()
        app.student_id.partner_id.property_account_receivable_id = self.receivable
        fee = self.fee(app.student_id, 1000)
        fee.date = self.today - timedelta(days=7)
        fee.action_campus_post()
        contact = self.ui.log_contact({"invoice_id": fee.invoice_id.id, "channel": "phone", "outcome": "Synthetic completed contact",
            "next_action": "Review payment plan", "next_date": str(self.today + timedelta(days=3)), "promise": True})
        row = self.env["campus.fee.contact"].browse(contact)
        self.assertEqual(row.user_id, self.owner)
        self.assertEqual(fee.invoice_id.amount_residual, 1000)
        with self.assertRaises(ValidationError):
            row.write({"outcome": "Replaced"})
        result = next(r for r in self.ui.get_workspace(self.year.id)["followups"] if r["id"] == fee.invoice_id.id)
        self.assertEqual(result["status"], "Promise to pay")

    def test_supplier_reversal_uses_its_own_academic_period(self):
        payable = self.env["account.account"].create({"name": "Fee QA payable", "code": "FQA9901", "account_type": "liability_payable", "reconcile": True})
        partner = self.env["res.partner"].create({"name": "Synthetic fee supplier", "property_account_payable_id": payable.id})
        self.cash_journal.outbound_payment_method_line_ids.payment_account_id = self.cash_account
        prior = self.year.start_date - timedelta(days=1)
        payment = self.env["account.payment"].create({"payment_type": "outbound", "partner_type": "supplier", "partner_id": partner.id,
            "amount": 250, "journal_id": self.cash_journal.id, "date": prior})
        payment.action_post()
        before = self.ui.get_workspace(self.year.id)["summary"]["expense"]
        reversal = payment.move_id._reverse_moves(default_values_list=[{"date": self.today}], cancel=False)
        reversal.action_post()
        self.assertEqual(self.ui.get_workspace(self.year.id)["summary"]["expense"] - before, -250)
