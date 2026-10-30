import base64
import uuid
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture

PROOF = base64.b64encode(b"Synthetic participation certificate").decode()


@tagged("post_install", "-at_install")
class TestStudentOD(OwnerMVPFixture, TransactionCase):
    """Student On Duty requests: student portal, mentor review, HOD decision and proof cycle."""

    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.student_user = new_test_user(self.env, login="od_student", groups="base.group_portal", partner_id=self.student.partner_id.id)
        self.student.user_id = self.student_user
        self.other = self.enrolled().student_id
        self.other_user = new_test_user(self.env, login="od_other_student", groups="base.group_portal", partner_id=self.other.partner_id.id)
        self.other.user_id = self.other_user
        self.mentor = new_test_user(self.env, login="od_mentor", groups="openeducat_core.group_op_faculty")
        self.other_mentor = new_test_user(self.env, login="od_other_mentor", groups="openeducat_core.group_op_faculty")
        self.hod = new_test_user(self.env, login="od_hod", groups="ideastone_erp.group_od_hod_approver")
        self.hod.dept_id = self.department
        self.other_hod = new_test_user(self.env, login="od_other_hod", groups="ideastone_erp.group_od_hod_approver")
        self.other_hod.dept_id = self.department
        routing = self.env["campus.student.leave.routing"]
        self.route = routing.create({"name": "OD QA route", "student_id": self.student.id, "advisor_id": self.mentor.id, "hod_id": self.hod.id})
        self.other_route = routing.create({"name": "OD QA other route", "student_id": self.other.id,
                                           "advisor_id": self.other_mentor.id, "hod_id": self.other_hod.id})
        self.portal = self.env["campus.student.portal"].with_user(self.student_user)
        self.other_portal = self.env["campus.student.portal"].with_user(self.other_user)
        self.mentor_ui = self.env["campus.staff.od.ui"].with_user(self.mentor)
        self.hod_ui = self.env["campus.hod.od.ui"].with_user(self.hod)
        # The student's local date drives every portal date check.
        self.day = fields.Date.context_today(self.portal)

    def submit(self, portal=None, operation="od_submit", **changes):
        payload = {"key": uuid.uuid4().hex, "name": "Inter-college symposium", "purpose": "Paper presentation",
                   "venue": "Partner college auditorium", "od_date_from": str(self.day), "od_date_to": str(self.day),
                   "od_from_session": "forenoon", "od_to_session": "afternoon"}
        payload.update(changes)
        (self.portal if portal is None else portal).act(operation, payload)
        return self.env["campus.student.od"].search([("submission_key", "=", payload["key"])])

    def od_data(self, portal=None):
        return (self.portal if portal is None else portal).snapshot()["od"]

    def actions(self, record):
        return record.event_ids.sorted("id").mapped("action")

    def test_hod_navigation_opens_hod_workspace_and_keeps_mentor_separate(self):
        for user in (self.hod, self.mentor):
            self.env["op.faculty"].create({"first_name": user.name, "last_name": "OD",
                "birth_date": "1980-01-01", "gender": "male", "partner_id": user.partner_id.id,
                "user_id": user.id, "company_id": self.env.company.id, "main_department_id": self.department.id})
        dashboard = self.env["campus.dashboard"]
        hod_data = dashboard.with_user(self.hod).get_overview()
        mentor_data = dashboard.with_user(self.mentor).get_overview()
        for data, action in [(hod_data, "ideastone_erp.action_hod_od_management"),
                             (mentor_data, "ideastone_erp.action_staff_od_management")]:
            od = next((module for module in data["faculty_modules"] if module["key"] == "od"), None)
            self.assertTrue(od, (action, data["faculty_modules"]))
            self.assertEqual([item["action"] for item in od["items"]], [action])
            self.assertEqual(od["items"][0]["action_id"], self.env.ref(action).id)
        self.assertEqual(self.env.ref("ideastone_erp.action_hod_od_management").tag, "ideastone_erp.hod_od_management")
        self.assertEqual(self.env["campus.staff.od.ui"].with_user(self.hod).get_page_data()["role"], "hod")
        self.assertNotEqual(self.mentor_ui.get_page_data().get("role"), "hod")
        with self.assertRaises(AccessError):
            self.env["campus.hod.od.ui"].with_user(self.mentor).get_page_data()

    def test_general_od_flows_from_student_to_mentor_to_hod(self):
        # Colleges run several semesters at once; a later-starting one must not hide this term's requests.
        self.env["op.academic.term"].create({"name": "OD QA concurrent semester", "academic_year_id": self.year.id,
            "term_start_date": self.day, "term_end_date": self.term.term_end_date})
        self.assertEqual(self.student.course_detail_ids.academic_term_id, self.term)
        before = self.od_data()
        self.assertTrue(before["can_submit"])
        self.assertIn(("on-duty", "OD Management", "briefcase"), self.portal.snapshot()["navigation"])

        key = uuid.uuid4().hex
        record = self.submit(key=key)
        self.assertEqual((record.state, record.category, record.token_cost), ("pending_mentor", "undetermined", 1))
        self.assertEqual((record.mentor_id, record.hod_id, record.initiated_by_id), (self.mentor, self.hod, self.student_user))
        # Retrying the same form submission must not create a second request.
        self.submit(key=key)
        self.assertEqual(self.env["campus.student.od"].search_count([("student_id", "=", self.student.id)]), 1)
        with self.assertRaisesRegex(ValidationError, "already covers"):
            self.submit()
        data = self.od_data()
        self.assertEqual((data["reserved"], data["used"], data["pending"]), (1, 0, 1))
        self.assertEqual(data["remaining"], before["remaining"] - 1)

        page = self.mentor_ui.get_page_data()
        self.assertEqual([row["id"] for row in page["rows"]], [record.id])
        self.assertTrue(page["rows"][0]["can_review"])
        # The HOD cannot act before the mentor has forwarded the request.
        with self.assertRaisesRegex(ValidationError, "Mentor authorization"):
            self.hod_ui.decide(record.id, "approve", category="general")
        self.assertEqual(self.mentor_ui.review_request(record.id, "forward", "Eligible event")["state"], "pending_hod")
        with self.assertRaisesRegex(ValidationError, "no longer awaiting"):
            self.mentor_ui.review_request(record.id, "forward")
        self.assertEqual((record.mentor_reviewed_by_id, record.mentor_note), (self.mentor, "Eligible event"))

        hod_page = self.hod_ui.get_page_data()
        self.assertEqual([row["id"] for row in hod_page["rows"] if row["can_decide"]], [record.id])
        with self.assertRaisesRegex(ValidationError, "General or Special"):
            self.hod_ui.decide(record.id, "approve")
        self.assertEqual(self.hod_ui.decide(record.id, "approve", category="general")["state"], "completed")
        self.assertEqual((record.category, record.hod_reviewed_by_id), ("general", self.hod))
        data = self.od_data()
        self.assertEqual((data["used"], data["reserved"], data["pending"]), (1, 0, 0))
        self.assertEqual(self.actions(record), ["Submitted for mentor review", "Forwarded to HOD: Eligible event", "HOD approved General OD"])

    def test_mentor_return_redraft_and_rejection(self):
        draft = self.submit(operation="od_draft")
        self.assertEqual(draft.state, "draft")
        self.assertEqual(self.od_data()["reserved"], 0)
        self.portal.act("od_activate", {"od_id": draft.id})
        self.assertEqual(draft.state, "pending_mentor")

        with self.assertRaisesRegex(ValidationError, "review note"):
            self.mentor_ui.review_request(draft.id, "return")
        with self.assertRaisesRegex(ValidationError, "valid mentor decision"):
            self.mentor_ui.review_request(draft.id, "approve")
        self.mentor_ui.review_request(draft.id, "return", "Attach the invitation")
        self.assertEqual(draft.state, "returned")
        row = next(row for row in self.od_data()["rows"] if row["id"] == draft.id)
        self.assertEqual((row["mentor_note"], row["can_submit_draft"]), ("Attach the invitation", True))

        self.portal.act("od_activate", {"od_id": draft.id})
        self.mentor_ui.review_request(draft.id, "forward")
        with self.assertRaisesRegex(ValidationError, "reason"):
            self.hod_ui.decide(draft.id, "reject")
        self.hod_ui.decide(draft.id, "reject", note="Event outside the approved list")
        self.assertEqual((draft.state, draft.hod_note), ("rejected", "Event outside the approved list"))
        # A rejected request frees its dates and token.
        self.assertEqual(self.submit().state, "pending_mentor")

    def test_special_od_proof_cycle(self):
        record = self.submit()
        self.mentor_ui.review_request(record.id, "forward")
        with self.assertRaisesRegex(ValidationError, "deadline"):
            self.hod_ui.decide(record.id, "approve", category="special", proof_requirements="Certificate")
        with self.assertRaisesRegex(ValidationError, "deadline"):
            self.hod_ui.decide(record.id, "approve", category="special", proof_requirements="Certificate",
                               proof_deadline=str(self.day - timedelta(days=1)))
        self.hod_ui.decide(record.id, "approve", category="special", proof_requirements="Participation certificate",
                           proof_deadline=str(self.day))
        self.assertEqual((record.state, record.category), ("withheld", "special"))
        data = self.od_data()
        self.assertTrue(data["proof_ready"])
        self.assertEqual(data["reserved"], 1)

        with self.assertRaisesRegex(ValidationError, "Attach"):
            self.portal.act("od_proof", {"od_id": record.id})
        with self.assertRaises(ValidationError):
            self.portal.act("od_proof", {"od_id": record.id, "file": PROOF, "filename": "proof.exe"})
        self.portal.act("od_proof", {"od_id": record.id, "file": PROOF, "filename": "certificate.txt"})
        self.assertEqual(record.state, "proof_review")
        proof = self.hod_ui.get_proof(record.id)
        self.assertEqual((proof["filename"], base64.b64decode(proof["content"])), ("certificate.txt", b"Synthetic participation certificate"))

        with self.assertRaisesRegex(ValidationError, "correction"):
            self.hod_ui.decide(record.id, "return_proof")
        self.hod_ui.decide(record.id, "return_proof", note="Upload the signed copy",
                           proof_requirements="Signed certificate", proof_deadline=str(self.day))
        self.assertEqual((record.state, record.proof_requirements), ("withheld", "Signed certificate"))
        self.portal.act("od_proof", {"od_id": record.id, "file": PROOF, "filename": "signed.txt"})
        self.hod_ui.decide(record.id, "accept_proof")
        self.assertEqual(record.state, "completed")
        self.assertEqual(self.od_data()["used"], 1)
        self.assertEqual(self.actions(record)[-1], "HOD verified proof; OD completed")

    def test_missing_proof_expires_only_after_the_deadline(self):
        record = self.submit()
        self.mentor_ui.review_request(record.id, "forward")
        # Two-day margins keep this independent of which user's time zone defines "today".
        self.hod_ui.decide(record.id, "approve", category="special", proof_requirements="Certificate",
                           proof_deadline=str(self.day + timedelta(days=2)))
        model = self.env["campus.student.od"]
        model._cron_expire_proof()
        self.assertEqual(record.state, "withheld")
        with self.assertRaisesRegex(AccessError, "overdue"):
            record.sudo().with_context(campus_od_proof_expiry=True).write({"state": "invalid"})

        # Backdate the deadline the way time would: the workflow itself never allows it.
        self.env.cr.execute("UPDATE campus_student_od SET proof_deadline = %s WHERE id = %s", (self.day - timedelta(days=2), record.id))
        record.invalidate_recordset(["proof_deadline"])
        with self.assertRaisesRegex(AccessError, "Proof can be submitted only"):
            self.portal.act("od_proof", {"od_id": record.id, "file": PROOF, "filename": "late.txt"})
        model._cron_expire_proof()
        self.assertEqual(record.state, "invalid")
        self.assertEqual(self.actions(record)[-1], "Proof deadline passed; OD invalidated")
        self.assertEqual(self.od_data()["reserved"], 0)

    def test_semester_token_allowance(self):
        self.env.company.campus_od_default_tokens = 1
        first = self.submit()
        self.assertFalse(self.od_data()["can_submit"])
        later = str(self.day + timedelta(days=1)) if self.day < self.term.term_end_date else str(self.day - timedelta(days=1))
        with self.assertRaisesRegex(ValidationError, "remaining semester OD tokens"):
            self.submit(od_date_from=later, od_date_to=later)
        # Drafts may be saved, but not submitted beyond the allowance.
        draft = self.submit(operation="od_draft", od_date_from=later, od_date_to=later)
        with self.assertRaisesRegex(ValidationError, "remaining semester OD tokens"):
            self.portal.act("od_activate", {"od_id": draft.id})
        self.portal.act("od_cancel", {"od_id": first.id})
        self.assertEqual(first.state, "cancelled")
        self.portal.act("od_activate", {"od_id": draft.id})
        self.assertEqual(draft.state, "pending_mentor")

        self.student.course_detail_ids.campus_od_tokens_override = 5
        self.env.company.campus_od_token_rule = "day"
        self.assertEqual(self.od_data()["total"], 5)
        with self.assertRaisesRegex(ValidationError, "within your active semester"):
            self.submit(od_date_from=str(self.term.term_start_date - timedelta(days=1)))
        with self.assertRaisesRegex(ValidationError, "end session"):
            self.submit(od_from_session="afternoon", od_to_session="forenoon")
        with self.assertRaisesRegex(ValidationError, "Reload"):
            self.submit(key="not-a-valid-key")

    def test_access_boundaries(self):
        record = self.submit()
        mine = {"od_id": record.id}
        # Another student cannot see or act on this request.
        self.assertNotIn(record.id, [row["id"] for row in self.od_data(self.other_portal)["rows"]])
        for operation in ("od_cancel", "od_activate", "od_proof"):
            with self.assertRaisesRegex(AccessError, "does not belong"):
                self.other_portal.act(operation, dict(mine, file=PROOF, filename="x.txt"))
        # Only the assigned mentor and HOD may decide it.
        other_mentor_ui = self.env["campus.staff.od.ui"].with_user(self.other_mentor)
        self.assertEqual(other_mentor_ui.get_page_data()["rows"], [])
        with self.assertRaisesRegex(AccessError, "not assigned"):
            other_mentor_ui.review_request(record.id, "forward")
        self.mentor_ui.review_request(record.id, "forward")
        with self.assertRaisesRegex(AccessError, "not assigned"):
            self.env["campus.hod.od.ui"].with_user(self.other_hod).decide(record.id, "approve", category="general")
        with self.assertRaisesRegex(AccessError, "assigned OD HOD"):
            self.env["campus.hod.od.ui"].with_user(self.mentor).get_page_data()
        with self.assertRaisesRegex(AccessError, "No submitted proof"):
            self.hod_ui.get_proof(record.id)
        # A HOD outside the student's department sees nothing.
        self.hod.dept_id = self.env["op.department"].create({"name": "OD QA other department", "code": "ODQAX"})
        with self.assertRaisesRegex(AccessError, "not assigned"):
            self.hod_ui.decide(record.id, "approve", category="general")
        self.hod.dept_id = self.department

        # The records and their history cannot be changed outside the workflow.
        with self.assertRaises(AccessError):
            record.sudo().write({"state": "completed"})
        with self.assertRaises(AccessError):
            record.sudo().with_context(campus_od_mentor_review=True).write({"state": "pending_hod"})
        with self.assertRaises(AccessError):
            record.sudo().unlink()
        with self.assertRaises(AccessError):
            self.env["campus.student.od"].sudo().create({"name": "Forged"})
        event = record.event_ids[:1]
        with self.assertRaises(AccessError):
            event.sudo().write({"action": "Forged"})
        with self.assertRaises(AccessError):
            event.sudo().unlink()
        with self.assertRaises(AccessError):
            self.portal.act("od_cancel", mine)
        self.hod_ui.decide(record.id, "approve", category="general")
        self.assertEqual(record.state, "completed")
