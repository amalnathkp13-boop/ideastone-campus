from datetime import datetime, time

from freezegun import freeze_time
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestOwnerAttendanceUI(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.owner.tz = "UTC"
        self.ui = self.env["campus.owner.attendance.ui"].with_user(self.owner)
        self.month = self.today.strftime("%Y-%m")

    def test_navigation_permissions_and_filter_validation(self):
        data = self.env["campus.dashboard"].with_user(self.owner).get_overview()
        attendance = next(row for row in data["faculty_modules"] if row["key"] == "attendance")
        self.assertEqual(attendance["items"][0]["action"], "ideastone_erp.action_owner_attendance_overview")
        for user in (self.teacher, self.outsider, self.admissions):
            with self.assertRaises(AccessError):
                self.env["campus.owner.attendance.ui"].with_user(user).get_dashboard()
        for mode, month in [("bad", self.month), ("student", "nonsense"), ("staff", "2101-01")]:
            with self.assertRaises(ValidationError):
                self.ui.get_dashboard(mode, month)
        with self.assertRaises(AccessError):
            self.ui.get_dashboard("student", self.month, "a:2147483647")

    def student_issue(self):
        self.enrolled()
        session = self.session(hour=10)
        sheet = self.sheet(session)
        sheet.action_campus_roster()
        sheet.attendance_line.campus_status = "absent"
        sheet.attendance_done()
        self.session(hour=12)
        return self.ui.get_dashboard("student", self.month, f"a:{self.department.id}"), sheet

    def test_submitted_student_data_and_pending_sessions_stay_separate(self):
        with freeze_time(datetime.combine(self.today, time(20))):
            data, sheet = self.student_issue()
            self.assertEqual((data["totals"]["students"], data["totals"]["held"], data["totals"]["pending"]), (1, 1, 1))
            self.assertEqual((data["totals"]["rate"], data["totals"]["below"]), (0, 1))
            person = data["departments"][0]["classes"][0]["students"][0]
            self.assertEqual(person["subjects"][0]["sessions"], 1)
            self.assertEqual(sheet.state, "done")
            self.assertFalse(sheet.attendance_line.present)

    def test_review_assignment_is_durable_idempotent_and_does_not_edit_attendance(self):
        hod = new_test_user(self.env, login="attendance_review_hod", groups="ideastone_erp.group_od_hod_approver")
        hod.dept_id = self.department
        with freeze_time(datetime.combine(self.today, time(20))):
            data, sheet = self.student_issue()
            issue = next(row for row in data["issues"] if row["id"].endswith(":pending"))
            args = ["student", self.month, issue["id"], hod.id, str(self.today), "Verify the unsubmitted session"]
            first = self.ui.assign_review(*args)
            self.assertEqual(self.ui.assign_review(*args), first)
            self.ui.escalate_review(first)
            self.ui.escalate_review(first)
            review = self.env["campus.service.request"].browse(first)
            self.assertEqual((review.attendance_review_assignee_id, review.state), (hod, "submitted"))
            shown = self.ui.get_dashboard("student", self.month, f"a:{self.department.id}")
            self.assertEqual(shown["reviews"][0]["status"], "Escalated")
            self.assertEqual(len(shown["audit"]), 2)
            self.assertEqual(sheet.state, "done")
            self.assertFalse(sheet.attendance_line.present)
            self.assertTrue(review.with_user(hod).read(["name"]))
            with self.assertRaises(AccessError):
                review.with_user(self.outsider).check_access_rights("read")
            unrelated = self.env["campus.service.request"].create({"name": "Other assigned review", "description": "Another reviewer",
                "attendance_review_mode": "student", "attendance_review_assignee_id": self.owner.id})
            self.assertFalse(self.env["campus.service.request"].with_user(hod).search([("id", "=", unrelated.id)]))
            with self.assertRaises(AccessError):
                self.env["campus.owner.attendance.ui"].with_user(hod).escalate_review(first)
            with self.assertRaises(AccessError):
                review.with_user(hod).write({"attendance_review_escalated": False})
            bad = args.copy()
            bad[3] = self.outsider.id
            with self.assertRaises(AccessError):
                self.ui.assign_review(*bad)
            foreign = self.env["res.company"].create({"name": "Other review college"})
            other = self.env["campus.service.request"].create({"name": "Foreign review", "description": "Foreign scope",
                "company_id": foreign.id, "attendance_review_mode": "student"})
            with self.assertRaises(AccessError):
                self.ui.escalate_review(other.id)

    def test_open_workday_is_not_finalized_as_absence_or_missing_punch(self):
        department = self.env["hr.department"].create({"name": "Attendance QA department", "company_id": self.env.company.id})
        calendar = self.env["resource.calendar"].create({"name": "Attendance QA calendar", "tz": "Asia/Kolkata",
            "attendance_ids": [(0, 0, {"name": "Daily work", "dayofweek": str(day), "hour_from": 9, "hour_to": 17}) for day in range(7)]})
        employees = self.env["hr.employee"].create([{"name": name, "department_id": department.id,
            "company_id": self.env.company.id, "resource_calendar_id": calendar.id} for name in ("QA checked in", "QA awaiting check-in")])
        self.env["hr.attendance"].create({"employee_id": employees[0].id, "check_in": datetime.combine(self.today, time(3))})
        with freeze_time(datetime.combine(self.today, time(5))):
            data = self.ui.get_dashboard("staff", self.month, f"h:{department.id}")
            self.assertEqual((data["totals"]["present"], data["totals"]["absent"], data["totals"]["missing"]), (1, 0, 0))
        with freeze_time(datetime.combine(self.today, time(18))):
            data = self.ui.get_dashboard("staff", self.month, f"h:{department.id}")
            self.assertEqual((data["totals"]["present"], data["totals"]["absent"], data["totals"]["missing"]), (1, 1, 1))
        with freeze_time(datetime.combine(self.today, time(20))):
            data = self.ui.get_dashboard("staff", self.month, f"h:{department.id}")
            self.assertEqual((data["totals"]["absent"], data["totals"]["missing"]), (1, 1))
