from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo.addons.ideastone_erp.tests.test_owner_mvp import OwnerMVPFixture
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestSuccessRadar(OwnerMVPFixture, TransactionCase):
    """Student Success Radar: scoring, explanations, scope and portal guidance."""

    def setUp(self):
        super().setUp()
        self.radar = self.env["campus.success.radar"]
        self.student = self.enrolled().student_id
        self.peer = self.enrolled().student_id
        # Enrolments start today by default; the radar reads a term in progress, so start them a month ago.
        (self.student | self.peer).course_detail_ids.write({"campus_date_from": self.today - timedelta(days=40)})
        # Mentors and HODs need a faculty record for the staff workspace, as in the college.
        self.student_user = new_test_user(self.env, login="radar_student", groups="base.group_portal", partner_id=self.student.partner_id.id)
        self.student.user_id = self.student_user
        self.mentor = new_test_user(self.env, login="radar_mentor", groups="openeducat_core.group_op_faculty")
        self.env["op.faculty"].create({"first_name": "Radar", "last_name": "Mentor", "gender": "female", "birth_date": "1988-01-01", "main_department_id": self.department.id,
            "partner_id": self.env["res.partner"].create({"name": "Radar Mentor", "user_id": self.mentor.id, "company_id": self.env.company.id}).id})
        self.hod = new_test_user(self.env, login="radar_hod", groups="ideastone_erp.group_od_hod_approver")
        self.hod.dept_id = self.department
        self.env["campus.student.leave.routing"].create({"name": "Radar route", "student_id": self.student.id, "advisor_id": self.mentor.id, "hod_id": self.hod.id})

    def attend(self, student, present_days, absent_days, start_offset=-30):
        """Record one completed class per day for the student: `present_days` present, then `absent_days` absent."""
        register = self.env["op.attendance.register"].create({"name": "Radar register", "code": "RADAR%s" % student.id, "course_id": self.course.id, "batch_id": self.section.id})
        for index in range(present_days + absent_days):
            day = self.today + timedelta(days=start_offset + index)
            session = self.env["op.session"].create({"course_id": self.course.id, "batch_id": self.section.id, "subject_id": self.subject.id, "faculty_id": self.faculty.id,
                "start_datetime": datetime.combine(day, time(9, 0)), "end_datetime": datetime.combine(day, time(10, 0)), "state": "confirm"})
            sheet = self.env["op.attendance.sheet"].create({"register_id": register.id, "session_id": session.id, "faculty_id": self.faculty.id, "attendance_date": day, "campus_managed": True})
            sheet.action_campus_roster()   # every enrolled student, present by default
            if index >= present_days:
                sheet.attendance_line.filtered(lambda line: line.student_id == student).write({"campus_status": "absent"})
            sheet.attendance_done()

    def future_classes(self, count):
        for index in range(1, count + 1):
            day = self.today + timedelta(days=index)
            self.env["op.session"].create({"course_id": self.course.id, "batch_id": self.section.id, "subject_id": self.subject.id, "faculty_id": self.faculty.id,
                "start_datetime": datetime.combine(day, time(9, 0)), "end_datetime": datetime.combine(day, time(10, 0)), "state": "confirm"})

    def row(self, student, user=None):
        data = self.radar.with_user(user or self.owner).get_workspace({"query": student.name})
        return next(row for row in data["rows"] if row["id"] == student.id)

    def test_on_track_student_scores_zero_with_no_concerns(self):
        self.attend(self.student, 18, 2)
        row = self.row(self.student)
        self.assertEqual((row["score"], row["band"], row["factors"]), (0, "low", []))
        self.assertEqual(row["attendance"]["rate"], 90.0)
        self.assertIn("No scored concerns", row["action"])

    def test_attendance_shortage_is_scored_explained_and_projected(self):
        self.attend(self.student, 12, 8)   # 60% term-to-date
        self.future_classes(10)
        row = self.row(self.student)
        attendance = row["attendance"]
        self.assertEqual(attendance["rate"], 60.0)
        self.assertEqual(attendance["remaining"], 10)
        # 75% of 30 classes = 22.5 -> 23 attended needed; 12 so far -> 11 more, which is beyond the 10 remaining.
        self.assertEqual(attendance["need"], 11)
        self.assertFalse(attendance["reachable"])
        self.assertEqual(row["factors"][0]["key"], "attendance")
        self.assertEqual(row["factors"][0]["points"], 40)
        self.assertIn("currently scheduled classes", row["factors"][0]["detail"])
        self.assertIn("remaining timetable", row["action"])
        self.assertEqual(row["band"], "watch")

        nudge = self.radar.sudo().student_nudge(self.student)
        self.assertIn("Currently scheduled classes alone", nudge["message"])

    def test_reachable_shortage_tells_the_student_exactly_what_to_do(self):
        self.attend(self.student, 14, 6)   # 70%
        self.future_classes(12)
        portal = self.env["campus.student.portal"].with_user(self.student_user).snapshot()["success"]
        # 75% of 32 = 24 -> needs 10 of the next 12.
        self.assertEqual(portal["attendance"]["need"], 10)
        self.assertIn("Attend 10 of your next 12 scheduled classes", portal["message"])
        self.assertEqual(portal["band"], "watch")
        self.assertIn("attend 10 of the next 12 scheduled classes", self.row(self.student)["action"])

    def test_low_attendance_without_future_timetable_is_not_called_on_track(self):
        self.attend(self.student, 0, 2, start_offset=-2)
        nudge = self.radar.sudo().student_nudge(self.student)
        self.assertEqual(nudge["attendance"]["rate"], 0)
        self.assertIn("below 75", nudge["message"])
        self.assertEqual(nudge["title"], "Attendance needs attention")
        self.assertEqual(nudge["display_band"], "watch")
        self.assertNotIn("on track", nudge["parent_message"])
        self.env.company.campus_attendance_threshold = 0
        self.assertEqual(self.radar.sudo().student_nudge(self.student)["attendance"]["threshold"], 0)

    def test_missing_effective_date_keeps_prior_month_term_attendance(self):
        self.attend(self.student, 1, 0, start_offset=-30)
        # Represent a legacy import without rewriting a protected historic placement.
        self.env.cr.execute("UPDATE op_student_course SET campus_date_from = NULL WHERE id = %s", [self.student.course_detail_ids.id])
        self.student.course_detail_ids.invalidate_recordset(["campus_date_from"])
        self.assertEqual(self.row(self.student)["attendance"]["conducted"], 1)

    def test_provisional_attendance_does_not_hide_other_high_risk_factors(self):
        row = self.radar.sudo()._assess(self.student, self.today)
        row.update(score=60, band="high", action="Review fees and results")
        with patch.object(type(self.radar), "_assess", return_value=row):
            nudge = self.radar.sudo().student_nudge(self.student)
        self.assertEqual(nudge["title"], "Needs attention now")

    def test_hod_requires_an_assigned_department_for_every_hod_group(self):
        self.hod.dept_id = False
        with self.assertRaises(AccessError):
            self.radar.with_user(self.hod).get_workspace()
        plain_hod = new_test_user(self.env, login="plain_radar_hod", groups="ideastone_erp.group_mvp_hod")
        with self.assertRaises(AccessError):
            self.radar.with_user(plain_hod).get_workspace()
        plain_hod.dept_id = self.department
        self.assertEqual(self.radar.with_user(plain_hod).get_workspace()["role"], "hod")

    def test_old_department_placement_does_not_leak_the_current_department(self):
        other_department = self.env["op.department"].create({"name": "Transferred department", "code": "RADART"})
        other_course = self.env["op.course"].create({"name": "Transferred course", "code": "RADART", "department_id": other_department.id})
        self.env["op.student.course"].create({"student_id": self.student.id, "course_id": other_course.id,
            "state": "running", "campus_date_from": self.today - timedelta(days=1)})
        rows = self.radar.with_user(self.hod).get_workspace()["rows"]
        self.assertNotIn(self.student.id, [row["id"] for row in rows])
        with self.assertRaises(AccessError):
            self.radar.with_user(self.hod).get_counseling_action(self.student.id)

    def test_filtered_radar_does_not_score_every_student_twice(self):
        original = type(self.radar)._assess
        calls = []
        def assess(recordset, student, today):
            calls.append(student.id)
            return original(recordset, student, today)
        with patch.object(type(self.radar), "_assess", assess):
            self.radar.with_user(self.owner).get_workspace({"query": self.student.name})
        self.assertEqual(sorted(calls), sorted([self.student.id, self.peer.id]))

    def test_new_counseling_resolves_old_followup_and_future_leave_is_not_counted(self):
        route = self.env["campus.student.leave.routing"].search([("student_id", "=", self.student.id)])
        leave = self.env["campus.student.leave"].with_user(self.mentor).create({"name": "Future leave", "routing_id": route.id,
            "reason": "Future event", "date": self.today + timedelta(days=5), "deadline": self.today + timedelta(days=8)})
        leave.action_submit()
        leave.with_user(self.mentor).action_approve()
        # Build an approved fixture; this test scores leave rather than its separate approval workflow.
        leave.with_user(self.hod).sudo().action_approve()
        self.env["campus.counseling"].create([
            {"name": "Old followup", "student_id": self.student.id, "mentor_id": self.faculty.id,
             "discussion": "Review", "date": self.today - timedelta(days=10), "follow_up_date": self.today - timedelta(days=5)},
            {"name": "Completed followup", "student_id": self.student.id, "mentor_id": self.faculty.id,
             "discussion": "Reviewed", "date": self.today}])
        row = self.row(self.student)
        self.assertEqual(row["engagement"]["leave_days"], 0)
        self.assertEqual(row["engagement"]["overdue_follow_up"], 0)

    def test_results_fees_and_engagement_factors(self):
        # A non-managed exam can be completed directly; managed exams go through the publication workflow.
        kind = self.env["op.exam.type"].create({"name": "Radar internal", "code": "RADAR"})
        session = self.env["op.exam.session"].create({"name": "Radar session", "exam_code": "RADAR", "course_id": self.course.id, "batch_id": self.section.id,
                                                    "exam_type": kind.id, "start_date": self.today, "end_date": self.today})
        exam = self.env["op.exam"].create({"name": "Radar exam", "exam_code": "RADAR", "session_id": session.id, "subject_id": self.subject.id, "total_marks": 100, "min_marks": 40,
                                          "responsible_id": [(6, 0, self.faculty.ids)], "start_time": datetime.combine(self.today, time(14)), "end_time": datetime.combine(self.today, time(15))})
        exam.write({"state": "done"})
        self.env["op.result.line"].create({"exam_id": exam.id, "student_id": self.student.id, "marks": 30})
        fee = self.fee(self.student)
        fee.action_campus_post()
        # Posted invoices are immutable; move the due date back the way time would.
        self.env.cr.execute("UPDATE account_move SET invoice_date_due = %s WHERE id = %s", (self.today - timedelta(days=45), fee.invoice_id.id))
        fee.invoice_id.invalidate_recordset(["invoice_date_due"])
        self.env["campus.counseling"].create({"name": "Radar counselling", "student_id": self.student.id, "mentor_id": self.faculty.id, "discussion": "Radar follow-up",
                                              "date": self.today - timedelta(days=20), "follow_up_date": self.today - timedelta(days=5)})
        row = self.row(self.student)
        factors = {factor["key"]: factor for factor in row["factors"]}
        self.assertEqual(factors["academics"]["points"], 29)   # (50-30)*1.2 = 24, plus one failed paper
        self.assertIn("1 below pass marks", factors["academics"]["detail"])
        self.assertEqual(factors["fees"]["points"], 11)        # 8 + one full month overdue
        self.assertIn("45 days", factors["fees"]["detail"])
        self.assertEqual(factors["engagement"]["points"], 5)   # overdue counselling follow-up
        self.assertEqual(row["score"], 45)
        self.assertEqual(row["band"], "watch")
        self.assertIn("remedial", row["action"])
        summary = self.radar.with_user(self.owner).get_workspace({})["summary"]
        self.assertEqual(summary["watch"], 1)
        self.assertEqual(summary["top_factors"][0], {"key": "academics", "count": 1})

    def test_scope_owner_hod_mentor_and_outsiders(self):
        other_department = self.env["op.department"].create({"name": "Radar other department", "code": "RADARX"})
        self.assertEqual({row["id"] for row in self.radar.with_user(self.owner).get_workspace({})["rows"]}, {self.student.id, self.peer.id})
        self.assertEqual(self.radar.with_user(self.owner).get_workspace({})["role"], "owner")
        # The mentor sees only the student routed to them.
        mentor_rows = self.radar.with_user(self.mentor).get_workspace({})
        self.assertEqual((mentor_rows["role"], [row["id"] for row in mentor_rows["rows"]]), ("mentor", [self.student.id]))
        # The HOD sees the whole department, and nothing once moved to another one.
        hod_rows = self.radar.with_user(self.hod).get_workspace({})
        self.assertEqual((hod_rows["role"], {row["id"] for row in hod_rows["rows"]}), ("hod", {self.student.id, self.peer.id}))
        self.hod.dept_id = other_department
        self.assertEqual(self.radar.with_user(self.hod).get_workspace({})["rows"], [])
        with self.assertRaises(AccessError):
            self.radar.with_user(self.outsider).get_workspace({})
        with self.assertRaises(AccessError):
            self.radar.with_user(self.student_user).get_workspace({})
        # Counselling opens only inside the caller's scope.
        action = self.radar.with_user(self.mentor).get_counseling_action(self.student.id)
        self.assertEqual(action["context"]["default_student_id"], self.student.id)
        with self.assertRaises(AccessError):
            self.radar.with_user(self.mentor).get_counseling_action(self.peer.id)
        # Filters and search narrow the list; the summary still covers the whole scope.
        data = self.radar.with_user(self.owner).get_workspace({"query": self.peer.name, "department_id": self.department.id})
        self.assertEqual([row["id"] for row in data["rows"]], [self.peer.id])
        self.assertEqual(data["summary"]["students"], 2)

    def test_workspaces_expose_the_radar_only_to_eligible_users(self):
        dashboard = self.env["campus.dashboard"]
        owner_modules = dashboard.with_user(self.owner).get_overview()["faculty_modules"]
        ai_module = next(module for module in owner_modules if module["key"] == "ai")
        self.assertEqual([item["label"] for item in ai_module["items"]], ["Student Success Radar", "Campus Assistant"])
        staff_modules = dashboard.with_user(self.mentor).get_overview()["faculty_modules"]
        self.assertIn("Student success", [module["label"] for module in staff_modules])
        teacher_modules = dashboard.with_user(self.teacher).get_overview()["faculty_modules"]
        self.assertNotIn("Student success", [module["label"] for module in teacher_modules])
        # Readonly reporting users can see the radar but not the assistant log.
        readonly_modules = dashboard.with_user(self.readonly).get_overview()["faculty_modules"]
        readonly_ai = next(module for module in readonly_modules if module["key"] == "ai")
        self.assertEqual([item["label"] for item in readonly_ai["items"]], ["Student Success Radar"])
