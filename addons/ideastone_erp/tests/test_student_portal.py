import base64
import uuid
from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestStudentPortal(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.student_user = new_test_user(self.env, login="student_portal_qa", groups="base.group_portal", partner_id=self.student.partner_id.id)
        self.student.user_id = self.student_user
        self.other = self.enrolled().student_id
        self.other_user = new_test_user(self.env, login="student_portal_other", groups="base.group_portal", partner_id=self.other.partner_id.id)
        self.other.user_id = self.other_user
        self.portal = self.env["campus.student.portal"].with_user(self.student_user)

    def request_payload(self, **changes):
        payload = {"type_id": self.env.ref("ideastone_erp.student_request_bonafide").id,
                   "key": uuid.uuid4().hex, "title": "QA bonafide", "description": "For education verification."}
        payload.update(changes)
        return payload

    def test_identity_context_and_direct_model_boundaries(self):
        self.assertEqual(self.portal.snapshot()["student"]["number"], self.student.gr_no)
        with self.assertRaises(AccessError):
            self.portal.snapshot(enrolment=self.other.course_detail_ids.id)
        with self.assertRaises(AccessError):
            self.env["campus.student.portal"].with_user(self.owner).snapshot()
        with self.assertRaises(AccessError):
            self.student.with_user(self.student_user).write({"first_name": "Unauthorized"})
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.student_user).get_owner_metrics()
        self.other.user_id = self.student_user
        with self.assertRaises(AccessError):
            self.portal.snapshot()

    def test_profile_policy_preferences_and_official_identity_lock(self):
        with self.assertRaises(AccessError):
            self.portal.act("profile", {"phone": "+919000000000"})
        self.env.company.campus_student_contact_edit = True
        with self.assertRaises(AccessError):
            self.portal.act("profile", {"first_name": "Changed"})
        with self.assertRaises(ValidationError):
            self.portal.act("profile", {"phone": "bad phone"})
        self.portal.act("profile", {"phone": "+919000000000", "city": "Erode"})
        self.assertEqual(self.student.phone, "+919000000000")
        self.assertEqual(self.portal.snapshot()["student"]["city"], "Erode")
        self.portal.act("preferences", {"notice_badge": False})
        self.assertFalse(self.portal.snapshot()["notice_badge"])

    def test_attendance_matches_college_policy_and_cancellation(self):
        session = self.session()
        sheet = self.sheet(session)
        sheet.action_campus_roster()
        sheet.attendance_line.filtered(lambda line: line.student_id == self.other).write({"campus_status": "absent"})
        sheet.attendance_done()
        data = self.portal.snapshot()
        self.assertEqual(data["attendance"]["rate"], 100)
        self.assertEqual(len(data["attendance"]["rows"]), 1)
        source = self.env["campus.dashboard"].with_user(self.owner)._attendance_rows(sheet.attendance_line.filtered(lambda line: line.student_id == self.student))
        self.assertEqual(source[0]["rate"], data["attendance"]["rate"])
        with self.assertRaises(AccessError):
            sheet.attendance_line.with_user(self.student_user).write({"present": False})
        session.write({"state": "cancel"})
        self.assertIsNone(self.portal.snapshot()["attendance"]["rate"])

    def test_unreleased_schedules_and_unpublished_marks_are_private(self):
        exam = self.exam()
        self.assertFalse(self.portal.snapshot()["exams"])
        with self.assertRaises(AccessError):
            exam.with_user(self.teacher).action_campus_release_schedule()
        exam.with_user(self.examiner).action_campus_release_schedule()
        self.assertEqual(len(self.portal.snapshot()["exams"]), 1)
        exam.with_user(self.teacher).action_campus_roster()
        exam.with_user(self.teacher).campus_result_ids.write({"marks": 75})
        self.assertFalse(self.portal.snapshot()["results"])
        exam.with_user(self.teacher).action_campus_submit()
        exam.with_user(self.examiner).action_campus_lock()
        exam.with_user(self.examiner).action_campus_publish()
        results = self.portal.snapshot()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["marks"], 75)
        self.assertEqual(results[0]["grade"], "P")

    def test_native_ledger_and_cross_student_receipt_denial(self):
        fee = self.fee(self.student)
        fee.action_campus_post()
        self.payment(fee.invoice_id, 300)
        other_fee = self.fee(self.other)
        other_fee.action_campus_post()
        foreign = self.payment(other_fee.invoice_id, 100).payment_id
        data = self.portal.snapshot()
        self.assertEqual(data["fees"]["assessed"], 500)
        self.assertEqual(data["fees"]["paid"], 300)
        self.assertEqual(data["fees"]["due"], 200)
        self.assertEqual(len(data["fees"]["payments"]), 1)
        with self.assertRaises(AccessError):
            self.portal._download("receipt", foreign.id)
        with self.assertRaises(AccessError):
            other_fee.invoice_id.with_user(self.student_user).read(["amount_total"])

    def test_notice_audience_and_durable_acknowledgement(self):
        model = self.env["campus.circular"].with_user(self.owner)
        notice = model.create({"name": "Student publication QA", "reference": "STUP-QA", "body": "<p>Published student notice</p>", "audience": "student", "campus_managed": True})
        notice.action_campus_publish()
        private = model.create({"name": "PRIVATE FACULTY NOTICE", "reference": "STUP-F", "body": "Private staff content", "audience": "faculty", "campus_managed": True})
        private.action_campus_publish()
        names = [n["name"] for n in self.portal.snapshot()["notices"]]
        self.assertIn(notice.name, names)
        self.assertNotIn(private.name, names)
        before = self.portal.snapshot()["unread"]
        self.portal.act("notice", {"notice_id": notice.id})
        self.portal.act("notice", {"notice_id": notice.id})
        self.assertEqual(self.portal.snapshot()["unread"], before - 1)
        with self.assertRaises(AccessError):
            self.portal.act("notice", {"notice_id": private.id})

    def test_request_retry_staff_workflow_notifications_and_document_scope(self):
        payload = self.request_payload()
        first = self.portal.act("request", payload)
        self.assertEqual(first, self.portal.act("request", payload))
        self.assertTrue(self.portal.act("request", self.request_payload())["existing"])
        rec = self.env["campus.service.request"].search([("portal_reference", "=", first["reference"])]).with_user(self.owner)
        self.assertEqual(rec.requester_id, self.student_user)
        with self.assertRaises(ValidationError):
            rec.action_portal_information()
        rec.write({"portal_reply": "Please confirm the intended recipient."})
        rec.action_portal_information()
        self.portal.act("reply", {"request_id": rec.id, "reply": "Scholarship office"})
        rec.action_approve()
        with self.assertRaises(ValidationError):
            self.portal.act("cancel", {"request_id": rec.id})
        rec.write({"portal_result_file": base64.b64encode(b"Official QA document"), "portal_result_filename": "issued.txt", "portal_reply": "The official document is available."})
        with self.assertRaises(AccessError):
            self.portal._download("request", rec.id)
        rec.action_portal_ready()
        self.assertEqual(self.portal._download("request", rec.id)[0], b"Official QA document")
        with self.assertRaises(AccessError):
            self.env["campus.student.portal"].with_user(self.other_user)._download("request", rec.id)
        self.assertGreater(self.portal.snapshot()["updates"], 0)
        self.portal.act("updates")
        self.assertEqual(self.portal.snapshot()["updates"], 0)
        with self.assertRaises(ValidationError):
            rec.unlink()

    def test_upload_and_request_identity_validation(self):
        with self.assertRaises(ValidationError):
            self.portal.act("request", self.request_payload(file=base64.b64encode(b"<html>unsafe</html>"), filename="fake.pdf"))
        with self.assertRaises(AccessError):
            self.portal.act("request", self.request_payload(attendance_id=99999999))
        valid = self.portal.act("request", self.request_payload(file=base64.b64encode(b"QA supporting text"), filename="evidence.txt", student_id=self.other.id))
        rec = self.env["campus.service.request"].search([("portal_reference", "=", valid["reference"])])
        self.assertEqual(rec.student_id, self.student)
        self.assertEqual(rec.filename, "evidence.txt")

    def test_disabled_college_catalogue_override_hides_global_template(self):
        template = self.env.ref("ideastone_erp.student_request_bonafide")
        local = template.with_user(self.owner).copy({"name": "College bonafide policy"})
        shown = self.portal.snapshot()["request_types"]
        self.assertIn(local.id, [row["id"] for row in shown])
        self.assertNotIn(template.id, [row["id"] for row in shown])
        with self.assertRaises(AccessError):
            template.with_user(self.owner).write({"active": False})
        local.with_user(self.owner).write({"active": False})
        self.assertNotIn(template.code, [row["code"] for row in self.portal.snapshot()["request_types"]])

    def test_local_day_bounds_and_inactive_identity(self):
        self.student_user.tz = "Asia/Kolkata"
        # 00:30 local time belongs to today even though its stored UTC date is yesterday.
        start = datetime.combine(self.today - timedelta(days=1), time(19, 0))
        session = self.session(start_datetime=start, end_datetime=start + timedelta(minutes=30))
        data = self.portal.snapshot(date_from=str(self.today), date_to=str(self.today))
        self.assertIn(session.id, [row["id"] for row in data["schedule"]])
        self.student.active = False
        with self.assertRaises(AccessError):
            self.portal.snapshot()
