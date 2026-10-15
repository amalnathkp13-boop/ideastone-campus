from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCampusPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True))
        cls.portal_user = new_test_user(cls.env, login="qa_http_portal", groups="base.group_portal", password="qa-http-fixture")
        cls.manager = new_test_user(cls.env, login="qa_http_manager", groups="ideastone_erp.group_manager")

    def test_authentication_required(self):
        response = self.url_open("/my/campus", allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))

    def test_portal_and_catalogue_render_empty_states(self):
        self.authenticate("qa_http_portal", "qa-http-fixture")
        response = self.url_open("/my/campus")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your account has no linked student record", response.text)
        response = self.url_open("/my/campus/library")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Digital resources", response.text)

    def test_no_identity_cannot_download(self):
        resource = self.env["campus.digital.resource"].create({"name": "QA protected", "document": "UUE=", "filename": "qa.txt"})
        resource.action_submit()
        resource.with_user(self.manager).action_approve()
        self.authenticate("qa_http_portal", "qa-http-fixture")
        response = self.url_open(f"/my/campus/resource/{resource.id}")
        self.assertEqual(response.status_code, 404)
