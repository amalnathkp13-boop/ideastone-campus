from datetime import datetime

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPrincipalStaffWorkspace(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({"name": "Principal staff QA college"})
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=[self.company.id], no_reset_password=True))
        self.principal = new_test_user(self.env, login="principal_staff_qa", groups="ideastone_principal.group_principal",
            company_id=self.company.id, company_ids=[(6, 0, self.company.ids)])
        self.outsider = new_test_user(self.env, login="principal_staff_outsider", groups="base.group_user",
            company_id=self.company.id, company_ids=[(6, 0, self.company.ids)])
        self.department = self.env["op.department"].create({"name": "QA engineering", "code": "PS-QA", "company_id": self.company.id})
        self.ui = self.env["ideastone.principal.staff.workspace"].with_user(self.principal)

    def test_recruitment_review_validation_audit_and_scope(self):
        model = self.env["ideastone.principal.staff.application"].with_user(self.principal)
        values = {"name": "Synthetic applicant", "role": "Assistant Professor", "department_id": self.department.id,
                  "qualification": "Ph.D.", "experience": "5 years", "company_id": self.company.id}
        application = model.create(values)
        self.assertTrue(application.reference.startswith("APP-"))
        with self.assertRaises(ValidationError):
            self.ui.decide_application(application.id, "approved")
        application.write({"documents": "verified", "interview_date": "2026-11-06 05:00:00"})
        application.action_schedule_interview()
        self.assertEqual(application.state, "interview")
        self.ui.decide_application(application.id, "approved", "Documents and interview reviewed")
        self.assertEqual((application.state, application.decided_by_id), ("approved", self.principal))
        self.assertTrue(application.decided_on)
        with self.assertRaises(ValidationError):
            application.write({"role": "Changed after approval"})
        with self.assertRaises(ValidationError):
            self.ui.decide_application(application.id, "rejected", "Duplicate decision")
        rejected = model.create(dict(values, name="Synthetic rejected applicant"))
        self.assertNotEqual(application.reference, rejected.reference)
        with self.assertRaises(ValidationError):
            self.ui.decide_application(rejected.id, "rejected", "")
        self.ui.decide_application(rejected.id, "rejected", "Current vacancy requirements differ")
        self.assertEqual(rejected.state, "rejected")
        with self.assertRaises(ValidationError):
            model.create(dict(values, state="approved"))
        with self.assertRaises(AccessError):
            self.env["ideastone.principal.staff.workspace"].with_user(self.outsider).get_applications()
        other = self.env["res.company"].create({"name": "Other recruitment college"})
        with self.assertRaises(AccessError):
            model.create(dict(values, company_id=other.id))
        navigation = self.env["campus.dashboard"].with_user(self.principal).get_overview()
        staff = next(m for m in navigation["faculty_modules"] if m["key"] == "staff")
        self.assertEqual([item["label"] for item in staff["items"]],
                         ["Staff directory", "New staff applications"])

    def test_directory_and_punch_reporting_use_active_college(self):
        calendar = self.env["resource.calendar"].create({"name": "QA staff UTC hours", "tz": "UTC", "company_id": self.company.id})
        employee = self.env["hr.employee"].create({"name": "QA campus technician", "company_id": self.company.id,
                                                   "resource_calendar_id": calendar.id})
        self.env["hr.attendance"].create({"employee_id": employee.id, "check_in": datetime(2026, 11, 2, 9, 30),
                                           "check_out": datetime(2026, 11, 2, 17)})
        directory = self.ui.get_directory()
        self.assertTrue(any(r["key"] == f"employee:{employee.id}" for r in directory["rows"]))
        # Salary figures are not part of the Principal workspace.
        with self.assertRaises(AccessError):
            self.ui.get_payroll("2026", "11")
        with self.assertRaises(AccessError):
            self.env["ideastone.principal.staff.workspace"].with_user(self.outsider).get_payroll()
        other = self.env["res.company"].create({"name": "Other staff reporting college"})
        other_employee = self.env["hr.employee"].create({"name": "Other college technician", "company_id": other.id})
        self.assertNotIn(f"employee:{other_employee.id}", [r["key"] for r in self.ui.get_directory()["rows"]])
