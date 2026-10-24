import re
from urllib.parse import urlsplit

from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCampusPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True))
        cls.portal_user = new_test_user(cls.env, login="qa_http_portal", groups="base.group_portal", password="qa-http-fixture")
        cls.manager = new_test_user(cls.env, login="qa_http_manager", groups="ideastone_erp.group_manager")
        cls.student_user = new_test_user(cls.env, login="qa_http_student", groups="base.group_portal", password="qa-http-fixture")
        cls.parent_user = new_test_user(cls.env, login="qa_http_parent", groups="base.group_portal", password="qa-http-fixture")
        cls.linked_student = cls.env["op.student"].create({"first_name": "QA", "last_name": "Linked", "gender": "o", "user_id": cls.student_user.id, "partner_id": cls.env["res.partner"].create({"name": "QA-LINKED-STUDENT", "user_id": cls.student_user.id, "company_id": cls.env.company.id}).id})
        cls.unrelated_student = cls.env["op.student"].create({"first_name": "QA", "last_name": "Unrelated", "gender": "o", "partner_id": cls.env["res.partner"].create({"name": "QA-UNRELATED-PRIVATE", "company_id": cls.env.company.id}).id})
        cls.parent_user.write({"child_ids": [(6, 0, cls.student_user.ids)]})
        relation = cls.env["op.parent.relationship"].create({"name": "HTTP test guardian"})
        cls.env["op.parent"].create({"name": cls.parent_user.partner_id.id, "user_id": cls.parent_user.id,
            "relationship_id": relation.id, "student_ids": [(6, 0, cls.linked_student.ids)]})

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

    def test_parent_cannot_select_unrelated_student(self):
        self.authenticate("qa_http_parent", "qa-http-fixture")
        response = self.url_open("/my/campus")
        self.assertEqual(response.status_code, 200)
        self.assertIn('aria-label="Parent navigation"', response.text)
        self.assertIn("QA-LINKED-STUDENT", response.text)
        response = self.url_open(f"/my/campus?student={self.unrelated_student.id}")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("QA-UNRELATED-PRIVATE", response.text)
        self.assertIn("This child is not available", response.text)

    def test_student_workspace_uses_own_identity(self):
        self.authenticate("qa_http_student", "qa-http-fixture")
        response = self.url_open("/my/campus?campus_role=Admin")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Student workspace", response.text)
        self.assertIn("/my/campus/student/profile", response.text)
        self.assertNotIn('href="/my/profile"', response.text)
        self.assertNotIn("QA-UNRELATED-PRIVATE", response.text)

    def test_portal_login_lands_on_campus(self):
        response = self.url_open("/web/login")
        token = re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)
        response = self.url_open("/web/login", data={"login": "qa_http_student", "password": "qa-http-fixture", "csrf_token": token}, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(urlsplit(response.headers["Location"]).path, "/my/campus")
        response = self.url_open("/my")
        self.assertIn('href="/my/campus"', response.text)

    def test_student_calendar_extremes_are_recoverable(self):
        self.student_user.tz = "Asia/Kolkata"
        self.authenticate("qa_http_student", "qa-http-fixture")
        for first, last in [("0001-01-01", "0001-01-02"), ("9999-12-30", "9999-12-31")]:
            response = self.url_open(f"/my/campus/student/timetable?date_from={first}&date_to={last}")
            self.assertEqual(response.status_code, 400)
            self.assertIn("Choose dates within the supported calendar range.", response.text)
            self.assertIn("Retry student access", response.text)
            self.assertIn("no-store", response.headers["Cache-Control"])
