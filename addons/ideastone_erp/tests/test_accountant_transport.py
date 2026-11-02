from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAccountantTransport(OwnerMVPFixture, TransactionCase):
    def route(self, **values):
        return self.env["campus.transport.route"].with_user(self.accountant).create({
            "name": "R-04 Perundurai", "year_id": self.year.id,
            "vehicle_registration": "TN 56 AB 1042", "capacity": 40, "staff_riders": 4,
            "maintenance_reserve": 32000, **values,
        })

    def test_saved_riders_receipts_and_actions(self):
        route = self.route()
        student = self.enrolled().student_id
        student.partner_id.property_account_receivable_id = self.receivable
        stop = self.env["campus.transport.stop"].create({"name": "Town centre", "route_id": route.id,
            "fee": 9000, "fee_product_id": self.product.id})
        allocation = self.env["campus.transport.allocation"].create({
            "name": "Student bus allocation", "student_id": student.id, "stop_id": stop.id})
        allocation.action_submit()
        manager = new_test_user(self.env, login="transport_qa_supervisor", groups="ideastone_erp.group_manager")
        allocation.with_user(manager).action_approve()
        allocation.with_user(self.accountant).action_invoice()
        invoice = allocation.invoice_id
        self.assertEqual(invoice.campus_transport_route_id, route)
        invoice.action_post()
        with self.assertRaises(ValidationError):
            invoice.write({"campus_transport_route_id": False})
        self.payment(invoice, 2500)
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        data = dashboard.get_transport_data(self.year.id)
        row = next(r for r in data["routes"] if r["id"] == route.id)
        self.assertEqual((row["students"], row["staff"]), (1, 4))
        self.assertEqual(data["revenue"], 2500)
        self.assertEqual(data["reserve"], 32000)
        allocation.with_user(manager).action_done()
        self.assertEqual(dashboard.get_transport_data(self.year.id)["revenue"], 2500)
        self.assertEqual(dashboard.get_transport_action("fleet", route.id)["res_id"], route.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            route.capacity = 3
        with self.assertRaises(AccessError):
            dashboard.with_user(self.outsider).get_transport_data()
        with self.assertRaises(ValidationError):
            dashboard.get_transport_action("unknown")

    def test_salary_bill_and_expenses_count_once(self):
        route = self.route()
        expense = self.env["account.account"].create({"name": "Transport expenses", "code": "TRQA01",
            "account_type": "expense", "company_id": self.env.company.id})
        payable = self.env["account.account"].create({"name": "Driver payable", "code": "TRQA02",
            "account_type": "liability_payable", "reconcile": True, "company_id": self.env.company.id})
        vendor = self.env["res.partner"].create({"name": "Sample driver", "property_account_payable_id": payable.id})
        self.env["account.journal"].create({"name": "Transport purchases", "code": "TQAP", "type": "purchase",
            "default_account_id": expense.id})
        payroll = self.env["campus.transport.payroll"].with_user(self.accountant).create({
            "route_id": route.id, "partner_id": vendor.id, "month": self.today.replace(day=1),
            "base": 28000, "allowance": 3500, "deductions": 500, "expense_account_id": expense.id})
        self.assertEqual(payroll.net, 31000)
        payroll.action_bill()
        bill = payroll.invoice_id
        payroll.action_bill()
        self.assertEqual(payroll.invoice_id, bill)
        self.assertEqual(bill.amount_total, 31000)
        dashboard = self.env["campus.dashboard"].with_user(self.accountant)
        self.assertEqual(dashboard.get_transport_data(self.year.id)["expenses"]["salary"], 0)
        bill.action_post()
        self.assertEqual(dashboard.get_transport_data(self.year.id)["expenses"]["salary"], 31000)
        self.assertEqual(payroll.payment_status, "processing")
        with self.assertRaises(ValidationError):
            payroll.write({"base": 1})
        with self.assertRaises(AccessError):
            self.env["campus.transport.payroll"].with_user(self.accountant).create({
                "route_id": route.id, "partner_id": vendor.id, "month": self.today.replace(day=1),
                "base": 1, "expense_account_id": expense.id, "invoice_id": bill.id})
