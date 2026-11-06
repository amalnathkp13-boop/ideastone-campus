from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo import fields


class TestPrincipalWorkflow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.staff = self.env["res.users"].create({
            "name": "Requesting Staff", "login": "requesting.staff@campus.test",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.principal = self.env["res.users"].create({
            "name": "Reviewing Principal", "login": "reviewing.principal@campus.test",
            "groups_id": [(6, 0, [self.env.ref("ideastone_principal.group_principal").id])],
        })

    def test_request_decision_and_access(self):
        request = self.env["ideastone.principal.request"].with_user(self.staff).create({
            "name": "Approve academic event", "request_type": "academic",
            "description": "Department event request",
        })
        request.with_user(self.staff).action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.staff).action_approve()
        with self.assertRaises(AccessError):
            request.with_user(self.staff).write({"decision_note": "Forged decision"})
        request.with_user(self.principal).write({"decision_note": "Request reviewed and approved"})
        request.with_user(self.principal).action_approve()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.decided_by_id, self.principal)

    def test_rejection_needs_reason(self):
        request = self.env["ideastone.principal.request"].with_user(self.staff).create({
            "name": "Facility budget", "request_type": "facility", "description": "Budget review",
        })
        request.with_user(self.staff).action_submit()
        with self.assertRaises(UserError):
            request.with_user(self.principal).action_reject()
        request.with_user(self.principal).write({"decision_note": "Insufficient detail"})
        request.with_user(self.principal).action_reject()
        self.assertEqual(request.state, "rejected")

    def test_notice_visibility(self):
        notice = self.env["ideastone.principal.notice"].with_user(self.principal).create({
            "name": "Campus circular", "body": "<p>Notice text</p>",
        })
        self.assertFalse(self.env["ideastone.principal.notice"].with_user(self.staff).search([("id", "=", notice.id)]))
        notice.with_user(self.principal).action_publish()
        self.assertTrue(self.env["ideastone.principal.notice"].with_user(self.staff).search([("id", "=", notice.id)]))

    def test_notice_approval_return_and_scheduling(self):
        now = fields.Datetime.now()
        notice = self.env["ideastone.principal.notice"].with_user(self.principal).create({
            "name": "Upcoming examinations", "body": "<p>Exam instructions</p>",
            "publish_at": now + timedelta(days=2), "expires_at": now + timedelta(days=5),
        })
        notice.action_submit()
        with self.assertRaises(ValidationError):
            notice.action_return("")
        notice.action_return("Confirm the reporting time")
        self.assertEqual(notice.state, "returned")
        self.assertEqual(notice.return_note, "Confirm the reporting time")
        notice.write({"body": "<p>Report at 9 AM.</p>"})
        notice.action_submit()
        with self.assertRaises(AccessError):
            notice.with_user(self.staff).action_approve()
        notice.action_approve()
        self.assertEqual(notice.state, "scheduled")
        self.assertFalse(notice.published_on)
        self.assertFalse(notice.with_user(self.staff).search([("id", "=", notice.id)]))
        with self.assertRaises(UserError):
            notice.action_approve()
        with self.assertRaises(AccessError):
            notice.write({"state": "published"})
        with patch("odoo.addons.ideastone_principal.models.notice_workspace.fields.Datetime.now", return_value=now + timedelta(days=3)):
            self.env["ideastone.principal.notice"]._cron_publication()
        self.assertEqual(notice.state, "published")
        with patch("odoo.addons.ideastone_principal.models.notice_workspace.fields.Datetime.now", return_value=now + timedelta(days=6)):
            self.env["ideastone.principal.notice"]._cron_publication()
        self.assertEqual(notice.state, "archived")

    def test_notice_workspace_counts_and_access(self):
        model = self.env["ideastone.principal.notice"].with_user(self.principal)
        before = model.get_workspace()["counts"]["pending"]
        notice = model.create({"name": "Notice queue sample", "body": "<p>Saved content</p>"})
        notice.action_submit()
        data = model.get_workspace()
        self.assertEqual(data["counts"]["pending"], before + 1)
        self.assertEqual(next(row for row in data["rows"] if row["id"] == notice.id)["summary"], "Saved content")
        with self.assertRaises(AccessError):
            model.with_user(self.staff).get_workspace()

    def test_overview_is_principal_only(self):
        with self.assertRaises(AccessError):
            self.env["ideastone.principal.dashboard"].with_user(self.staff).get_overview()
        overview = self.env["ideastone.principal.dashboard"].with_user(self.principal).get_overview()
        self.assertIn("students", overview["counts"])
        self.assertIn("pending", overview["counts"])
        self.assertEqual(len(overview["dashboard"]["trend"]), 6)
        self.assertEqual(len(overview["dashboard"]["readiness"]), 4)
        # The overview reports counselling as counts; the notes themselves stay with mentors.
        with self.assertRaises(AccessError):
            self.env["campus.counseling"].with_user(self.principal).check_access_rights("read")
        request = self.env["ideastone.principal.request"].with_user(self.staff).create({
            "name": "Dashboard refresh check", "request_type": "academic", "description": "Saved request",
        })
        request.with_user(self.staff).action_submit()
        refreshed = self.env["ideastone.principal.dashboard"].with_user(self.principal).get_overview()
        self.assertEqual(refreshed["counts"]["pending"], overview["counts"]["pending"] + 1)
        self.assertFalse(self.env["op.student"].with_user(self.principal).check_access_rights("write", raise_exception=False))

    def test_finance_rupee_display_is_principal_only(self):
        usd = self.env.ref("base.USD")
        college = self.env["res.company"].create({"name": "Finance display test", "currency_id": usd.id})
        self.principal.write({"company_ids": [(4, college.id)]})
        owner = self.env["res.users"].create({
            "name": "Finance owner", "login": "finance.owner@principal.test",
            "company_id": college.id, "company_ids": [(6, 0, college.ids)],
            "groups_id": [(6, 0, [self.env.ref("ideastone_erp.group_mvp_owner").id])],
        })
        finance = self.env["campus.owner.fees"].with_company(college)
        principal_data = finance.with_user(self.principal).get_workspace()
        owner_data = finance.with_user(owner).get_workspace()
        self.assertEqual((principal_data["currency"], principal_data["symbol"]), ("INR", "₹"))
        self.assertEqual((owner_data["currency"], owner_data["symbol"]), (usd.name, usd.symbol))
        self.assertEqual(principal_data["summary"], owner_data["summary"])
        self.assertEqual(college.currency_id, usd)

    def test_shared_navigation_uses_existing_workspaces(self):
        overview = self.env["campus.dashboard"].with_user(self.principal).get_overview()
        self.assertEqual(overview["workspace_role"], "Principal")
        self.assertEqual(overview["faculty_modules"][0]["key"], "home")
        self.assertEqual(overview["faculty_modules"][0]["items"][0]["action"],
                         "ideastone_principal.action_principal_overview")
        self.assertIn("ideastone_erp.action_admissions_overview",
                      [item["action"] for module in overview["faculty_modules"]
                       for item in module["items"] if "action" in item])
        modules = {module["key"]: module for module in overview["faculty_modules"]}
        self.assertEqual(modules["staff"]["label"], "Faculty oversight")
        self.assertNotIn("Payroll History", [item["label"] for item in modules["staff"]["items"]])
        self.assertNotIn("Fee structures", [item["label"] for item in modules["fees"]["items"]])
        self.assertNotIn("Enquiries", [item["label"] for item in modules["admissions"]["items"]])
        self.assertNotIn("Schedule & marks entry", [item["label"] for item in modules["exams"]["items"]])
        self.assertEqual({item["action"] for item in overview["navigation"]},
                         {item["action"] for module in modules.values() for item in module["items"]})
        self.assertNotIn("communication", modules)
        self.assertFalse(any(module["key"] == "settings" for module in overview["faculty_modules"]))

    def test_navigation_models_are_readable(self):
        action_ids = self.env["ir.model.data"].search([
            ("module", "=", "ideastone_principal"),
            ("model", "=", "ir.actions.act_window"),
        ])
        for action_id in action_ids:
            action = self.env.ref(f"ideastone_principal.{action_id.name}")
            model = self.env[action.res_model].with_user(self.principal)
            self.assertTrue(model.check_access_rights("read", raise_exception=False), action.name)
            model.search([], limit=1)

    def test_other_roles_keep_their_navigation(self):
        for role in ("owner", "accountant"):
            user = self.env["res.users"].create({
                "name": role, "login": f"{role}@principal.test",
                "groups_id": [(6, 0, [self.env.ref(f"ideastone_erp.group_mvp_{role}").id])],
            })
            overview = self.env["campus.dashboard"].with_user(user).get_overview()
            self.assertFalse(overview.get("is_principal_workspace"))
            modules = {module["key"]: module for module in overview["faculty_modules"]}
            self.assertNotIn("decisions", modules)
            self.assertNotIn("principal_notices", modules)
            if role == "owner":
                self.assertIn("OD Staffs", [item["label"] for item in modules["staff"]["items"]])
            else:
                self.assertTrue(overview["is_accountant_workspace"])

    def test_principal_navigation_preferences_scope(self):
        preferences = self.principal.with_user(self.principal).campus_get_navigation("principal")
        self.assertEqual(preferences["items"], [])
