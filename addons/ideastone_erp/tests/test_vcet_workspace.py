from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestVcetWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
        cls.admin = new_test_user(cls.env, login="vcet_qa_admin", groups="ideastone_erp.group_college_admin,ideastone_erp.group_role_approver")
        cls.approver = new_test_user(cls.env, login="vcet_qa_approver", groups="ideastone_erp.group_role_approver")
        cls.teacher = new_test_user(cls.env, login="vcet_qa_teacher", groups="openeducat_attendance.group_op_attendance_user,openeducat_exam.group_op_exam_user")
        cls.other_teacher = new_test_user(cls.env, login="vcet_qa_other", groups="openeducat_attendance.group_op_attendance_user")
        cls.faculty = cls.env["op.faculty"].create({"first_name": "VCET QA", "last_name": "Faculty", "gender": "male", "birth_date": "1990-01-01", "partner_id": cls.env["res.partner"].create({"name": "VCET QA Faculty", "user_id": cls.teacher.id, "company_id": cls.env.company.id}).id})
        cls.collection = cls.env["op.media.type"].create({"name": "QA permitted collection", "code": "QA-A"})
        cls.other_collection = cls.env["op.media.type"].create({"name": "QA other collection", "code": "QA-B"})
        author = cls.env["op.author"].create({"name": "QA author"})
        publisher = cls.env["op.publisher"].create({"name": "QA publisher"})
        book = cls.env["op.media"].create({"name": "QA scoped book", "media_type_id": cls.collection.id, "author_ids": [(4, author.id)], "publisher_ids": [(4, publisher.id)]})
        cls.unit = cls.env["op.media.unit"].create({"name": "QA copy", "media_id": book.id})
        cls.student = cls.env["op.student"].create({"first_name": "QA", "last_name": "Student", "gender": "o", "gr_no": "=FORMULA", "partner_id": cls.env["res.partner"].create({"name": "=QA Student", "company_id": cls.env.company.id}).id})
        kind = cls.env["op.library.card.type"].create({"name": "QA one loan", "allow_media": 1, "duration": 7, "penalty_amt_per_day": 1})
        cls.card = cls.env["op.library.card"].create({"partner_id": cls.student.partner_id.id, "student_id": cls.student.id, "type": "student", "library_card_type_id": kind.id})

    def appointment(self, **changes):
        today = self.env["campus.responsibility"]._college_today()
        vals = {"faculty_id": self.faculty.id, "media_type_ids": [(6, 0, self.collection.ids)], "date_from": today, "date_to": today + timedelta(days=10), "justification": "QA appointment authority"}
        vals.update(changes)
        return self.env["campus.responsibility"].with_user(self.admin).create(vals)

    def approve(self, rec):
        rec.action_request()
        rec.with_user(self.approver).action_approve()
        return rec

    def test_approval_is_independent_and_cannot_be_forged(self):
        with self.assertRaises(AccessError):
            self.env["campus.responsibility"].with_user(self.teacher).create({"faculty_id": self.faculty.id})
        with self.assertRaises(AccessError):
            self.appointment(state="approved")
        rec = self.appointment()
        other_faculty = self.faculty.copy({"partner_id": self.env["res.partner"].create({"name": "QA draft nominee", "user_id": self.other_teacher.id, "company_id": self.env.company.id}).id})
        rec.write({"faculty_id": other_faculty.id})
        self.assertEqual(rec.account_id, self.other_teacher)
        rec.write({"faculty_id": self.faculty.id})
        rec.action_request()
        with self.assertRaises(AccessError):
            rec.action_approve()
        rec.with_user(self.approver).action_approve()
        self.assertEqual(rec.approved_by, self.approver)
        with self.assertRaises(ValidationError):
            rec.write({"date_to": fields.Date.today()})
        with self.assertRaises(AccessError):
            rec.write({"approved_by": self.admin.id})
        with self.assertRaises(ValidationError):
            rec.unlink()
        self.assertFalse(self.teacher.has_group("account.group_account_invoice"))
        self.assertFalse(self.teacher.has_group("ideastone_erp.group_people"))

    def test_expiry_revocation_and_college_boundaries(self):
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        with self.assertRaises(AccessError):
            desk.get_desk()
        rec = self.approve(self.appointment())
        self.assertTrue(rec.effective)
        self.assertIn(self.unit.id, [u["id"] for u in desk.get_desk()["units"]])
        rec.action_revoke()
        with self.assertRaises(AccessError):
            desk.get_desk()
        yesterday = self.env["campus.responsibility"]._college_today() - timedelta(days=1)
        expired = self.approve(self.appointment(date_from=yesterday, date_to=yesterday))
        self.assertFalse(expired.effective)
        with self.assertRaises(AccessError):
            desk.get_desk()
        other = self.env["res.company"].create({"name": "QA other college"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.appointment(company_id=other.id)

    def test_circulation_persists_without_broad_permissions(self):
        self.approve(self.appointment())
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        matches = desk.get_desk("QA scoped book", 0, self.card.number)
        self.assertIn(self.unit.id, [u["id"] for u in matches["units"]])
        self.assertEqual([c["id"] for c in matches["cards"]], self.card.ids)
        desk.issue(self.unit.id, self.card.id)
        self.assertEqual(self.unit.state, "issue")
        loan = self.env["op.media.movement"].search([("media_unit_id", "=", self.unit.id)])
        self.assertEqual(loan.company_id, self.env.company)
        self.assertEqual(loan.state, "issue")
        with self.assertRaises(ValidationError):
            desk.issue(self.unit.id, self.card.id)
        with self.assertRaises(AccessError):
            desk.return_loan(99999999)
        desk.return_loan(loan.id)
        self.assertEqual(self.unit.state, "available")
        self.assertEqual(loan.state, "return_done")
        rec = self.env["campus.responsibility"].search([("faculty_id", "=", self.faculty.id)])
        rec.with_user(self.admin).action_revoke()
        with self.assertRaises(AccessError):
            desk.return_loan(loan.id)

    def test_out_of_scope_collection_and_college_rejected(self):
        self.approve(self.appointment())
        book = self.unit.media_id.copy({"name": "Other collection", "media_type_id": self.other_collection.id})
        unit = self.env["op.media.unit"].create({"name": "Other copy", "media_id": book.id})
        desk = self.env["campus.library.desk"].with_user(self.teacher)
        with self.assertRaises(AccessError):
            desk.issue(unit.id, self.card.id)
        other = self.env["res.company"].create({"name": "QA foreign library"})
        foreign = self.unit.copy({"name": "Foreign copy", "campus_company_id": other.id})
        with self.assertRaises(AccessError):
            desk.issue(foreign.id, self.card.id)
        self.assertNotIn(foreign.id, [u["id"] for u in desk.get_desk()["units"]])

    def test_attendance_export_scope_snapshot_and_csv(self):
        course = self.env["op.course"].search([], limit=1)
        batch = self.env["op.batch"].create({"name": "QA batch", "code": "VCETQA", "course_id": course.id, "end_date": fields.Date.today() + timedelta(days=30)})
        register = self.env["op.attendance.register"].create({"name": "QA register", "code": "VCET-QA", "course_id": course.id, "batch_id": batch.id})
        for faculty_id, present, state in [(self.faculty.id, True, "done"), (False, False, "done"), (self.faculty.id, False, "draft")]:
            sheet = self.env["op.attendance.sheet"].create({"register_id": register.id, "faculty_id": faculty_id, "attendance_date": fields.Date.today(), "state": state})
            self.env["op.attendance.line"].create({"attendance_id": sheet.id, "student_id": self.student.id, "present": present})
        wizard = self.env["campus.attendance.export.wizard"].with_user(self.teacher).create({"date_from": fields.Date.today(), "date_to": fields.Date.today(), "academic_year": "2026-27", "semester": "V"})
        export = wizard._snapshot().with_user(self.teacher)
        self.assertEqual(export.snapshot["sessions"], 1)
        self.assertEqual(export.snapshot["present"], 1)
        self.assertEqual(export.snapshot["shortage"], 0)
        import base64
        csv = base64.b64decode(export.csv_file).decode("utf-8-sig")
        self.assertIn("'=FORMULA", csv)
        with self.assertRaises(AccessError):
            export.with_user(self.other_teacher).read(["snapshot"])
        with self.assertRaises(AccessError):
            export.write({"name": "Forged"})
        with self.assertRaises(AccessError):
            self.env["campus.attendance.export"].with_user(self.teacher).create({"name": "Forged"})
        html, _kind = self.env["ir.actions.report"].with_user(self.teacher)._render_qweb_html("ideastone_erp.report_attendance_export", export.ids)
        self.assertIn(b"Attendance Shortage Report", html)
        self.assertIn(b"DRAFT", html)

    def test_faculty_cannot_publish_or_edit_other_attendance(self):
        # Permission checks must not depend on optional vendor demo records.
        today = fields.Date.today()
        course = self.env["op.course"].create({"name": "Publication QA", "code": "VCET-PUB"})
        batch = self.env["op.batch"].create({"name": "Publication QA", "code": "VCET-PUB", "course_id": course.id, "end_date": today + timedelta(days=30)})
        subject = self.env["op.subject"].create({"name": "Publication QA", "code": "VCET-PUB"})
        kind = self.env["op.exam.type"].create({"name": "Publication QA", "code": "VCET-PUB"})
        session = self.env["op.exam.session"].create({"name": "Publication QA", "exam_code": "VCET-PUB", "course_id": course.id, "batch_id": batch.id,
                                                    "exam_type": kind.id, "start_date": today, "end_date": today})
        exam = self.env["op.exam"].create({"name": "Publication QA", "exam_code": "VCET-PUB", "session_id": session.id, "subject_id": subject.id,
                                          "total_marks": 100, "min_marks": 40, "responsible_id": [(6, 0, self.faculty.ids)],
                                          "start_time": datetime.combine(today, time(14)), "end_time": datetime.combine(today, time(15))})
        with self.assertRaises(AccessError):
            exam.with_user(self.teacher).act_done()
        exam.write({"state": "done"})
        result = self.env["op.result.line"].create({"exam_id": exam.id, "student_id": self.student.id, "marks": exam.min_marks})
        with self.assertRaises(AccessError):
            result.with_user(self.teacher).write({"marks": exam.total_marks})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            result.write({"marks": exam.total_marks + 1})
        register = self.env["op.attendance.register"].create({"name": "Publication QA", "code": "VCET-PUB", "course_id": course.id, "batch_id": batch.id})
        sheet = self.env["op.attendance.sheet"].create({"register_id": register.id, "attendance_date": today})
        with self.assertRaises(AccessError):
            sheet.with_user(self.teacher).write({"state": "done"})

    def test_workspace_uses_authenticated_role(self):
        overview = self.env["campus.dashboard"].with_user(self.teacher).get_overview()
        self.assertEqual(overview["workspace_role"], "Faculty")
        self.assertFalse(overview["is_admin"])
        self.assertNotIn("access", [p["key"] for p in overview["pages"]])
        self.assertFalse(overview["library_allowed"])
        self.assertIn("teaching", [module["key"] for module in overview["faculty_modules"]])
        for module in overview["faculty_modules"]:
            for item in module["items"]:
                if item.get("action"):
                    self.assertEqual(self.env.ref(item["action"]).id, item["action_id"])
        self.assertFalse(self.env["campus.dashboard"].with_user(self.admin).get_overview()["faculty_modules"])
        with self.assertRaises(AccessError):
            self.env["campus.library.desk"].with_user(self.other_teacher).get_desk()

    def test_personal_diary_is_private_and_persistent(self):
        tasks = self.env["campus.faculty.task"].with_user(self.teacher)
        task = tasks.create({"name": "Prepare next lesson", "kind": "teaching", "notes": "Planning notes"})
        task.write({"state": "progress"})
        self.assertEqual(task.state, "progress")
        self.assertEqual(task.user_id, self.teacher)
        with self.assertRaises(AccessError):
            task.with_user(self.other_teacher).read(["notes"])
        with self.assertRaises(AccessError):
            tasks.create({"name": "Forged owner", "user_id": self.other_teacher.id})
        with self.assertRaises(AccessError):
            task.write({"user_id": self.other_teacher.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            tasks.create({"name": "Invalid dates", "date": "2026-10-17", "deadline": "2026-10-16"})

    def faculty_class_fixture(self):
        course = self.env["op.course"].search([], limit=1)
        batch = self.env["op.batch"].create({"name": "Faculty tools QA", "code": "FAC-TOOLS-QA", "course_id": course.id, "end_date": "2035-12-31"})
        subject = self.env["op.subject"].create({"name": "Faculty tools QA", "code": "FAC-TOOLS-QA"})
        self.env["op.session"].create({"course_id": course.id, "batch_id": batch.id, "faculty_id": self.faculty.id,
                                       "subject_id": subject.id, "start_datetime": "2035-01-01 10:00:00", "end_datetime": "2035-01-01 11:00:00"})
        self.env["op.student.course"].create({"student_id": self.student.id, "course_id": course.id, "batch_id": batch.id})
        return batch, subject

    def test_weighted_assessment_and_class_scope(self):
        _batch, subject = self.faculty_class_fixture()
        assessments = self.env["campus.faculty.assessment"].with_user(self.teacher)
        vals = {"name": "QA internal marks", "student_id": self.student.id, "subject_id": subject.id,
                "academic_year": "2035-36", "semester": "I", "output_maximum": 25,
                "component_ids": [(0, 0, {"name": "Test", "score": 75, "maximum": 100, "weight": 40}),
                                  (0, 0, {"name": "Practical", "score": 45, "maximum": 50, "weight": 60})]}
        record = assessments.create(vals)
        self.assertAlmostEqual(record.total, 21)
        record.write({"state": "done"})
        html, _kind = self.env["ir.actions.report"].with_user(self.teacher)._render_qweb_html("ideastone_erp.report_faculty_assessment", record.ids)
        self.assertIn(b"QA internal marks", html)
        self.assertIn(b"21.00", html)
        with self.assertRaises(AccessError):
            record.with_user(self.other_teacher).read(["total"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            assessments.with_user(self.other_teacher).create(vals)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.component_ids[0].unlink()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.write({"output_maximum": 50})
        record.write({"state": "planned"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.component_ids[0].write({"score": 101})

    def test_activity_attendance_and_document_privacy(self):
        batch, _subject = self.faculty_class_fixture()
        activity = self.env["campus.faculty.activity"].with_user(self.teacher).create({"name": "QA SDP", "kind": "sdp", "batch_id": batch.id,
                    "attendance_ids": [(0, 0, {"student_id": self.student.id, "forenoon": True})]})
        self.assertTrue(activity.attendance_ids.forenoon)
        with self.assertRaises(AccessError):
            activity.attendance_ids.with_user(self.other_teacher).read(["student_id"])
        document = self.env["campus.faculty.document"].with_user(self.teacher).create({"name": "QA question paper", "kind": "question", "document": "UUE=", "filename": "qa.txt"})
        with self.assertRaises(AccessError):
            document.with_user(self.other_teacher).read(["document"])

    def test_student_leave_review_chain_and_evidence(self):
        route = self.env["campus.student.leave.routing"].create({"name": "QA student advisor", "student_id": self.student.id,
                    "advisor_id": self.teacher.id, "hod_id": self.other_teacher.id})
        preview = self.env["campus.student.leave"].with_user(self.teacher).new({"routing_id": route.id})
        preview._onchange_routing_id()
        self.assertEqual(preview.student_id, self.student)
        self.assertEqual(preview.hod_id, self.other_teacher)
        leave = self.env["campus.student.leave"].with_user(self.teacher).create({"name": "QA student leave", "routing_id": route.id, "reason": "QA medical leave"})
        with self.assertRaises(AccessError):
            leave.write({"state": "approved"})
        leave.action_submit()
        with self.assertRaises(AccessError):
            leave.with_user(self.other_teacher).action_approve()
        leave.action_approve()
        self.assertEqual(leave.state, "hod")
        with self.assertRaises(AccessError):
            leave.action_approve()
        leave.with_user(self.other_teacher).action_approve()
        self.assertEqual(leave.state, "approved")
        self.assertIn("hod -> approved", leave.decision_log)
        original_student = leave.student_id
        other_student = self.student.copy({"partner_id": self.env["res.partner"].create({"name": "Other routed student", "company_id": self.env.company.id}).id, "gr_no": "ROUTE-QA"})
        route.write({"student_id": other_student.id})
        self.assertEqual(leave.student_id, original_student, "Existing leave retains its student snapshot when routing changes")
        with self.assertRaises(AccessError):
            leave.write({"decision_log": "Forged"})
        with self.assertRaises(AccessError):
            route.with_user(self.teacher).write({"hod_id": self.teacher.id})

    def test_faculty_tools_views_and_report_domains(self):
        self.faculty_class_fixture()
        dashboard = self.env["campus.dashboard"].with_user(self.teacher)
        overview = dashboard.get_overview()
        for module in overview["faculty_modules"]:
            for item in module["items"]:
                if not item.get("tool"):
                    continue
                action = dashboard.get_faculty_action(item["tool"])
                if action["type"] == "ir.actions.client":
                    self.assertTrue(action["tag"])
                    continue
                model = self.env[action["res_model"]].with_user(self.teacher).with_context(action["context"])
                model.search(action["domain"], limit=1)
                model.get_views(action["views"], {"toolbar": True})
        photos = dashboard.get_faculty_action("report_photos")
        self.assertEqual(photos["views"][0][1], "kanban")
        self.assertIn(self.student.id, self.env["op.student"].with_user(self.teacher).search(photos["domain"]).ids)
        with self.assertRaises(AccessError):
            dashboard.get_faculty_action("arbitrary_model")

    def test_timetable_read_is_own_only_and_does_not_allow_mutation(self):
        batch, _subject = self.faculty_class_fixture()
        session = self.env["op.session"].search([("batch_id", "=", batch.id)], limit=1)
        self.assertEqual(session.with_user(self.teacher).read(["batch_id"])[0]["batch_id"][0], batch.id)
        with self.assertRaises(AccessError):
            session.with_user(self.other_teacher).read(["batch_id"])
        with self.assertRaises(AccessError):
            session.with_user(self.teacher).write({"state": "confirm"})

    def test_examination_reports_keep_category_and_allocation_scope(self):
        batch, subject = self.faculty_class_fixture()
        kind = self.env["op.exam.type"].create({"name": "QA faculty examination", "code": "FACQA"})
        session = self.env["op.exam.session"].create({"name": "QA faculty session", "course_id": batch.course_id.id,
            "batch_id": batch.id, "exam_code": "FACQA", "start_date": "2035-01-01", "end_date": "2035-01-31", "exam_type": kind.id})
        exam = self.env["op.exam"].create({"name": "QA university exam", "session_id": session.id, "subject_id": subject.id,
            "exam_code": "FACQA", "start_time": "2035-01-02 10:00:00", "end_time": "2035-01-02 11:00:00",
            "total_marks": 100, "min_marks": 40, "responsible_id": [(6, 0, self.faculty.ids)], "campus_exam_kind": "university"})
        own = self.env["op.result.line"].create({"exam_id": exam.id, "student_id": self.student.id, "marks": 75})
        foreign_exam = exam.copy({"exam_code": "FACQA-OTHER", "responsible_id": [(5, 0, 0)],
            "start_time": "2035-01-03 10:00:00", "end_time": "2035-01-03 11:00:00"})
        foreign = self.env["op.result.line"].create({"exam_id": foreign_exam.id, "student_id": self.student.id, "marks": 90})
        dashboard = self.env["campus.dashboard"].with_user(self.teacher)
        action = dashboard.get_faculty_action("report_university")
        results = self.env["op.result.line"].with_user(self.teacher).search(action["domain"])
        self.assertIn(own, results)
        self.assertNotIn(foreign, results)
        action = dashboard.get_faculty_action("report_autonomous")
        self.assertNotIn(own, self.env["op.result.line"].with_user(self.teacher).search(action["domain"]))
        exam.write({"campus_exam_kind": "autonomous"})
        self.assertIn(own, self.env["op.result.line"].with_user(self.teacher).search(action["domain"]))

    def test_student_complaint_identity_and_required_category(self):
        requests = self.env["campus.service.request"].with_user(self.teacher)
        vals = {"name": "QA student complaint", "kind": "student_complaint", "student_id": self.student.id,
                "description": "QA complaint evidence", "complaint_category": "Attendance concern"}
        complaint = requests.create(vals)
        complaint.action_submit()
        self.assertEqual(complaint.state, "submitted")
        with self.assertRaises(AccessError):
            complaint.write({"requester_id": self.other_teacher.id})
        with self.assertRaises(AccessError):
            requests.create(dict(vals, requester_id=self.other_teacher.id))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            requests.create(dict(vals, complaint_category=False))

    def test_previous_academic_records_scope_and_scores(self):
        self.faculty_class_fixture()
        model = self.env["campus.student.education"].with_user(self.teacher)
        vals = {"name": "QA previous education", "student_id": self.student.id, "qualification": "Higher secondary",
                "institution": "QA school", "completion_year": 2025, "score": 450, "maximum": 500}
        record = model.create(vals)
        self.assertEqual(record.percentage, 90)
        with self.assertRaises(AccessError):
            record.with_user(self.other_teacher).read(["score"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            record.write({"score": 501})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            model.with_user(self.other_teacher).create(vals)

    def test_survey_invitations_are_projected_only_for_recipient(self):
        survey = self.env["survey.survey"].create({"title": "QA staff survey", "access_mode": "token"})
        own = self.env["survey.user_input"].create({"survey_id": survey.id, "partner_id": self.teacher.partner_id.id})
        foreign = self.env["survey.user_input"].create({"survey_id": survey.id, "partner_id": self.other_teacher.partner_id.id})
        invitations = self.env["campus.dashboard"].with_user(self.teacher).get_overview()["faculty_surveys"]
        self.assertIn(own.id, [row["id"] for row in invitations])
        self.assertNotIn(foreign.id, [row["id"] for row in invitations])
        self.assertIn(own.access_token, next(row["url"] for row in invitations if row["id"] == own.id))

    def test_lesson_review_is_independent_and_preserves_delivery(self):
        batch, subject = self.faculty_class_fixture()
        term = self.env["op.academic.term"].search([], limit=1)
        reviewer = new_test_user(self.env, login="qa_lesson_reviewer", groups="ideastone_erp.group_academic")
        plan = self.env["campus.teaching.plan"].with_user(self.teacher).create({
            "name": "QA lesson review", "faculty_id": self.faculty.id, "subject_id": subject.id,
            "batch_id": batch.id, "term_id": term.id, "planned_date": fields.Date.today(),
            "unit": "I", "topic": "QA lesson", "planned_hours": 1,
        })
        plan.action_submit_review()
        with self.assertRaises(AccessError):
            plan.action_approve_review()
        with self.assertRaises(ValidationError):
            plan.write({"topic": "Silently replaced"})
        plan.with_user(reviewer).action_approve_review()
        self.assertEqual(plan.reviewed_by, reviewer)
        plan.write({"execution_date": fields.Date.today(), "actual_hours": 1, "notes": "Delivered"})
        self.assertEqual(plan.variance, 0)
        with self.assertRaises(AccessError):
            plan.write({"reviewed_by": self.teacher.id})
        with self.assertRaises(ValidationError):
            plan.unlink()
        returned = plan.copy({"name": "QA return and revise"})
        returned.action_submit_review()
        with self.assertRaises(ValidationError):
            returned.with_user(reviewer).action_return_review()
        returned.with_user(reviewer).write({"review_reason": "Add learning outcomes"})
        returned.with_user(reviewer).action_return_review()
        returned.write({"topic": "Revised with outcomes"})
        returned.action_submit_review()
        returned.with_user(reviewer).action_approve_review()
        self.assertEqual(returned.review_state, "approved")
        with self.assertRaises(AccessError):
            returned.write({"review_reason": "Erased"})

    def test_personal_payroll_is_read_only_and_own_only(self):
        payroll = new_test_user(self.env, login="qa_faculty_payroll_operator", groups="ideastone_erp.group_manager")
        employee = self.env["hr.employee"].create({"name": "QA payroll faculty", "user_id": self.teacher.id})
        agreement = self.env["campus.salary.agreement"].create({"name": "QA pay agreement", "employee_id": employee.id,
                     "date_from": "2035-01-01", "basic": 1000})
        agreement.with_user(payroll).action_submit()
        agreement.with_user(payroll).action_approve()
        slip = self.env["campus.payslip"].create({"name": "QA own payslip", "agreement_id": agreement.id,
                    "date_from": "2035-01-01", "date_to": "2035-01-31", "working_days": 20})
        slip.with_user(payroll).action_compute()
        slip.with_user(payroll).action_submit()
        slip.with_user(payroll).action_approve()
        admin_history = self.env["campus.payslip"].with_user(payroll).get_history_data(employee.id)
        self.assertEqual(admin_history["employee_id"], employee.id)
        self.assertEqual([row["id"] for row in admin_history["records"]], slip.ids)
        self.assertEqual(admin_history["currency_code"], self.env.company.currency_id.name)
        staff_admin = new_test_user(self.env, login="qa_staff_admin_history", groups="ideastone_erp.group_people")
        for user in (staff_admin, self.teacher):
            with self.assertRaises(AccessError):
                self.env["campus.payslip"].with_user(user).get_history_data(employee.id)
            with self.assertRaises(AccessError):
                self.env["campus.payslip"].with_user(user).get_punch_entries(
                    employee.id, "2035-01-01", "2035-01-31")
        self.assertEqual(slip.with_user(self.teacher).read(["name"])[0]["name"], slip.name)
        with self.assertRaises(AccessError):
            slip.with_user(self.other_teacher).read(["net"])
        with self.assertRaises(AccessError):
            slip.with_user(self.teacher).write({"payment_reference": "Forged"})
        self.env["campus.payslip"].with_user(self.teacher).get_views([(False, "form")], {"toolbar": True})
        html, _kind = self.env["ir.actions.report"].with_user(self.teacher)._render_qweb_html("ideastone_erp.report_payslip", slip.ids)
        self.assertIn(b"Salary statement", html)
