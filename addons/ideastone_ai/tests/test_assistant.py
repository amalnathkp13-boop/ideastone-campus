import json
from unittest.mock import patch

from odoo.addons.ideastone_ai.models import assistant as assistant_module
from odoo.addons.ideastone_erp.tests.test_owner_mvp import OwnerMVPFixture
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


class FakeResponse:
    def __init__(self, status_code=200, content="Answer text", raw=None):
        self.status_code = status_code
        self._body = raw if raw is not None else {"choices": [{"message": {"content": content}}]}

    def json(self):
        return self._body


@tagged("post_install", "-at_install")
class TestCampusAssistant(OwnerMVPFixture, TransactionCase):
    """Campus Assistant: configuration gate, grounding context, privacy and audit log."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.sudo().write({"campus_ai_enabled": True, "campus_ai_endpoint": "https://ai.example.test/v1",
                                   "campus_ai_model": "test-model", "campus_ai_api_key": "sk-test", "campus_ai_monthly_limit": 3})
        self.assistant = self.env["campus.ai.assistant"].with_user(self.owner)
        self.calls = []

    def fake_post(self, response=None):
        calls = self.calls
        def post(url, json=None, headers=None, timeout=None):
            calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
            return response or FakeResponse()
        return post

    def test_status_and_configuration_gate(self):
        status = self.assistant.get_status()
        self.assertTrue(status["configured"])
        self.assertEqual((status["model"], status["endpoint_host"], status["used"], status["limit"]), ("test-model", "ai.example.test", 0, 3))
        self.company.sudo().campus_ai_enabled = False
        self.assertFalse(self.assistant.get_status()["configured"])
        with patch.object(assistant_module.requests, "post", self.fake_post()):
            with self.assertRaisesRegex(UserError, "not configured"):
                self.assistant.ask("How many students?")
        self.assertEqual(self.calls, [])
        with self.assertRaises(AccessError):
            self.env["campus.ai.assistant"].with_user(self.outsider).get_status()
        with self.assertRaises(AccessError):
            self.env["campus.ai.assistant"].with_user(self.readonly).ask("Anything?")
        with self.assertRaises(ValidationError):
            self.company.sudo().campus_ai_endpoint = "ftp://nope"

    def test_ask_is_grounded_shares_only_aggregates_and_is_logged(self):
        student = self.enrolled().student_id
        with patch.object(assistant_module.requests, "post", self.fake_post(FakeResponse(content="There are 1 active students."))):
            result = self.assistant.ask("How many active students are there?")
        self.assertEqual(result["answer"], "There are 1 active students.")
        call = self.calls[0]
        self.assertEqual(call["url"], "https://ai.example.test/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(call["json"]["model"], "test-model")
        payload = call["json"]["messages"][1]["content"]
        self.assertIn("QUESTION: How many active students are there?", payload)
        data = json.loads(payload.split("DATA:\n", 1)[1].split("\n\nQUESTION:")[0])
        self.assertEqual(data["college"], self.company.name)
        self.assertEqual(data["figures"]["Active students"], 1)
        self.assertIn("student_success", data)
        # Privacy: no personal record travels with the question.
        self.assertNotIn(student.name, payload)
        self.assertNotIn(student.partner_id.email or "@", payload)
        log = self.env["campus.ai.log"].sudo().search([("company_id", "=", self.company.id)])
        self.assertEqual(len(log), 1)
        self.assertEqual((log.feature, log.ok, log.user_id, log.model_name), ("ask", True, self.owner, "test-model"))
        self.assertIn("overview figures", log.shared)
        with self.assertRaises(AccessError):
            log.with_user(self.owner).unlink()
        with self.assertRaises(AccessError):
            log.with_user(self.owner).write({"ok": False})

    def test_provider_failures_and_monthly_limit(self):
        with patch.object(assistant_module.requests, "post", self.fake_post(FakeResponse(status_code=503))):
            with self.assertRaisesRegex(UserError, "HTTP 503"):
                self.assistant.ask("Anything?")
        with patch.object(assistant_module.requests, "post", self.fake_post(FakeResponse(raw={"choices": []}))):
            with self.assertRaisesRegex(UserError, "empty answer"):
                self.assistant.ask("Anything?")
        failed = self.env["campus.ai.log"].sudo().search([("ok", "=", False)])
        self.assertEqual(len(failed), 2)
        self.assertTrue(all(failed.mapped("error")))
        with patch.object(assistant_module.requests, "post", self.fake_post()):
            for _index in range(3):
                self.assistant.ask("Count?")
            with self.assertRaisesRegex(UserError, "call limit"):
                self.assistant.ask("One more?")
        self.assertEqual(self.assistant.get_status()["used"], 3)
        with self.assertRaises(ValidationError):
            self.assistant.ask("x" * 1001)

    def test_notice_draft_is_escaped_and_opens_a_circular(self):
        text = "TITLE: Internal assessment 2\n\nAll third-year students will sit IA-2 from 10 to 14 November.\n\nCarry your <b>hall ticket</b> & ID card."
        with patch.object(assistant_module.requests, "post", self.fake_post(FakeResponse(content=text))):
            draft = self.assistant.draft_notice("IA-2 for third years, 10-14 Nov, hall tickets from exam cell", "student", "formal")
        self.assertEqual(draft["title"], "Internal assessment 2")
        self.assertIn("<p>All third-year students will sit IA-2 from 10 to 14 November.</p>", draft["body_html"])
        self.assertIn("&lt;b&gt;hall ticket&lt;/b&gt; &amp; ID card", draft["body_html"])
        self.assertNotIn("<b>", draft["body_html"])
        action = draft["create_action"]
        self.assertEqual((action["res_model"], action["context"]["default_audience"], action["context"]["default_name"]),
                         ("campus.circular", "student", "Internal assessment 2"))
        self.assertEqual(self.calls[0]["json"]["messages"][1]["content"], "IA-2 for third years, 10-14 Nov, hall tickets from exam cell")
        with self.assertRaises(ValidationError):
            self.assistant.draft_notice("x", "everyone", "formal")

    def test_feedback_summary_is_anonymous(self):
        student = self.enrolled().student_id
        other = self.enrolled().student_id
        self.env["campus.feedback"].sudo().create([
            {"name": "Student feedback 2026-27", "respondent_id": self.teacher.id, "student_id": student.id, "kind": "student", "period": "2026-27", "score": 2, "comments": "Library closes too early for hostel students."},
            {"name": "Student feedback 2026-27 (2)", "respondent_id": self.owner.id, "student_id": other.id, "kind": "student", "period": "2026-27", "score": 4, "comments": "Labs are well equipped."},
        ])
        self.assertEqual(self.assistant.feedback_periods("student"), ["2026-27"])
        with patch.object(assistant_module.requests, "post", self.fake_post(FakeResponse(content="Theme 1: library hours."))):
            result = self.assistant.summarise_feedback("2026-27", "student")
        self.assertEqual((result["responses"], result["with_comments"], result["average"]), (2, 2, 3.0))
        sent = self.calls[0]["json"]["messages"][1]["content"]
        self.assertIn("Library closes too early", sent)
        self.assertNotIn(student.name, sent)
        self.assertNotIn(self.teacher.name, sent)
        with self.assertRaisesRegex(UserError, "No parent feedback"):
            with patch.object(assistant_module.requests, "post", self.fake_post()):
                self.assistant.summarise_feedback("2026-27", "parent")
