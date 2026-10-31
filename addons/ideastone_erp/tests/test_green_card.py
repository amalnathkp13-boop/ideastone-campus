import base64
import uuid
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestGreenCard(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.student_user = new_test_user(self.env, login="green_student", groups="base.group_portal", partner_id=self.student.partner_id.id)
        self.student.user_id = self.student_user
        self.hod = new_test_user(self.env, login="green_hod", groups="openeducat_core.group_op_faculty,ideastone_erp.group_od_hod_approver")
        self.hod.dept_id = self.department
        self.route = self.env["campus.student.leave.routing"].create({"name": "Green Card route", "student_id": self.student.id,
            "advisor_id": self.teacher.id, "hod_id": self.hod.id})
        self.ui = self.env["campus.green.card.ui"].with_user(self.student_user)
        self.mentor_ui = self.env["campus.green.card.ui"].with_user(self.teacher)
        self.hod_ui = self.env["campus.green.card.ui"].with_user(self.hod)

    def payload(self, **values):
        day = str(self.today + timedelta(days=7))
        return dict({"key": uuid.uuid4().hex, "from": day, "to": day, "fromSession": "FN", "toSession": "AN",
                     "type": "announced", "reason": "Family appointment requiring leave."}, **values)

    def test_student_mentor_hod_proof_workflow_preserves_attendance(self):
        sheet = self.sheet(self.session())
        sheet.action_campus_roster()
        sheet.attendance_line.campus_status = "absent"
        sheet.attendance_done()
        payload = self.payload()
        request_id = self.ui.submit(payload)
        self.assertEqual(self.ui.submit(payload), request_id)
        self.assertFalse(self.hod_ui.get_workspace()["rows"])
        with self.assertRaises(AccessError):
            self.hod_ui.review(request_id, "approve")
        self.mentor_ui.review(request_id, "parent", "Parent confirmed the family appointment.")
        self.mentor_ui.review(request_id, "approve")
        self.assertEqual(self.hod_ui.get_workspace()["rows"][0]["state"], "hod")
        self.hod_ui.review(request_id, "proof", "Please upload the appointment letter.")
        with self.assertRaises(ValidationError):
            self.hod_ui.review(request_id, "approve")
        with self.assertRaises(ValidationError):
            self.ui.respond(request_id, {})
        self.ui.respond(request_id, {"filename": "appointment.pdf", "file": base64.b64encode(b"%PDF-1.4\nQA proof")})
        self.hod_ui.review(request_id, "approve", "Evidence reviewed.")
        row = self.ui.get_workspace()["rows"][0]
        self.assertEqual((row["state"], row["days"], row["parent"]), ("approved", 1, True))
        self.assertTrue(row["mentorAt"] and row["hodAt"])
        with self.assertRaises(AccessError):
            self.hod_ui.review(request_id, "approve")
        self.assertEqual(sheet.state, "done")
        self.assertFalse(sheet.attendance_line.present)
        self.assertEqual(row["history"][0]["by"], self.student_user.name)

    def test_returned_hod_request_restarts_mentor_authorization(self):
        request_id = self.ui.submit(self.payload())
        self.mentor_ui.review(request_id, "approve")
        self.hod_ui.review(request_id, "return", "Explain why the full day is needed.")
        self.ui.respond(request_id, {"reason": "The appointment requires a full day of travel."})
        self.assertFalse(self.hod_ui.get_workspace()["rows"])
        self.assertEqual(self.mentor_ui.get_workspace()["rows"][0]["state"], "mentor")
        self.mentor_ui.review(request_id, "approve")
        self.hod_ui.review(request_id, "reject", "The requested period is not authorized.")
        self.assertEqual(self.ui.get_workspace()["rows"][0]["state"], "rejected")

    def test_session_ranges_overlap_validation_and_upload_formats(self):
        first = self.ui.submit(self.payload(toSession="FN"))
        second = self.ui.submit(self.payload(fromSession="AN"))
        self.assertNotEqual(first, second)
        self.assertEqual([row["days"] for row in self.ui.get_workspace()["rows"]], [.5, .5])
        for payload in [self.payload(), self.payload(fromSession="AN", toSession="FN"),
                        self.payload(type="unannounced"), self.payload(reason="short")]:
            with self.assertRaises(ValidationError):
                self.ui.submit(payload)
        later = str(self.today + timedelta(days=9))
        with self.assertRaises(ValidationError):
            self.ui.submit(self.payload(**{"from": later, "to": later, "filename": "proof.pdf", "file": base64.b64encode(b"not a pdf")}))

    def test_roles_department_boundaries_and_evidence_are_server_guarded(self):
        request_id = self.ui.submit(self.payload())
        for user in (self.owner, self.outsider):
            with self.assertRaises(AccessError):
                self.env["campus.green.card.ui"].with_user(user).get_workspace()
        with self.assertRaises(AccessError):
            self.hod_ui.get_workspace("mentor")
        other = self.enrolled().student_id
        other_user = new_test_user(self.env, login="green_other_student", groups="base.group_portal", partner_id=other.partner_id.id)
        other.user_id = other_user
        other_ui = self.env["campus.green.card.ui"].with_user(other_user)
        self.assertFalse(other_ui.get_workspace()["rows"])
        with self.assertRaises(AccessError):
            other_ui.respond(request_id, {"reason": "Attempted cross-student update."})
        rec = self.env["campus.student.leave"].browse(request_id)
        with self.assertRaises(AccessError):
            rec.with_user(self.teacher).write({"green_mentor_at": "2026-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            rec.with_user(self.hod).write({"state": "approved"})
        self.mentor_ui.review(request_id, "approve")
        foreign_dept = self.env["op.department"].create({"name": "Other Green Card department", "code": "GREENOTHER"})
        self.hod.dept_id = foreign_dept
        self.assertFalse(self.hod_ui.get_workspace()["rows"])
        with self.assertRaises(AccessError):
            self.hod_ui.review(request_id, "approve")

    def test_navigation_adds_only_the_matching_portal_action(self):
        modules = self.env["campus.dashboard"].with_user(self.teacher).get_overview()["faculty_modules"]
        self.assertNotIn("green-card", [module["key"] for module in modules])
        green = next(module for module in modules if module["key"] == "attendance")
        self.assertEqual(green["items"][0]["action"], "ideastone_erp.action_green_card_mentor")
        self.assertNotIn("green-card", [m["key"] for m in self.env["campus.dashboard"].with_user(self.owner).get_overview()["faculty_modules"]])
        self.assertIn("green-card", [n[0] for n in self.env["campus.student.portal"].with_user(self.student_user).snapshot()["navigation"]])

    def test_existing_principal_policy_is_not_bypassed(self):
        principal = new_test_user(self.env, login="green_principal", groups="base.group_user")
        self.route.principal_id = principal
        request_id = self.ui.submit(self.payload())
        self.mentor_ui.review(request_id, "approve")
        self.hod_ui.review(request_id, "approve")
        self.assertEqual(self.ui.get_workspace()["rows"][0]["state"], "principal")
        self.env["campus.student.leave"].browse(request_id).with_user(principal).action_approve()
        self.assertEqual(self.ui.get_workspace()["rows"][0]["state"], "approved")
