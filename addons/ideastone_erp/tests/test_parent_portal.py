import base64
import uuid
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestParentPortal(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.first = self.enrolled().student_id
        self.second = self.enrolled().student_id
        self.foreign = self.enrolled().student_id
        self.user = new_test_user(self.env, login="parent_portal_qa", groups="base.group_portal", tz="Asia/Kolkata")
        self.other_parent = new_test_user(self.env, login="parent_portal_other", groups="base.group_portal", tz="Asia/Kolkata")
        relation = self.env["op.parent.relationship"].create({"name": "QA guardian"})
        self.link = self.env["op.parent"].create({"name": self.user.partner_id.id, "user_id": self.user.id,
            "relationship_id": relation.id, "student_ids": [(6, 0, (self.first | self.second).ids)]})
        self.other_link = self.env["op.parent"].create({"name": self.other_parent.partner_id.id, "user_id": self.other_parent.id,
            "relationship_id": relation.id, "student_ids": [(6, 0, self.first.ids)]})
        self.portal = self.env["campus.parent.portal"].with_user(self.user)

    def payload(self, **changes):
        data = {"key": uuid.uuid4().hex, "type_id": self.env.ref("ideastone_erp.parent_enquiry").id,
                "title": "Parent enquiry", "description": "Please review this question."}
        data.update(changes)
        return data

    def test_linked_child_selection_and_invalid_context(self):
        self.assertEqual(len(self.portal.snapshot()["children"]), 2)
        self.assertEqual(self.portal.snapshot(self.second.id)["student_id"], self.second.id)
        self.assertNotIn("phone", self.portal.snapshot()["student"])
        for child in [self.foreign.id, "bad-id", -1]:
            with self.assertRaises(AccessError):
                self.portal.snapshot(child)
        with self.assertRaises(AccessError):
            self.portal.snapshot(self.first.id, self.second.course_detail_ids.id)
        for user in [self.owner, new_test_user(self.env, login="parent_unlinked", groups="base.group_portal")]:
            with self.assertRaises(AccessError):
                self.env["campus.parent.portal"].with_user(user).snapshot()

    def test_revocation_archival_and_college_scope(self):
        self.link.active = False
        with self.assertRaises(AccessError):
            self.portal.snapshot()
        self.link.active = True
        self.first.write({"active": False, "campus_status_reason": "QA archive to verify parent access revocation"})
        with self.assertRaises(AccessError):
            self.portal.snapshot(self.first.id)
        self.first.write({"active": True, "campus_status_reason": "QA restore after revocation check"})
        other = self.env["res.company"].create({"name": "Another college"})
        self.user.write({"company_id": other.id, "company_ids": [(6, 0, other.ids)]})
        with self.assertRaises(AccessError):
            self.portal.snapshot(self.first.id)

    def test_parent_does_not_mutate_official_or_student_records(self):
        for operation in ["profile", "feedback", "payment", "submission", "updates"]:
            with self.assertRaises(AccessError):
                self.portal.act(operation, self.first.id, {})
        with self.assertRaises(AccessError):
            self.first.with_user(self.user).write({"first_name": "Forged"})
        with self.assertRaises(AccessError):
            self.env["campus.student.portal"].with_user(self.user).snapshot()
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.user).get_owner_metrics()

    def test_fee_ledgers_and_downloads_follow_selected_child(self):
        fee = self.fee(self.first)
        fee.action_campus_post()
        payment = self.payment(fee.invoice_id, 300).payment_id
        other_fee = self.fee(self.second)
        other_fee.action_campus_post()
        foreign_payment = self.payment(other_fee.invoice_id, 50).payment_id
        first = self.portal.snapshot(self.first.id)
        second = self.portal.snapshot(self.second.id)
        self.assertEqual(first["fees"]["due"], 200)
        self.assertEqual(second["fees"]["due"], 450)
        self.assertIn("child=" + str(self.first.id), first["fees"]["payments"][0]["url"])
        self.assertEqual(first["fees"]["payments"][0]["id"], payment.id)
        with self.assertRaises(AccessError):
            self.portal.with_context(parent_child=self.first.id)._download("receipt", foreign_payment.id)
        self.link.student_ids = [(6, 0, self.second.ids)]
        with self.assertRaises(AccessError):
            self.portal.with_context(parent_child=self.first.id)._download("receipt", payment.id)

    def test_published_attendance_and_marks_only(self):
        sheet = self.sheet(self.session())
        sheet.action_campus_roster()
        self.assertIsNone(self.portal.snapshot(self.first.id)["attendance"]["rate"])
        sheet.attendance_done()
        self.assertEqual(self.portal.snapshot(self.first.id)["attendance"]["rate"], 100)
        no_data = self.portal.snapshot(self.first.id, date_from=str(self.today + timedelta(days=1)), date_to=str(self.today + timedelta(days=2)))
        self.assertIsNone(no_data["attendance"]["rate"])
        exam = self.exam()
        self.assertFalse(self.portal.snapshot(self.first.id)["exams"])
        exam.with_user(self.examiner).action_campus_release_schedule()
        self.assertEqual(len(self.portal.snapshot(self.first.id)["exams"]), 1)
        exam.with_user(self.teacher).action_campus_roster()
        exam.with_user(self.teacher).campus_result_ids.write({"marks": 75})
        self.assertFalse(self.portal.snapshot(self.first.id)["results"])
        exam.with_user(self.teacher).action_campus_submit()
        exam.with_user(self.examiner).action_campus_lock()
        exam.with_user(self.examiner).action_campus_publish()
        self.assertEqual(self.portal.snapshot(self.first.id)["results"][0]["marks"], 75)

    def test_parent_notice_scope_and_independent_read_states(self):
        model = self.env["campus.circular"].with_user(self.owner)
        notice = model.create({"name": "Parent published notice", "reference": "PARENT-QA", "body": "<p>School update</p>", "audience": "parent", "campus_managed": True, "parent_pinned": True})
        notice.action_campus_publish()
        private = model.create({"name": "Staff private notice", "reference": "PARENT-STAFF", "body": "Private", "audience": "faculty", "campus_managed": True})
        private.action_campus_publish()
        initial = self.portal.snapshot(self.first.id)
        self.assertNotIn(private.id, [n["id"] for n in initial["notices"]])
        self.portal.act("notice", self.first.id, {"notice_id": notice.id})
        self.assertTrue(self.portal.snapshot(self.first.id)["notices"][0]["read"])
        self.assertFalse(self.portal.snapshot(self.second.id)["notices"][0]["read"])
        self.assertFalse(self.env["campus.parent.portal"].with_user(self.other_parent).snapshot(self.first.id)["notices"][0]["read"])
        with self.assertRaises(AccessError):
            self.portal.act("notice", self.first.id, {"notice_id": private.id})

    def test_request_staff_lifecycle_and_parent_isolation(self):
        payload = self.payload()
        result = self.portal.act("request", self.first.id, payload)
        self.assertEqual(result, self.portal.act("request", self.first.id, payload))
        own = self.portal._requests(self.first)
        self.assertEqual(len(own), 1)
        self.assertFalse(self.portal.snapshot(self.second.id)["requests"])
        self.assertFalse(self.env["campus.parent.portal"].with_user(self.other_parent).snapshot(self.first.id)["requests"])
        own = own.with_user(self.owner)
        own.portal_reply = "Please provide the preferred meeting date."
        own.action_portal_information()
        self.portal.act("reply", self.first.id, {"request_id": own.id, "reply": "Monday morning"})
        self.assertEqual(own.state, "submitted")
        own.action_approve()
        own.portal_reply = "Meeting confirmed"
        own.action_done()
        self.assertEqual(self.portal.snapshot(self.first.id)["requests"][0]["state"], "done")
        with self.assertRaises(AccessError):
            self.portal.act("cancel", self.second.id, {"request_id": own.id})
        with self.assertRaises(AccessError):
            self.portal.act("request", self.first.id, self.payload(type_id=self.env.ref("ideastone_erp.student_request_bonafide").id))

    def test_absence_request_keeps_attendance_unchanged_and_dates_immutable(self):
        sheet = self.sheet(self.session())
        sheet.action_campus_roster()
        sheet.attendance_done()
        before = self.portal.snapshot(self.first.id)["attendance"]
        kind = self.env.ref("ideastone_erp.parent_absence")
        with self.assertRaises(ValidationError):
            self.portal.act("request", self.first.id, self.payload(type_id=kind.id))
        payload = self.payload(type_id=kind.id, absence_from=str(self.today), absence_to=str(self.today))
        result = self.portal.act("request", self.first.id, payload)
        record = self.portal._requests(self.first)
        self.assertEqual(record.parent_absence_from, self.today)
        self.assertEqual(before, self.portal.snapshot(self.first.id)["attendance"])
        payload["absence_to"] = str(self.today + timedelta(days=1))
        self.assertEqual(result, self.portal.act("request", self.first.id, payload))
        self.assertEqual(record.parent_absence_to, self.today)

    def test_only_explicitly_released_verified_documents(self):
        requirement = self.env["campus.admission.requirement"].create({"name": "Parent document"})
        admission = self.env["op.admission"].search([("student_id", "=", self.first.id)])
        doc = self.env["campus.admission.document"].create({"admission_id": admission.id, "requirement_id": requirement.id,
            "file": base64.b64encode(b"Verified synthetic evidence"), "filename": "evidence.txt"})
        with self.assertRaises(AccessError):
            self.portal.with_context(parent_child=self.first.id)._download("document", doc.id)
        doc.action_verify()
        self.assertFalse(self.portal.snapshot(self.first.id)["documents"])
        doc.action_parent_share()
        self.assertEqual(self.portal.with_context(parent_child=self.first.id)._download("document", doc.id)[0], b"Verified synthetic evidence")
        doc.action_parent_share()
        with self.assertRaises(AccessError):
            self.portal.with_context(parent_child=self.first.id)._download("document", doc.id)

    def test_homework_uses_existing_allocation_and_submission(self):
        kind = self.env["grading.assignment.type"].create({"name": "QA coursework"})
        task = self.env["op.assignment"].create({"name": "Assigned exercise", "course_id": self.course.id, "batch_id": self.section.id,
            "subject_id": self.subject.id, "faculty_id": self.faculty.id, "assignment_type": kind.id, "description": "Solve the exercise",
            "issued_date": self.today, "submission_date": self.today + timedelta(days=2), "allocation_ids": [(6, 0, self.first.ids)]})
        self.assertFalse(self.portal.snapshot(self.first.id)["homework"])
        task.act_publish()
        self.assertEqual(self.portal.snapshot(self.first.id)["pending_work"], 1)
        self.assertFalse(self.portal.snapshot(self.second.id)["homework"])
        self.env["op.assignment.sub.line"].create({"assignment_id": task.id, "student_id": self.first.id, "state": "submit"})
        self.assertEqual(self.portal.snapshot(self.first.id)["pending_work"], 0)
        self.assertEqual(self.portal.snapshot(self.first.id)["homework"][0]["status"], "Submitted")

    def test_transport_requires_enabled_current_approved_allocation(self):
        manager = new_test_user(self.env, login="parent_transport_manager", groups="ideastone_erp.group_manager")
        route = self.env["campus.transport.route"].create({"name": "QA parent route", "year_id": self.year.id, "vehicle_registration": "QA-ONLY", "driver_phone": "9000000000"})
        stop = self.env["campus.transport.stop"].create({"name": "QA boarding point", "route_id": route.id, "pickup_time": 7.5})
        allocation = self.env["campus.transport.allocation"].create({"name": "QA parent allocation", "student_id": self.first.id, "stop_id": stop.id})
        self.assertFalse(self.portal.snapshot(self.first.id)["transport"])
        self.env.company.campus_parent_transport = True
        self.assertFalse(self.portal.snapshot(self.first.id)["transport"])
        allocation.action_submit()
        allocation.with_user(manager).action_approve()
        result = self.portal.snapshot(self.first.id)
        self.assertEqual(result["transport"][0]["pickup"], "07:30")
        self.assertIn("transport", [row[0] for row in result["navigation"]])
        self.assertFalse(self.portal.snapshot(self.second.id)["transport"])
        stop.active = False
        self.assertFalse(self.portal.snapshot(self.first.id)["transport"])
        stop.active = True
        allocation.with_user(manager).action_cancel()
        self.assertFalse(self.portal.snapshot(self.first.id)["transport"])
