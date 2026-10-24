import base64

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAdmissionsUI(OwnerMVPFixture, TransactionCase):
    def test_empty_filters_open_a_valid_enquiry_create_form(self):
        action = self.env["campus.admissions.ui"].with_user(self.owner).get_action("enquiries", create=True)
        spec = {"name": {}, "contact_name": {}, "campus_year_id": {"fields": {"display_name": {}}},
                "campus_course_id": {"fields": {"display_name": {}}}, "company_id": {"fields": {"display_name": {}}}}
        result = self.env["crm.lead"].with_user(self.owner).with_context(**action["context"]).onchange({}, [], spec)
        self.assertIs(result["value"]["campus_year_id"], False)
        self.assertIs(result["value"]["campus_course_id"], False)

    def test_navigation_keeps_source_workflows_and_checks_access(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        module = next(m for m in dashboard.get_overview()["faculty_modules"] if m["key"] == "admissions")
        self.assertEqual([r["label"] for r in module["items"]], ["Overview", "Enquiries", "Applications & review", "Documents", "Admission register"])
        for item in module["items"]:
            action = dashboard.get_owner_action(item["action"])
            self.assertEqual(action["context"]["campus_module"], "admissions")
            self.assertEqual(action["tag"], "ideastone_erp.admissions")
            self.assertEqual(dashboard.get_owner_action(item["source_action"])["type"], "ir.actions.act_window")
        with self.assertRaises(AccessError):
            self.env["campus.admissions.ui"].with_user(self.outsider).get_workspace()

    def test_saved_readiness_and_capacity_reconcile_after_workflow(self):
        requirement = self.env["campus.admission.requirement"].create({"name": "Required certificate"})
        app = self.application()
        app.action_campus_submit()
        ui = self.env["campus.admissions.ui"].with_user(self.owner)
        data = ui.get_workspace("applications", {"year_id": self.year.id})
        self.assertEqual(data["counts"]["ready"], 0)
        self.assertEqual(data["rows"][0]["status"], "Documents pending")
        document = self.env["campus.admission.document"].with_user(self.admissions).create({"admission_id": app.id,
            "requirement_id": requirement.id, "file": base64.b64encode(b"Synthetic UI evidence"), "filename": "evidence.txt"})
        document.action_verify()
        data = ui.get_workspace("applications", {"year_id": self.year.id})
        self.assertEqual(data["counts"]["ready"], 1)
        self.assertEqual(data["rows"][0]["completeness"], 100)
        app.action_campus_review()
        app.action_campus_approve()
        app.enroll_student()
        data = ui.get_workspace("register", {"year_id": self.year.id})
        self.assertEqual(data["counts"]["enrolled"], 1)
        self.assertEqual(sum(r["confirmed"] for r in data["departments"]), 1)
        self.assertEqual(data["rows"][0]["confirmed"], 1)
        self.assertEqual(data["rows"][0]["fill"], 1.0)

    def test_active_company_filters_search_and_record_actions(self):
        app = self.application()
        other = self.env["res.company"].create({"name": "Other admissions college"})
        self.owner.company_ids += other
        foreign = self.env["crm.lead"].create({"name": "Private foreign enquiry", "campus_enquiry": True, "company_id": other.id})
        lead = self.env["crm.lead"].create({"name": "Local CSE enquiry", "contact_name": "UI Prospect", "campus_enquiry": True, "company_id": self.env.company.id,
            "campus_year_id": self.year.id, "campus_course_id": self.course.id})
        ui = self.env["campus.admissions.ui"].with_user(self.owner).with_context(allowed_company_ids=[self.env.company.id, other.id])
        result = ui.get_workspace("enquiries", {"year_id": self.year.id}, "UI Prospect")
        self.assertEqual([r["id"] for r in result["rows"]], [lead.id])
        self.assertNotIn(foreign.id, [r["id"] for r in ui.get_workspace("enquiries")["rows"]])
        with self.assertRaises(AccessError):
            ui.get_action("enquiries", foreign.id)
        for invalid in (True, "1", -1, 2147483648):
            with self.assertRaises(ValidationError):
                ui.get_action("applications", invalid)
        action = ui.get_action("applications", app.id)
        self.assertEqual(action["res_id"], app.id)
        self.assertEqual(action["views"][0][1], "form")
        with self.assertRaises(ValidationError):
            ui.get_workspace(page=-1)
        before = self.env["op.admission"].search_count([])
        ui.get_action("applications", create=True)
        self.assertEqual(self.env["op.admission"].search_count([]), before)
