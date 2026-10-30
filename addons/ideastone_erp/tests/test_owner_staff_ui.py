from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestOwnerStaffUI(OwnerMVPFixture, TransactionCase):
    def test_three_owner_tabs_and_existing_staff_workflows(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        staff = next(module for module in dashboard.get_overview()["faculty_modules"] if module["key"] == "staff")
        labels = [item["label"] for item in staff["items"]]
        # The redesigned pages lead; the existing staff tools stay reachable after them.
        self.assertEqual(labels[:3], ["Staff directory", "Leave Management", "Payroll History"])
        self.assertIn("Teaching allocation", labels[3:])
        for item in staff["items"][:3]:
            self.assertTrue(dashboard.get_owner_action(item["action"])["tag"].startswith("ideastone_erp.owner_staff_"))
        source = dashboard.get_owner_source_action("faculty")
        self.assertEqual(source["res_model"], "op.faculty")
        self.assertEqual(source["context"]["campus_module"], "staff")
        with self.assertRaises(AccessError):
            self.env["campus.owner.staff.ui"].with_user(self.outsider).get_directory()

    def test_saved_categories_company_isolation_and_employee_deduplication(self):
        employee = self.env["hr.employee"].create({"name": "Linked teaching employee", "company_id": self.env.company.id})
        self.faculty.write({"emp_id": employee.id, "campus_category": "teaching", "campus_staff_code": "STAFF-UIQA"})
        support = self.faculty.copy({"partner_id": self.env["res.partner"].create({"name": "UI support", "company_id": self.env.company.id}).id,
            "first_name": "UI", "last_name": "Support", "campus_staff_code": "STAFF-SUPPORT", "campus_category": "non_teaching", "emp_id": False})
        foreign_company = self.env["res.company"].create({"name": "Foreign staff college"})
        foreign = self.env["hr.employee"].create({"name": "Foreign staff", "company_id": foreign_company.id})
        foreign_faculty = self.faculty.copy({"partner_id": self.env["res.partner"].create({"name": "Foreign faculty", "company_id": foreign_company.id}).id,
            "company_id": foreign_company.id, "main_department_id": False, "emp_id": foreign.id, "campus_staff_code": "FOREIGN-STAFF"})
        self.owner.company_ids |= foreign_company
        data = self.env["campus.owner.staff.ui"].with_user(self.owner).with_context(
            allowed_company_ids=[self.env.company.id, foreign_company.id]).get_directory()
        self.assertIn(f"faculty:{self.faculty.id}", [row["key"] for row in data["rows"]])
        self.assertNotIn(f"employee:{employee.id}", [row["key"] for row in data["rows"]])
        self.assertNotIn(f"employee:{foreign.id}", [row["key"] for row in data["rows"]])
        self.assertNotIn(f"faculty:{foreign_faculty.id}", [row["key"] for row in data["rows"]])
        row = next(row for row in data["rows"] if row["id"] == support.id and row["model"] == "op.faculty")
        self.assertEqual(row["category"], "non_teaching")
        department = next(row for row in data["departments"] if row["key"] == f"academic:{self.department.id}")
        self.assertEqual((department["teaching"], department["non_teaching"]), (1, 1))
        self.assertNotIn("campus_pan_reference", row)

    def test_leave_queue_and_native_decisions(self):
        employee = self.env["hr.employee"].create({"name": "Review sample staff", "company_id": self.env.company.id})
        kind = self.env["hr.leave.type"].create({"name": "Review sample leave", "requires_allocation": "no", "leave_validation_type": "hr"})
        day = self.today + timedelta(days=7)
        day += timedelta(days=(7 - day.weekday()) % 7)
        mandatory = self.env["hr.leave.mandatory.day"]
        while mandatory.search_count([("start_date", "<=", day), ("end_date", ">=", day)]):
            day += timedelta(days=7)
        leave = self.env["hr.leave"].create({"employee_id": employee.id, "holiday_status_id": kind.id,
            "request_date_from": day, "request_date_to": day, "name": "Saved approval request"})
        if leave.state == "draft":
            leave.action_confirm()
        service = self.env["campus.owner.staff.ui"].with_user(self.owner)
        self.assertIn(leave.id, [row["id"] for row in service.get_leave_queue()])
        with self.assertRaises(AccessError):
            self.env["campus.owner.staff.ui"].with_user(self.outsider).review_leave(leave.id, "approve")
        with self.assertRaises(ValidationError):
            service.review_leave(True, "approve")
        service.review_leave(leave.id, "approve")
        self.assertEqual(leave.state, "validate")
        self.assertNotIn(leave.id, [row["id"] for row in service.get_leave_queue()])
        with self.assertRaises(AccessError):
            service.review_leave(leave.id, "refuse")
        other_company = self.env["res.company"].create({"name": "Other leave college"})
        other_employee = self.env["hr.employee"].create({"name": "Other college staff", "company_id": other_company.id})
        other_leave = self.env["hr.leave"].create({"employee_id": other_employee.id, "holiday_status_id": kind.id,
            "request_date_from": day, "request_date_to": day, "name": "Other college request"})
        if other_leave.state == "draft":
            other_leave.action_confirm()
        self.owner.company_ids |= other_company
        service = service.with_context(allowed_company_ids=[self.env.company.id, other_company.id])
        self.assertNotIn(other_leave.id, [row["id"] for row in service.get_leave_queue()])
        with self.assertRaises(AccessError):
            service.review_leave(other_leave.id, "approve")
