from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAccountantWorkspace(OwnerMVPFixture, TransactionCase):
    def test_collection_tabs_use_saved_college_records(self):
        student = self.enrolled().student_id
        fee = self.fee(student, 500)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 125)
        plan = self.env["op.fees.terms"].create({
            "name": "QA semester plan", "campus_managed": True,
            "campus_course_id": self.course.id, "campus_year_id": self.year.id,
            "line_ids": [(0, 0, {"campus_product_id": self.product.id, "campus_amount": 500,
                                   "due_date": self.today, "value": 100})],
        })
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        tabs = next(module for module in dashboard.get_overview()["faculty_modules"]
                    if module["key"] == "collections")["items"]
        self.assertEqual(tabs[1]["page"], "accountant-collections-structures")
        self.assertEqual(tabs[-1]["page"], "accountant-collections-exports")
        for screen in ("structures", "assign", "invoices", "receipts", "reports", "dues", "exports"):
            result = dashboard.get_accountant_collection_records(screen, self.year.id)
            self.assertEqual(result["screen"], screen)
            self.assertTrue(result["metrics"])
            if screen != "exports":
                self.assertTrue(result["rows"], screen)
        self.assertEqual(dashboard.get_accountant_collection_records("structures", self.year.id)["rows"][0]["id"], plan.id)
        self.assertEqual(dashboard.get_accountant_collection_records("dues", self.year.id)["rows"][0]["cells"][3], 375)

    def test_collections_overview_uses_saved_invoices_and_receipts(self):
        student = self.enrolled().student_id
        fee = self.fee(student, 500)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 125)
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        modules = dashboard.get_overview()["faculty_modules"]
        collections = next(module for module in modules if module["key"] == "collections")
        self.assertEqual(collections["items"][0]["page"], "accountant-collections-overview")
        data = dashboard.get_accountant_collections_overview({
            "date_from": str(self.today), "date_to": str(self.today), "department_id": self.department.id})
        self.assertEqual(data["invoice_count"], 1)
        self.assertEqual(data["collected_month"], 125)
        self.assertEqual(data["status"]["billed"], 500)
        self.assertEqual(data["status"]["pending"] + data["status"]["overdue"], 375)
        self.assertEqual(data["recent_invoices"][0]["status"], "Pending")
        self.assertEqual(data["by_department"][0]["id"], self.department.id)

    def test_accountant_sees_saved_fee_balances_without_other_admin_modules(self):
        student = self.enrolled().student_id
        fee = self.fee(student, 500)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 125)
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        overview = dashboard.get_overview()
        self.assertEqual(overview["workspace_role"], "Accountant")
        self.assertEqual([module["key"] for module in overview["faculty_modules"]],
                         ["home", "students", "collections", "transport", "spending", "communication", "complaints"])
        student_module = next(module for module in overview["faculty_modules"] if module["key"] == "students")
        self.assertEqual([item["label"] for item in student_module["items"]],
                         ["Student fee directory", "Pending fee students", "Student fee accounts"])
        spending_module = next(module for module in overview["faculty_modules"] if module["key"] == "spending")
        self.assertEqual([item["label"] for item in spending_module["items"]], ["Event bills", "Maintenance bills"])
        for mode in ("events", "maintenance"):
            self.assertEqual(dashboard.get_owner_action("ideastone_erp.accountant_spending_" + mode)["tag"],
                             "ideastone_erp.accountant_spending")
        directory = dashboard.get_accountant_directory()
        row = next(r for r in directory["rows"] if r["id"] == student.id)
        self.assertEqual((row["total"], row["paid"], row["pending"]), (500, 125, 375))
        self.assertTrue(any(r["record_id"] == fee.invoice_id.id and r["pending"] == 375 for r in row["ledger"]))
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.outsider).get_accountant_directory()
        data = dashboard.get_accountant_metrics({"date_from": str(self.today), "date_to": str(self.today)})
        self.assertTrue(any(row["id"] == student.id and row["pending"] == 375 for row in data["pending"]))
        self.assertGreaterEqual(data["cards"][0]["value"], 125)
        self.assertEqual(len(data["trend"]), 12)
        self.assertGreaterEqual(data["trend"][-1]["collections"], 125)
        self.assertTrue(any(row["status"] == "Posted" for row in data["activity"]))
        self.assertGreaterEqual(data["collection_status"]["pending"] + data["collection_status"]["overdue"], 375)
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
            "campus_spend_department_id": self.department.id,
            "invoice_line_ids": [(0, 0, {"name": "Annual day supplies", "quantity": 1,
                "price_unit": 2400, "account_id": expense.id, "tax_ids": [(5, 0, 0)]})],
        })
        bill.action_post()
        self.assertEqual(bill.campus_spend_category, "event")
        data = self.env["campus.dashboard"].with_user(self.accountant).get_accountant_metrics({
            "date_from": str(self.today), "date_to": str(self.today)})
        self.assertTrue(any(row["id"] == bill.id for row in data["recent_bills"]))
        self.assertGreaterEqual(next(row["value"] for row in data["spending"] if row["label"] == "Event"), 2400)
        filtered = self.env["campus.dashboard"].with_user(self.accountant).get_accountant_metrics({
            "date_from": str(self.today), "date_to": str(self.today), "department_id": self.department.id})
        self.assertGreaterEqual(next(row["value"] for row in filtered["cards"] if row["key"] == "spending"), 2400)
        self.assertTrue(any(row["reference"] == bill.name for row in filtered["activity"]))

        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        values = {"vendor_id": vendor.id, "department_id": self.department.id, "category": "maintenance",
            "amount": 1250.50, "date": str(self.today), "reference": "QA maintenance draft"}
        draft = self.env["account.move"].browse(dashboard.create_accountant_spending(values))
        self.assertEqual((draft.state, draft.amount_total, draft.currency_id),
                         ("draft", 1250.50, self.env.company.currency_id))
        spending = dashboard.get_accountant_spending()
        row = next(r for r in spending["rows"] if r["id"] == draft.id)
        self.assertEqual((row["total"], row["due"], row["status"], row["category"]),
                         (1250.50, 1250.50, "Not Paid", "maintenance"))
        self.assertTrue(any(r["id"] == bill.id and r["total"] == 2400 for r in spending["rows"]))
        draft.button_cancel()
        self.assertNotIn(draft.id, [r["id"] for r in dashboard.get_accountant_spending()["rows"]])
        for amount in (0, -1, float("nan"), float("inf"), True, "100"):
            with self.assertRaises(ValidationError):
                dashboard.create_accountant_spending(dict(values, amount=amount))
        with self.assertRaises(ValidationError):
            dashboard.create_accountant_spending(dict(values, state="posted"))
        other = self.env["res.company"].create({"name": "QA other spending college"})
        other_department = self.env["op.department"].create({"name": "Other college", "code": "QA-SPEND",
            "company_id": other.id})
        with self.assertRaises(AccessError):
            dashboard.create_accountant_spending(dict(values, department_id=other_department.id))
        self.assertNotIn(other_department.id, [d["id"] for d in dashboard.get_accountant_spending()["departments"]])
        outsider = self.env["campus.dashboard"].with_user(self.outsider)
        with self.assertRaises(AccessError):
            outsider.get_accountant_spending()
        with self.assertRaises(AccessError):
            outsider.create_accountant_spending(values)

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
