from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


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

    def test_overview_is_principal_only(self):
        with self.assertRaises(AccessError):
            self.env["ideastone.principal.dashboard"].with_user(self.staff).get_overview()
        overview = self.env["ideastone.principal.dashboard"].with_user(self.principal).get_overview()
        self.assertIn("students", overview["counts"])
        self.assertIn("pending", overview["counts"])
        self.assertFalse(self.env["op.student"].with_user(self.principal).check_access_rights("write", raise_exception=False))

    def test_shared_navigation_uses_existing_workspaces(self):
        overview = self.env["campus.dashboard"].with_user(self.principal).get_overview()
        self.assertEqual(overview["workspace_role"], "Principal")
        self.assertEqual(overview["faculty_modules"][0]["key"], "home")
        self.assertEqual(overview["faculty_modules"][0]["items"][0]["action"],
                         "ideastone_principal.action_principal_overview")
        self.assertIn("ideastone_erp.action_admissions_overview",
                      [item["action"] for module in overview["faculty_modules"]
                       for item in module["items"] if "action" in item])
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
