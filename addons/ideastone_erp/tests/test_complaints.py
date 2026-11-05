import base64

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestComplaints(OwnerMVPFixture, TransactionCase):
    def test_routing_visibility_response_and_resolution(self):
        owner = self.env["campus.complaints.ui"].with_user(self.owner)
        reporter = self.env["campus.complaints.ui"].with_user(self.admissions)
        respondent = self.env["campus.complaints.ui"].with_user(self.teacher)
        handler = self.env["campus.complaints.ui"].with_user(self.accountant)
        owner.save_route("staff", self.accountant.id)
        result = reporter.submit({
            "subject": "Workplace concern", "description": "Please investigate this incident.",
            "category": "staff", "kind": "incident", "target_user_id": self.teacher.id,
            "evidence": base64.b64encode(b"\x89PNG\r\n\x1a\nexample").decode(),
            "evidence_filename": "incident.png",
        })
        case_id = result["id"]
        self.assertEqual(result["reference"], f"CMP-{case_id:05d}")
        self.assertEqual(handler.get_page_data("staff")["counts"]["in_charge"], 1)
        self.assertEqual(reporter.get_page_data("staff")["counts"]["mine"], 1)
        about_me = next(row for row in respondent.get_page_data("staff")["rows"] if row["id"] == case_id)
        self.assertTrue(about_me["about_me"])
        self.assertEqual(about_me["reporter"], "Identity withheld")
        self.assertFalse(about_me["can_work"])
        self.assertFalse(about_me["has_evidence"])
        with self.assertRaises(AccessError):
            respondent.evidence(case_id)
        self.assertEqual(owner.evidence(case_id)[1], "incident.png")
        self.assertEqual(owner.get_page_data("staff")["rows"][0]["reporter"], self.admissions.name)
        with self.assertRaises(AccessError):
            respondent.act(case_id, "resolve", {"resolution": "I closed this."})
        respondent.act(case_id, "respond", {"note": "I can provide more context."})
        handler.act(case_id, "start")
        handler.act(case_id, "resolve", {"resolution": "Reviewed with the college office."})
        reporter.act(case_id, "reopen", {"note": "Please review additional evidence."})
        handler.act(case_id, "resolve", {"resolution": "Reviewed the additional detail."})
        owner.act(case_id, "close")
        self.assertEqual(owner.get_page_data("staff")["rows"][0]["state"], "closed")
        self.assertEqual(len(self.env["campus.complaint"].sudo().browse(case_id).event_ids), 7)
        with self.assertRaises(AccessError):
            reporter.act(case_id, "reopen", {"note": "After closure"})

    def test_owner_cannot_submit_and_self_assignment_is_rejected(self):
        owner = self.env["campus.complaints.ui"].with_user(self.owner)
        with self.assertRaises(AccessError):
            owner.submit({"subject": "Owner report", "description": "Not allowed", "category": "other"})
        reporter = self.env["campus.complaints.ui"].with_user(self.admissions)
        case_id = reporter.submit({
            "subject": "Leaking pipe", "description": "Water near the lab.",
            "category": "infrastructure", "location": "Lab corridor",
        })["id"]
        with self.assertRaises(AccessError):
            owner.act(case_id, "assign", {"user_id": self.admissions.id})
        with self.assertRaises(ValidationError):
            reporter.submit({"subject": "Bad date", "description": "Invalid incident date",
                             "category": "safety", "incident_date": "2999-01-01"})
        with self.assertRaises(AccessError):
            self.env["campus.complaint"].with_user(self.admissions).browse(case_id).read(["description"])

    def test_cross_college_cases_remain_in_their_college(self):
        case_id = self.env["campus.complaints.ui"].with_user(self.admissions).submit({
            "subject": "Electrical concern", "description": "Socket requires inspection.",
            "category": "infrastructure",
        })["id"]
        another = self.env["res.company"].create({"name": "Other complaint college"})
        self.owner.company_ids |= another
        other_owner = self.env["campus.complaints.ui"].with_user(self.owner).with_company(another)
        self.assertFalse(any(row["id"] == case_id for row in other_owner.get_page_data()["rows"]))
        with self.assertRaises(AccessError):
            other_owner.act(case_id, "close")

    def test_three_submodules_appear_for_each_internal_workspace(self):
        coe = new_test_user(self.env, login="complaints.coe", groups="ideastone_erp.group_coe_admin")
        for user in (self.owner, self.admissions, self.accountant, self.teacher, coe):
            data = self.env["campus.dashboard"].with_user(user).get_overview()
            module = next(item for item in data["faculty_modules"] if item["key"] == "complaints")
            self.assertEqual([item["label"] for item in module["items"]],
                             ["Dashboard", "Student complaints", "Staff complaints"])
