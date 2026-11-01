from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAccountantWorkspace(OwnerMVPFixture, TransactionCase):
    def test_accountant_sees_saved_fee_balances_without_other_admin_modules(self):
        student = self.enrolled().student_id
        fee = self.fee(student, 500)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 125)
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        overview = dashboard.get_overview()
        self.assertEqual(overview["workspace_role"], "Accountant")
        self.assertEqual([module["key"] for module in overview["faculty_modules"]],
                         ["home", "students", "collections", "transport", "spending", "communication"])
        student_module = next(module for module in overview["faculty_modules"] if module["key"] == "students")
        self.assertEqual([item["label"] for item in student_module["items"]],
                         ["Student fee directory", "Pending fee students", "Student fee accounts"])
        data = dashboard.get_accountant_metrics({"date_from": str(self.today), "date_to": str(self.today)})
        self.assertTrue(any(row["id"] == student.id and row["pending"] == 375 for row in data["pending"]))
        self.assertGreaterEqual(data["cards"][0]["value"], 125)
        owner_dashboard = self.env["campus.dashboard"].with_user(self.owner)
        self.assertIn("accounts", [module["key"] for module in owner_dashboard.get_overview()["faculty_modules"]])
        self.assertEqual(owner_dashboard.get_accountant_metrics({"date_from": str(self.today),
            "date_to": str(self.today)})["cards"], data["cards"])
        with self.assertRaises(AccessError):
            dashboard.get_owner_metrics()

    def test_event_bill_is_stored_and_counted_in_outgoing(self):
        expense = self.env["account.account"].create({"name": "QA event expense", "code": "MVP9811",
            "account_type": "expense", "company_id": self.env.company.id})
        payable = self.env["account.account"].create({"name": "QA vendor payable", "code": "MVP9812",
            "account_type": "liability_payable", "reconcile": True, "company_id": self.env.company.id})
        vendor = self.env["res.partner"].create({"name": "QA college event vendor", "property_account_payable_id": payable.id})
        journal = self.env["account.journal"].create({"name": "QA vendor bills", "code": "MQAP", "type": "purchase",
            "default_account_id": expense.id})
        bill = self.env["account.move"].with_user(self.accountant).create({
            "move_type": "in_invoice", "partner_id": vendor.id, "journal_id": journal.id,
            "invoice_date": self.today, "campus_spend_category": "event",
            "invoice_line_ids": [(0, 0, {"name": "Annual day supplies", "quantity": 1,
                "price_unit": 2400, "account_id": expense.id, "tax_ids": [(5, 0, 0)]})],
        })
        bill.action_post()
        self.assertEqual(bill.campus_spend_category, "event")
        data = self.env["campus.dashboard"].with_user(self.accountant).get_accountant_metrics({
            "date_from": str(self.today), "date_to": str(self.today)})
        self.assertTrue(any(row["id"] == bill.id for row in data["recent_bills"]))
        self.assertGreaterEqual(next(row["value"] for row in data["spending"] if row["label"] == "Event"), 2400)

    def test_fee_circular_and_approved_transport_bill_persist(self):
        notice = self.env["campus.circular"].with_user(self.accountant).create({
            "name": "Semester fee due date", "reference": "QA-FEE-CIRCULAR",
            "date_from": self.today, "audience": "student", "body": "<p>Pay by the due date.</p>",
            "campus_managed": True, "campus_category": "Fees",
        })
        notice.action_campus_publish()
        self.assertEqual(notice.campus_status, "published")
        self.assertEqual(self.env["campus.circular"].with_user(self.accountant).search_count([("id", "=", notice.id)]), 1)

        student = self.enrolled().student_id
        student.partner_id.property_account_receivable_id = self.receivable
        route = self.env["campus.transport.route"].create({"name": "QA bus", "year_id": self.year.id,
            "vehicle_registration": "TN-00-QA-0001", "capacity": 40})
        stop = self.env["campus.transport.stop"].create({"name": "QA stop", "route_id": route.id,
            "fee": 750, "fee_product_id": self.product.id})
        allocation = self.env["campus.transport.allocation"].create({"name": "QA transport",
            "student_id": student.id, "stop_id": stop.id})
        allocation.action_submit()
        manager = new_test_user(self.env, login="qa_transport_manager", groups="ideastone_erp.group_manager")
        allocation.with_user(manager).action_approve()
        allocation.with_user(self.accountant).action_invoice()
        self.assertEqual(allocation.invoice_id.amount_total, 750)
        self.assertEqual(allocation.invoice_id.campus_student_id, student)
        with self.assertRaises(AccessError):
            allocation.with_user(self.accountant).write({"name": "Changed route"})
