from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestFacultyTaskList(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.hod = new_test_user(self.env, login="task_list_hod", groups="ideastone_erp.group_od_hod_approver")
        self.hod.dept_id = self.department
        self.hod_faculty = self.env["op.faculty"].create({"first_name": "Task list", "last_name": "HOD",
            "birth_date": "1980-01-01", "gender": "male", "main_department_id": self.department.id,
            "partner_id": self.hod.partner_id.id, "user_id": self.hod.id, "company_id": self.env.company.id})
        self.route = self.env["campus.student.leave.routing"].create({"name": "Task list assigned mentor",
            "student_id": self.student.id, "advisor_id": self.teacher.id, "hod_id": self.hod.id})
        self.ui = self.env["campus.faculty.task.list"].with_user(self.teacher)

    def test_task_navigation_separates_hod_from_staff_mentorship(self):
        attendance_action = self.env["campus.faculty.home"].with_user(self.teacher).get_action("attendance")
        self.assertEqual(attendance_action["tag"], "ideastone_erp.my_teaching_subjects")
        self.assertEqual(attendance_action["context"]["campus_module"], "teaching")
        faculty_tabs = ["My Teaching Subjects", "Timetable", "Student Attendance", "My Mentorship Class",
                        "My Tasks & e-Diary", "Examinations & Marks", "Assignments", "Alternate Hour",
                        "Lesson Plans", "Circulars & Announcements"]
        for user in (self.teacher, self.hod):
            data = self.env["campus.dashboard"].with_user(user).get_overview()
            task = next(module for module in data["faculty_modules"] if module["key"] == "teaching")
            labels = [row["label"] for row in task["items"]]
            if user == self.hod:
                self.assertEqual(labels[0], "My Teaching Subjects")
                self.assertNotIn("My Mentorship Class", labels)
                attendance = next(module for module in data["faculty_modules"] if module["key"] == "attendance")
                self.assertIn("ideastone_erp.action_green_card_hod", [row.get("action") for row in attendance["items"]])
            else:
                self.assertEqual(labels, faculty_tabs)
                attendance = next(module for module in data["faculty_modules"] if module["key"] == "attendance")
                self.assertEqual([row["action"] for row in attendance["items"]], ["ideastone_erp.action_green_card_mentor"])
                self.assertFalse(any(item.get("action") == "ideastone_erp.action_subject_attendance_workspace" for item in data["navigation"]))
        with self.assertRaises(AccessError):
            self.env["campus.faculty.task.list"].with_user(self.hod).get_mentor_data()
        with self.assertRaises(AccessError):
            self.env["campus.faculty.task.list"].with_user(self.outsider).get_teaching_data()

    def test_daily_register_cannot_be_overwritten_or_accessed_outside_mentorship(self):
        day = str(self.today)
        data = self.ui.get_sop_daily(False, day, "FN")
        self.assertEqual([row["id"] for row in data["rows"]], self.student.ids)
        key = data["class_key"]
        with self.assertRaises(AccessError):
            self.ui.save_sop_daily(key, day, "FN", {"999999": {"status": "present"}})
        values = {str(self.student.id): {"status": "late", "remark": "Arrived after roll call"}}
        self.ui.save_sop_daily(key, day, "FN", values, submit=True)
        saved = self.ui.get_sop_daily(key, day, "FN")
        self.assertTrue(saved["locked"])
        self.assertEqual(saved["rows"][0]["status"], "late")
        with self.assertRaises(ValidationError):
            self.ui.save_sop_daily(key, day, "FN", values)
        with self.assertRaises(ValidationError):
            self.ui.save_sop_daily(key, day, "FULL", values, submit=True)
        with self.assertRaises(AccessError):
            self.ui.with_user(self.hod).get_sop_daily(key, day, "FN")

    def test_mentor_monitors_only_assigned_students_and_saves_real_followups(self):
        other_student = self.enrolled().student_id
        session = self.session()
        sheet = self.sheet(session)
        sheet.action_campus_roster()
        sheet.attendance_line.filtered(lambda row: row.student_id == self.student).campus_status = "absent"
        sheet.attendance_done()
        data = self.ui.get_mentor_data()
        self.assertEqual([row["id"] for row in data["students"]], self.student.ids)
        self.assertEqual((data["students"][0]["present"], data["students"][0]["held"], data["students"][0]["shortage"]), (0, 1, True))
        self.assertEqual((data["history"][0]["present"], data["history"][0]["absent"]), (0, 1))
        class_key = data["class_key"]
        self.ui.save_followup(self.student.id, "Review attendance with the student", class_key, str(self.today))
        data = self.ui.get_mentor_data()
        saved = data["followups"]
        self.assertEqual((saved[0]["student_id"], saved[0]["note"]), (self.student.id, "Review attendance with the student"))
        self.assertEqual((saved[0]["due"], saved[0]["completed"], data["open_followups"]), (str(self.today), False, 1))
        self.ui.resolve_followup(saved[0]["id"], class_key)
        resolved = self.ui.get_mentor_data()
        self.assertTrue(resolved["followups"][0]["completed"])
        self.assertEqual(resolved["open_followups"], 0)
        foreign = self.env["campus.counseling"].create({
            "name": "Outside the selected class", "student_id": other_student.id, "mentor_id": self.faculty.id,
            "discussion": "Private follow-up", "follow_up_date": self.today,
        })
        with self.assertRaises(AccessError):
            self.ui.resolve_followup(foreign.id, class_key)
        self.assertEqual(sheet.state, "done")
        with self.assertRaises(AccessError):
            self.ui.save_followup(other_student.id, "Not assigned")
        with self.assertRaises(AccessError):
            self.ui.get_mentor_data("999:999")

    def test_teaching_uses_own_allocations_and_existing_submission_lock(self):
        own = self.session()
        hod_session = self.session(hour=12, faculty_id=self.hod_faculty.id)
        data = self.ui.get_teaching_data(self.term.id, str(self.today))
        self.assertEqual(data["session_id"], own.id)
        hod_ui = self.env["campus.faculty.task.list"].with_user(self.hod)
        self.assertEqual(hod_ui.get_teaching_data(self.term.id, str(self.today))["session_id"], hod_session.id)
        with self.assertRaises(AccessError):
            self.ui.save_teaching_attendance(hod_session.id, {str(self.student.id): "present"}, "Foreign class")
        sheet = self.sheet(own)
        sheet.action_campus_roster()
        sheet.attendance_line.campus_status = "excused"
        with self.assertRaises(ValidationError):
            self.ui.save_teaching_attendance(own.id, {str(self.student.id): "absent"}, "Protected entry")
        result = self.ui.save_teaching_attendance(own.id, {str(self.student.id): "excused"}, "Topic taught", submit=True)
        self.assertEqual(result["sheet_id"], sheet.id)
        self.assertEqual((sheet.state, sheet.campus_subject_lesson_notes), ("done", "Topic taught"))
        with self.assertRaisesRegex(ValidationError, "already submitted"):
            self.ui.save_teaching_attendance(own.id, {str(self.student.id): "excused"}, "Duplicate", submit=True)
        self.assertEqual(self.env["op.attendance.sheet"].search_count([("session_id", "=", own.id)]), 1)
