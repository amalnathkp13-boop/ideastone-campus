from datetime import timedelta
from uuid import uuid4

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestOwnerPlacements(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.workspace = self.env["campus.owner.placements.ui"].with_user(self.owner)
        self.cohort = self.today.year + 1

    def profile(self, **changes):
        application = self.enrolled()
        values = {"student_id": application.student_id.id, "placement_enrolment_id": application.campus_enrolment_id.id,
                  "graduation_year": self.cohort, "consent": "willing", "cgpa_recorded": True, "cgpa": 7.8,
                  "readiness_recorded": True, "quantitative": 60, "verbal": 75, "technical_recorded": True, "technical": 65}
        values.update(changes)
        return self.env["campus.placement.profile"].create(values)

    def drive_values(self, **changes):
        values = {"company": "Placement QA recruiter", "role": "Graduate engineer", "date": str(self.today + timedelta(days=7)),
                  "deadline": str(self.today + timedelta(days=5)), "salary": 6.5, "cgpa": 7, "dept": str(self.department.id),
                  "mode": "On campus", "location": "College campus", "coordinator": "Placement officer", "year": self.cohort,
                  "request_key": str(uuid4())}
        values.update(changes)
        return values

    def drive(self, **changes):
        values = self.drive_values(**changes)
        before = self.env["campus.placement.drive"].search([])
        self.workspace.create_drive(values)
        return self.env["campus.placement.drive"].search([]) - before

    def publish_results(self):
        exam = self.exam().with_user(self.teacher)
        exam.action_campus_roster()
        exam.campus_result_ids.write({"marks": 78})
        exam.action_campus_submit()
        exam.with_user(self.examiner).action_campus_lock()
        exam.with_user(self.examiner).action_campus_publish()

    def offer(self, profile, drive, **changes):
        values = {"name": "Placement QA offer", "company_id": self.env.company.id, "drive_id": drive.id,
                  "student_id": profile.student_id.id, "profile_id": profile.id,
                  "portal_enrolment_id": profile.placement_enrolment_id.id, "state": "selected",
                  "offer_reference": "QA-OFFER", "offered_salary": 650000}
        values.update(changes)
        return self.env["campus.placement.candidate"].with_user(self.owner).create(values)

    def test_owner_only_and_current_college_scope(self):
        self.profile()
        for user in (self.readonly, self.accountant, self.outsider):
            service = self.workspace.with_user(user)
            with self.assertRaises(AccessError):
                service.get_data()
            with self.assertRaises(AccessError):
                service.create_drive(self.drive_values())
            with self.assertRaises(AccessError):
                service.save_plan({"kind": "resume", "year": self.cohort, "dept": "All"})
        other = self.env["res.company"].create({"name": "Placement foreign college"})
        department = self.env["op.department"].with_company(other).create({"name": "Foreign department", "code": "PLC-FOREIGN"})
        self.assertNotIn(str(department.id), {row["id"] for row in self.workspace.get_data()["departments"]})
        with self.assertRaises(AccessError):
            self.workspace.create_drive(self.drive_values(dept=str(department.id)))
        with self.assertRaises(AccessError):
            self.workspace.with_context(allowed_company_ids=[other.id]).get_data()

    def test_drive_is_shared_approved_and_profile_values_are_not_invented(self):
        profile = self.profile(cgpa_recorded=False, readiness_recorded=False, technical_recorded=False)
        self.department.write({"placement_coordinator": "Placement QA coordinator", "placement_sequence": 0})
        drive = self.drive()
        self.assertEqual(drive.state, "approved")
        self.assertEqual(drive.approved_by, self.owner)
        self.assertTrue(drive.approved_on)
        self.assertTrue(drive.portal_published)
        self.assertEqual(drive.course_ids, self.course)
        data = self.workspace.get_data()
        self.assertEqual(data["departments"][0]["id"], str(self.department.id))
        self.assertEqual(data["departments"][0]["coordinator"], "Placement QA coordinator")
        student = next(row for row in data["students"] if row["id"] == str(profile.student_id.id))
        self.assertIsNone(student["cgpa"])
        self.assertIsNone(student["aptitude"])
        self.assertIsNone(student["coding"])
        self.assertFalse(student["eligible"])
        self.publish_results()
        academic = self.env["campus.student.portal"]._placement_academic(profile.student_id, profile.placement_enrolment_id)
        self.assertFalse(drive._portal_matches(profile.placement_enrolment_id, academic))
        profile.write({"cgpa_recorded": True})
        self.assertTrue(drive._portal_matches(profile.placement_enrolment_id, academic))

    def test_drive_input_validation_and_profile_identity(self):
        profile = self.profile()
        for invalid in ({"salary": float("nan")}, {"cgpa": 11}, {"mode": "Imaginary"}, {"year": 2027.5},
                        {"deadline": str(self.today - timedelta(days=1))}, {"deadline": str(self.today + timedelta(days=8))}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.workspace.create_drive(self.drive_values(**invalid))
        another = self.enrolled()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            profile.write({"placement_enrolment_id": another.campus_enrolment_id.id})

    def test_drive_retry_does_not_publish_a_second_opportunity(self):
        values = self.drive_values()
        first = self.workspace.create_drive(values)
        second = self.workspace.create_drive(values)
        drives = self.env["campus.placement.drive"].search([("owner_request_key", "=", values["request_key"])])
        self.assertEqual(len(drives), 1)
        self.assertEqual(first["drives"], second["drives"])
        self.assertEqual(drives.state, "approved")

    def test_drive_shortlist_uses_published_results_percentage_and_section_rules(self):
        profile = self.profile()
        drive = self.drive()
        def shortlisted(record):
            row = next(row for row in self.workspace.get_data()["drives"] if row["id"] == str(record.id))
            return str(profile.student_id.id) in row["eligible_ids"]
        self.assertFalse(shortlisted(drive))
        self.publish_results()
        self.assertTrue(shortlisted(drive))
        demanding = drive.copy({"name": "Higher academic cutoff", "min_percentage": 90})
        self.assertFalse(shortlisted(demanding))
        other_section = self.env["op.batch"].create({"name": "Other placement section", "code": "PL-OTHER",
            "course_id": self.course.id, "campus_year_id": self.year.id, "campus_term_id": self.term.id,
            "start_date": self.year.start_date, "end_date": self.year.end_date})
        restricted = drive.copy({"name": "Other section only", "batch_ids": [(6, 0, other_section.ids)]})
        self.assertFalse(shortlisted(restricted))

    def test_plans_persist_once_and_only_include_selected_cohort(self):
        profile = self.profile()
        other = self.profile(graduation_year=self.cohort - 1)
        values = {"kind": "skills", "year": self.cohort, "dept": str(self.department.id)}
        data = self.workspace.save_plan(values)
        plan = self.env["campus.placement.improvement.plan"].browse(data["plans"][0]["id"])
        self.assertEqual(plan.student_ids, profile.student_id)
        self.assertNotIn(other.student_id, plan.student_ids)
        self.assertEqual(plan.graduation_year, self.cohort)
        with self.assertRaises(ValidationError):
            self.workspace.save_plan(values)
        with self.assertRaises(AccessError):
            self.workspace.save_plan({"kind": "student", "year": self.cohort, "dept": "All", "student_id": other.student_id.id})
        with self.assertRaises(AccessError):
            self.workspace.reset_preview()

    def test_multiple_offers_keep_pending_primary_and_student_outcomes_shared(self):
        profile = self.profile()
        self.publish_results()
        pending = self.offer(profile, self.drive())
        declined = self.offer(profile, self.drive(company="Declined QA recruiter"), offer_decision="declined", offered_salary=1200000)
        data = self.workspace.get_data()
        student = next(row for row in data["students"] if row["id"] == str(profile.student_id.id))
        self.assertEqual(student["company"], pending.drive_id.recruiter_id.name)
        self.assertEqual(student["salary"], 6.5)
        self.assertEqual(len([row for row in data["offers"] if row["student_id"] == str(profile.student_id.id)]), 2)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            pending.write({"joined_on": self.today})
        pending.write({"offer_decision": "accepted", "offer_accepted_on": self.today, "joined_on": self.today})
        row = self.env["campus.student.portal"]._placement_application_row(pending, self.today)
        self.assertEqual(row["status"], "Joined")
        self.assertIn("Joining confirmed", [item["title"] for item in row["timeline"]])
        # A later cohort assignment must not count previous-cohort offers as current placements.
        profile.graduation_year = self.cohort + 1
        data = self.workspace.get_data()
        student = next(row for row in data["students"] if row["id"] == str(profile.student_id.id))
        self.assertFalse(student["placed"])
        self.assertEqual({row["year"] for row in data["offers"] if row["id"] in {str(pending.id), str(declined.id)}}, {self.cohort})
