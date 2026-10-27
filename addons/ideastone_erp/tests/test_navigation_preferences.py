from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestNavigationPreferences(TransactionCase):
    def setUp(self):
        super().setUp()
        self.first = new_test_user(self.env, login="navigation.first", groups="base.group_portal")
        self.second = new_test_user(self.env, login="navigation.second", groups="base.group_portal")
        self.users = self.env["res.users"].with_user(self.first)
        self.rows = [{"id": "dashboard", "target": "dashboard", "label": "My home", "visible": True}]

    def test_personal_role_and_company_isolation(self):
        self.assertEqual(self.users.campus_get_navigation("student"), {"revision": 0, "items": []})
        saved = self.users.campus_save_navigation("student", self.rows, 0)
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(self.users.campus_get_navigation("student")["items"][0]["label"], "My home")
        self.assertFalse(self.users.campus_get_navigation("parent")["items"])
        self.assertFalse(self.users.with_user(self.second).campus_get_navigation("student")["items"])
        company = self.env["res.company"].create({"name": "Navigation second college"})
        self.first.company_ids |= company
        self.assertFalse(self.users.with_company(company).campus_get_navigation("student")["items"])
        # Even calling on another user's recordset still only saves the caller's preferences.
        self.second.with_user(self.first).campus_save_navigation("parent", self.rows, 0)
        self.assertFalse(self.second.campus_navigation_preferences)
        self.assertTrue(self.users.campus_get_navigation("parent")["items"])

    def test_reject_malformed_and_injected_preferences(self):
        for rows in [None, {}, [], self.rows * 101, [{**self.rows[0], "url": "javascript:alert(1)"}],
                     [{**self.rows[0], "visible": "false"}], [{**self.rows[0], "removed": "false"}],
                     [{**self.rows[0], "target": "javascript:alert(1)"}], [{**self.rows[0], "label": " "}],
                     [{**self.rows[0], "label": "x" * 41}], [{**self.rows[0], "label": "a\nb"}],
                     [{**self.rows[0], "visible": False}], self.rows * 2,
                     self.rows + [{**self.rows[0], "id": "shortcut-1", "label": "MY HOME"}]]:
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.users.campus_save_navigation("student", rows, 0)
        with self.assertRaises(ValidationError):
            self.users.campus_save_navigation("unknown-role", self.rows, 0)
        with self.assertRaises(ValidationError):
            self.users.campus_save_navigation("student", self.rows, True)
        self.assertFalse(self.first.campus_navigation_preferences)

    def test_every_login_scope_has_independent_saved_preferences(self):
        scopes = ("student", "parent", "owner", "faculty", "hod", "coe", "staff")
        for scope in scopes:
            self.users.campus_save_navigation(scope, [{**self.rows[0], "label": f"{scope} Home"}], 0)
        for scope in scopes:
            saved = self.users.campus_get_navigation(scope)
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(saved["items"][0]["label"], f"{scope} Home")

    def test_conflicting_saves_preserve_other_workspaces(self):
        self.users.campus_save_navigation("student", self.rows, 0)
        self.users.campus_save_navigation("parent", self.rows, 0)
        with self.assertRaises(UserError):
            self.users.campus_save_navigation("student", [{**self.rows[0], "label": "Stale edit"}], 0)
        self.assertEqual(self.users.campus_get_navigation("student")["items"][0]["label"], "My home")
        self.assertEqual(self.users.campus_get_navigation("parent")["revision"], 1)
        self.users.campus_save_navigation("student", [{**self.rows[0], "label": "New name"}], 1)
        self.assertEqual(self.users.campus_get_navigation("student")["revision"], 2)

    def test_public_cannot_customize_and_existing_access_is_unchanged(self):
        public = self.users.with_user(self.env.ref("base.public_user"))
        for operation in [lambda: public.campus_get_navigation("student"),
                          lambda: public.campus_save_navigation("student", self.rows, 0)]:
            with self.assertRaises(AccessError):
                operation()
        before = (self.first.groups_id, self.first.company_ids)
        self.users.campus_save_navigation("student", self.rows, 0)
        self.assertEqual((self.first.groups_id, self.first.company_ids), before)
        with self.assertRaises(AccessError):
            self.first.with_user(self.first).read(["campus_navigation_preferences"])
