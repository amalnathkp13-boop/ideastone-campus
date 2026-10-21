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

    def test_library_projection_and_enquiry_do_not_change_circulation(self):
        author = self.env["op.author"].create({"name": "Library QA author"})
        publisher = self.env["op.publisher"].create({"name": "Library QA publisher"})
        media = self.env["op.media"].create({"name": "Library QA title <safe>", "internal_code": "LIB-STUDENT-QA",
            "author_ids": [(4, author.id)], "publisher_ids": [(4, publisher.id)]})
        units = self.env["op.media.unit"].create([{"name": "Library QA copy %s" % index, "media_id": media.id} for index in range(2)])
        card_type = self.env["op.library.card.type"].create({"name": "Library QA card", "allow_media": 3, "duration": 7, "penalty_amt_per_day": 1})
        card = self.env["op.library.card"].create({"partner_id": self.student.partner_id.id, "student_id": self.student.id,
            "type": "student", "library_card_type_id": card_type.id})
        today = self.env["op.media.movement"]._fields["issued_date"].default(self.env["op.media.movement"])
        loan = self.env["op.media.movement"].create({"media_id": media.id, "media_unit_id": units[0].id,
            "library_card_id": card.id, "type": "student", "student_id": self.student.id, "company_id": self.env.company.id,
            "issued_date": today - timedelta(days=10), "return_date": today - timedelta(days=3)})
        loan.issue_media()
        foreign_company = self.env["res.company"].create({"name": "Foreign Library QA"})
        self.env["op.media.unit"].create({"name": "Foreign copy", "media_id": media.id, "campus_company_id": foreign_company.id})
        self.env["op.media.queue"].create({"media_id": media.id, "user_id": self.other_user.id,
            "partner_id": self.other.partner_id.id, "date_to": today + timedelta(days=7)})
        data = self.portal.snapshot()
        book = next(row for row in data["library_ui"]["books"] if row["id"] == media.id)
        self.assertEqual((book["copies"], book["available"]), (2, 1))
        self.assertEqual(data["library_ui"]["overdue"], 1)
        self.assertFalse(data["library_ui"]["reservations"])
        self.assertFalse(self.env["campus.student.portal"].with_user(self.other_user).snapshot()["library_ui"]["loans"])
        payload = {"intent": "renew", "loan_id": loan.id, "book_title": media.name, "note": "Please review.", "key": uuid.uuid4().hex}
        with self.assertRaises(AccessError):
            self.env["campus.student.portal"].with_user(self.other_user).act("library_enquiry", payload)
        result = self.portal.act("library_enquiry", payload)
        self.assertEqual(self.portal.act("library_enquiry", payload), result)
        self.assertEqual(loan.state, "issue")
        self.assertEqual(loan.return_date, today - timedelta(days=3))
        enquiry = self.portal.snapshot()["library_ui"]["active_enquiry"]
        self.assertEqual(enquiry["reference"], result["reference"])
        self.portal.act("cancel", {"request_id": enquiry["id"]})
        self.assertFalse(self.portal.snapshot()["library_ui"]["active_enquiry"])
        rendered = str(self.env["ir.ui.view"]._render_template("ideastone_erp.student_library_book_card", {"book": book}))
        self.assertIn("&lt;safe&gt;", rendered)
        with self.assertRaises(ValidationError):
            self.portal.act("library_enquiry", dict(payload, intent="approve"))

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
        chart = self.env["ir.ui.view"]._render_template("ideastone_erp.student_attendance_bars", {"d": data})
        self.assertIn("width: 100", str(chart))
        self.assertIn("%", str(chart))
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
        self.assertFalse(self.portal.snapshot()["exam_ui"]["results"])
        exam.with_user(self.teacher).action_campus_submit()
        exam.with_user(self.examiner).action_campus_lock()
        exam.with_user(self.examiner).action_campus_publish()
        results = self.portal.snapshot()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["marks"], 75)
        self.assertEqual(results[0]["grade"], "P")
        self.assertEqual(results[0]["rate"], 75.0)
        self.assertEqual(results[0]["tone"], "good")
        self.assertEqual(self.portal.snapshot()["exam_ui"]["published_groups"], 1)

    def test_native_ledger_and_cross_student_receipt_denial(self):
        fee = self.fee(self.student)
        fee.action_campus_post()
        payment = self.payment(fee.invoice_id, 300).payment_id
        other_fee = self.fee(self.other)
        other_fee.action_campus_post()
        foreign = self.payment(other_fee.invoice_id, 100).payment_id
        data = self.portal.snapshot()
        self.assertEqual(data["fees"]["assessed"], 500)
        self.assertEqual(data["fees"]["paid"], 300)
        self.assertEqual(data["fees"]["due"], 200)
        self.assertEqual(len(data["fees"]["payments"]), 1)
        self.assertEqual(data["fee_ui"]["status"], "Partially paid")
        self.assertEqual(data["fee_ui"]["posted_total"], 300)
        self.assertEqual(data["fee_ui"]["invoices"][0]["progress"], 60)
        markup = self.env["ir.ui.view"]._render_template("ideastone_erp.student_fees_content", {
            "d": data, "money": lambda amount: str(amount), "student_url_for": lambda page: "/my/campus/student/" + page})
        self.assertIn("badge tone-warn", str(markup))
        self.assertIn("Download receipt", str(markup))
        with self.assertRaises(AccessError):
            self.portal._download("receipt", foreign.id)
        with self.assertRaises(AccessError):
            other_fee.invoice_id.with_user(self.student_user).read(["amount_total"])
        payment.campus_reversal_reason = "QA payment correction"
        payment.action_campus_reverse()
        corrected = self.portal.snapshot()
        self.assertEqual(corrected["fees"]["due"], 500)
        self.assertEqual(corrected["fee_ui"]["posted_total"], 0)
        self.assertEqual(corrected["fee_ui"]["posted_count"], 0)
        self.assertEqual(corrected["fee_ui"]["payments"][0]["status"], "Reversed")

    def test_notice_audience_and_durable_acknowledgement(self):
        model = self.env["campus.circular"].with_user(self.owner)
        notice = model.create({"name": "Student publication QA", "reference": "STUP-QA", "body": "<p>Published student notice</p>", "audience": "student", "campus_managed": True, "campus_portal_priority": "important"})
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
        start = datetime.combine(self.today + timedelta(days=1), time(12))
        public_event = self.env["event.event"].create({"name": "PUBLIC STUDENT EVENT", "company_id": self.student.company_id.id,
            "website_id": False, "date_begin": start, "date_end": start + timedelta(hours=2), "is_published": True})
        self.env["event.event"].create({"name": "DRAFT STUDENT EVENT", "company_id": self.student.company_id.id,
            "website_id": False, "date_begin": start, "date_end": start + timedelta(hours=2), "is_published": False})
        foreign_company = self.env["res.company"].create({"name": "Other event college"})
        self.env["event.event"].create({"name": "FOREIGN STUDENT EVENT", "company_id": foreign_company.id,
            "website_id": False, "date_begin": start, "date_end": start + timedelta(hours=2), "is_published": True})
        data = self.portal.snapshot()
        event_names = [row["name"] for row in data["notice_ui"]["events"]]
        self.assertIn(public_event.name, event_names)
        self.assertNotIn("DRAFT STUDENT EVENT", event_names)
        self.assertNotIn("FOREIGN STUDENT EVENT", event_names)
        item = self.portal.with_context(tz="UTC")._calendar_item("boundary", "Year boundary", datetime(2026, 12, 31, 12), datetime(2027, 1, 1), "Academic")
        self.assertEqual(item["end_day"], "2026-12-31")
        self.assertEqual(item["end_utc"], "20270101T000000Z")
        rendered = str(self.env["ir.ui.view"]._render_template("ideastone_erp.student_notice_card", {
            "n": next(row for row in data["notice_ui"]["notices"] if row["id"] == notice.id), "preview": True}))
        self.assertIn("badge urgent", rendered)
        self.assertNotIn(private.name, rendered)
        self.assertNotIn("FOREIGN STUDENT EVENT", rendered)

    def test_request_retry_staff_workflow_notifications_and_document_scope(self):
        payload = self.request_payload(requested_office="academic", priority="deadline")
        first = self.portal.act("request", payload)
        self.assertEqual(first, self.portal.act("request", payload))
        self.assertTrue(self.portal.act("request", self.request_payload())["existing"])
        rec = self.env["campus.service.request"].search([("portal_reference", "=", first["reference"])]).with_user(self.owner)
        self.assertEqual(rec.requester_id, self.student_user)
        self.assertEqual(rec.portal_requested_office, "academic")
        self.assertEqual(rec.portal_priority, "deadline")
        ui = self.portal.snapshot()["request_ui"]
        self.assertEqual(ui["total"], 1)
        self.assertEqual(ui["review"], 1)
        self.assertEqual(ui["rows"][0]["office"], "Academic office")
        self.assertEqual(ui["rows"][0]["priority"], "Deadline approaching")
        self.assertEqual(ui["rows"][0]["tone"], "closed")
        self.assertFalse(self.env["campus.student.portal"].with_user(self.other_user).snapshot()["request_ui"]["rows"])
        with self.assertRaises(ValidationError):
            rec.write({"portal_priority": "normal"})
        with self.assertRaises(ValidationError):
            rec.action_portal_information()
        rec.write({"portal_reply": "Please confirm the intended recipient."})
        rec.action_portal_information()
        self.assertEqual(self.portal.snapshot()["request_ui"]["rows"][0]["tone"], "review")
        self.portal.act("reply", {"request_id": rec.id, "reply": "Scholarship office"})
        rec.action_approve()
        self.assertEqual(self.portal.snapshot()["request_ui"]["completed"], 0)
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
        rec.action_done()
        self.assertEqual(self.portal.snapshot()["request_ui"]["completed"], 1)
        with self.assertRaises(ValidationError):
            rec.unlink()

    def test_upload_and_request_identity_validation(self):
        with self.assertRaises(ValidationError):
            self.portal.act("request", self.request_payload(priority="unrecognised"))
        with self.assertRaises(ValidationError):
            self.portal.act("request", self.request_payload(requested_office="other-college-office"))
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
        self.student.write({"active": False, "campus_status_reason": "QA archive checks student access revocation"})
        with self.assertRaises(AccessError):
            self.portal.snapshot()

    def test_calendar_extremes_return_validation_errors(self):
        self.student_user.tz = "Asia/Kolkata"
        for first, last in [("0001-01-01", "0001-01-02"), ("9999-12-30", "9999-12-31")]:
            with self.subTest(first=first, last=last), self.assertRaises(ValidationError):
                self.portal.snapshot(date_from=first, date_to=last)

    def test_material_publication_and_college_download_scope(self):
        model = self.env["campus.digital.resource"]
        publisher = new_test_user(self.env, login="student_material_publisher", groups="ideastone_erp.group_manager")
        own = model.create({"name": "Student published guide", "document": base64.b64encode(b"QA guide"), "filename": "guide.txt"})
        own.action_submit()
        own.with_user(publisher).action_approve()
        draft = model.create({"name": "PRIVATE draft guide", "document": base64.b64encode(b"Private"), "filename": "draft.txt"})
        company = self.env["res.company"].create({"name": "Other college student privacy QA"})
        operator = new_test_user(self.env, login="student_other_college_operator", groups="ideastone_erp.group_manager", company_id=company.id, company_ids=[(6, 0, company.ids)])
        foreign = model.create({"name": "PRIVATE other college guide", "company_id": company.id, "document": base64.b64encode(b"Private"), "filename": "other.txt"})
        foreign.action_submit()
        foreign.with_user(operator).action_approve()
        shown = [row["id"] for row in self.portal.snapshot()["materials"]]
        self.assertIn(own.id, shown)
        self.assertNotIn(draft.id, shown)
        self.assertNotIn(foreign.id, shown)
        self.assertEqual(self.portal._download("resource", own.id)[0], b"QA guide")
        for record in draft | foreign:
            with self.assertRaises(AccessError):
                self.portal._download("resource", record.id)
