import base64
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestFacultyProfileWorkspace(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.ui = self.env["campus.faculty.workspace"].with_user(self.teacher)
        self.employee = self.env["hr.employee"].create({"name": "Profile audit employee", "user_id": self.teacher.id})
        self.reviewer = new_test_user(self.env, login="profile_payroll_reviewer", groups="ideastone_erp.group_manager,ideastone_erp.group_people")

    def test_seven_submodules_and_profile_first(self):
        overview = self.env["campus.dashboard"].with_user(self.teacher).get_overview()
        staff = next(m for m in overview["faculty_modules"] if m["key"] == "staff")
        self.assertEqual(len(staff["items"]), 7)
        self.assertEqual(staff["items"][0]["label"], "My staff profile")
        self.assertEqual(self.env.ref(staff["items"][0]["action"]).params, {"page": "myprofile"})
        self.assertFalse(self.env["campus.dashboard"].with_user(self.owner).get_overview().get("faculty_profile_enabled"))
        with self.assertRaises(AccessError):
            self.ui.with_user(self.outsider).get_workspace()

    def test_contact_edits_and_document_verification_are_scoped(self):
        self.ui.save_profile({"mobile": "9000000001", "campus_emergency_phone": "9000000002"})
        self.assertEqual(self.ui.get_workspace()["profile"]["mobile"], "9000000001")
        with self.assertRaises(ValidationError):
            self.ui.save_profile({"campus_designation": "Principal"})
        doc = self.ui.save_record("document", {"name": "Synthetic qualification", "kind": "qualification", "campus_category": "academic",
            "document": base64.b64encode(b"%PDF-1.4\nSynthetic QA document").decode(), "filename": "qualification.pdf",
            "campus_expiry_date": str(self.today + timedelta(days=10))})
        data = self.ui.get_workspace()
        self.assertEqual(data["documents"][0]["status"], "Expiring soon")
        self.assertEqual(data["documents"][0]["verification"], "pending")
        self.assertIn("/web/content/", self.ui.record_action("document", doc)["url"])
        with self.assertRaises(ValidationError):
            self.ui.save_record("document", {"name": "Forged review", "verification": "verified"}, doc)
        other_company = self.env["res.company"].create({"name": "Foreign profile college"})
        foreign = self.env["campus.faculty.detail"].create({"name": "Private other-college document", "faculty_id": self.faculty.id, "company_id": other_company.id})
        with self.assertRaises(AccessError):
            self.ui.save_record("document", {"name": "Changed"}, foreign.id)

    def test_activity_save_submit_and_private_evidence(self):
        activity = self.ui.save_record("activity", {"name": "Synthetic training", "kind": "fdp", "date_from": str(self.today), "campus_hours": 8})
        self.assertEqual(self.ui.get_workspace()["activities"][0]["campus_hours"], 8)
        self.ui.record_action("submit", activity)
        self.assertEqual(self.ui.get_workspace()["activities"][0]["state"], "submitted")
        with self.assertRaises(ValidationError):
            self.ui.save_record("activity", {"name": "Changed after submit"}, activity)
        with self.assertRaises(AccessError):
            self.ui.record_action("activity", 2147483647)
        with self.assertRaises(ValidationError):
            self.ui.save_record("document", {"name": "Bad file", "document": "PGh0bWw+", "filename": "malicious.html"})

    def test_approved_own_salary_only_and_same_payroll_values(self):
        agreement = self.env["campus.salary.agreement"].create({"name": "Audit salary", "employee_id": self.employee.id,
            "date_from": self.today.replace(day=1), "basic": 30000, "allowance": 5000, "bank_reference": "DO-NOT-EXPOSE"})
        self.assertFalse(self.ui.get_workspace()["agreements"])
        agreement.action_submit()
        agreement.with_user(self.reviewer).action_approve()
        data = self.ui.get_workspace()
        self.assertEqual(data["agreements"][0]["basic"], 30000)
        self.assertNotIn("bank_reference", data["agreements"][0])
        self.assertFalse(data["payroll"])
        slip = self.env["campus.payslip"].with_user(self.reviewer).create({"name": "Profile audit payslip", "agreement_id": agreement.id,
            "date_from": self.today.replace(day=1), "date_to": self.today, "working_days": 1})
        slip.action_compute()
        slip.action_submit()
        slip.action_approve()
        own = self.ui.get_workspace()["payroll"][0]
        history = self.env["campus.payslip"].with_user(self.teacher).get_history_data()["records"][0]
        self.assertEqual((own["id"], own["net"], own["late_days"], own["late_deduction"]),
                         (history["id"], history["net"], history["late_days"], history["late_deduction"]))
        other_employee = self.env["hr.employee"].create({"name": "Other payroll employee"})
        other = self.env["campus.salary.agreement"].create({"name": "Other private salary", "employee_id": other_employee.id, "date_from": self.today, "basic": 100000})
        other.action_submit()
        other.with_user(self.reviewer).action_approve()
        self.assertEqual(len(self.ui.get_workspace()["agreements"]), 1)
