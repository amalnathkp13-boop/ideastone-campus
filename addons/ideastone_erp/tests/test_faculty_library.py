import base64
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestFacultyLibrary(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True))
        cls.teacher = new_test_user(cls.env, login="library_teacher", groups="openeducat_core.group_op_faculty")
        cls.other = new_test_user(cls.env, login="library_other", groups="openeducat_core.group_op_faculty")
        cls.outsider = new_test_user(cls.env, login="library_outsider", groups="base.group_user")
        cls.manager = new_test_user(cls.env, login="library_manager", groups="ideastone_erp.group_manager")
        cls.faculty = cls.env["op.faculty"].create({"first_name": "Library", "last_name": "Teacher", "gender": "male",
            "birth_date": "1990-01-01", "partner_id": cls.env["res.partner"].create({"name": "Library Teacher", "user_id": cls.teacher.id, "company_id": cls.env.company.id}).id})
        cls.other_faculty = cls.env["op.faculty"].create({"first_name": "Other", "last_name": "Teacher", "gender": "male",
            "birth_date": "1990-01-01", "partner_id": cls.env["res.partner"].create({"name": "Other Teacher", "user_id": cls.other.id, "company_id": cls.env.company.id}).id})
        kind = cls.env["op.library.card.type"].create({"name": "Staff library policy", "allow_media": 5, "duration": 14, "penalty_amt_per_day": 1})
        cls.card = cls.env["op.library.card"].create({"type": "faculty", "faculty_id": cls.faculty.id, "partner_id": cls.faculty.partner_id.id, "library_card_type_id": kind.id})
        cls.other_card = cls.env["op.library.card"].create({"type": "faculty", "faculty_id": cls.other_faculty.id, "partner_id": cls.other_faculty.partner_id.id, "library_card_type_id": kind.id})
        cls.book = cls.env["op.media"].create({"name": "Faculty library test book", "campus_department": "ECE", "campus_publication_year": 2024,
            "campus_call_number": "621.38", "edition": "2nd", "author_ids": [(0, 0, {"name": "Library Author"})], "publisher_ids": [(0, 0, {"name": "Library Publisher"})]})
        cls.unit = cls.env["op.media.unit"].create({"name": "Library test copy", "media_id": cls.book.id,
            "campus_accession_number": "FL-QA-001", "campus_location": "Main Library", "campus_rack": "R2"})
        cls.library = cls.env["campus.faculty.library"].with_user(cls.teacher)

    def loan(self, other=False, returned=False):
        faculty, card = (self.other_faculty, self.other_card) if other else (self.faculty, self.card)
        unit = self.env["op.media.unit"].create({"name": "Loan copy", "media_id": self.book.id})
        today = fields.Date.context_today(self.library)
        loan = self.env["op.media.movement"].create({"media_id": self.book.id, "media_unit_id": unit.id,
            "type": "faculty", "faculty_id": faculty.id, "library_card_id": card.id,
            "partner_id": faculty.partner_id.id, "user_id": faculty.user_id.id,
            "issued_date": today - timedelta(days=5), "return_date": today + timedelta(days=9), "company_id": self.env.company.id})
        loan.issue_media()
        if returned:
            loan.return_media(today)
        return loan

    def test_live_catalogue_metadata_refresh_and_navigation(self):
        first = self.library.get_workspace()
        row = next(row for row in first["books"] if row["id"] == self.unit.id)
        self.assertEqual((row["code"], row["year"], row["rack"]), ("FL-QA-001", 2024, "R2"))
        self.unit.write({"campus_rack": "R4"})
        self.env["op.media.unit"].create({"name": "New copy", "media_id": self.book.id})
        refreshed = self.library.get_workspace()
        self.assertEqual(refreshed["counts"]["total"], first["counts"]["total"] + 1)
        self.assertEqual(next(row["rack"] for row in refreshed["books"] if row["id"] == self.unit.id), "R4")
        module = next(module for module in self.env["campus.dashboard"].with_user(self.teacher).get_overview()["faculty_modules"] if module["key"] == "library")
        self.assertEqual([item["label"] for item in module["items"]], ["OPAC & digital library", "Library catalogue", "Library circulation", "Learning platform"])
        self.assertFalse(refreshed["desk_allowed"])

    def test_personal_loans_and_active_college_boundaries(self):
        own, other = self.loan(), self.loan(other=True)
        foreign = self.env["res.company"].create({"name": "Foreign library college"})
        foreign_unit = self.env["op.media.unit"].create({"name": "Foreign library copy", "media_id": self.book.id, "campus_company_id": foreign.id})
        snapshot = self.library.get_workspace()
        self.assertIn(own.id, [row["id"] for row in snapshot["loans"]])
        self.assertNotIn(other.id, [row["id"] for row in snapshot["loans"]])
        self.assertNotIn(foreign_unit.id, [row["id"] for row in snapshot["books"]])
        self.assertEqual(snapshot["counts"]["own"], 1)
        self.assertEqual(snapshot["staff"]["limit"], 5)
        with self.assertRaises(AccessError):
            self.env["campus.faculty.library"].with_user(self.outsider).get_workspace()

    def test_renewal_is_saved_once_without_changing_the_due_date(self):
        loan = self.loan()
        due = loan.return_date
        self.library.request_renewal(loan.id)
        self.library.request_renewal(loan.id)
        requests = self.env["campus.service.request"].search([("campus_library_loan_id", "=", loan.id)])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.state, "submitted")
        self.assertEqual(requests.requester_id, self.teacher)
        self.assertEqual(loan.return_date, due)
        snapshot = self.library.get_workspace()
        self.assertEqual(snapshot["counts"]["pending"], 1)
        self.assertEqual(next(row["status"] for row in snapshot["loans"] if row["id"] == loan.id), "Renewal pending")
        for invalid in (True, "1", -1):
            with self.assertRaises(ValidationError):
                self.library.request_renewal(invalid)
        with self.assertRaises(AccessError):
            self.library.request_renewal(self.loan(other=True).id)
        with self.assertRaises(ValidationError):
            self.library.request_renewal(self.loan(returned=True).id)

    def test_assistance_and_forged_renewal_link(self):
        self.library.request_assistance("Please help locate accession FL-QA-001.")
        request = self.env["campus.service.request"].search([("requester_id", "=", self.teacher.id), ("kind", "=", "library")])
        self.assertEqual(request.state, "submitted")
        self.assertEqual(request.faculty_id, self.faculty)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["campus.service.request"].with_user(self.teacher).create({"name": "Forged loan request", "kind": "library",
                "faculty_id": self.faculty.id, "campus_library_loan_id": self.loan(other=True).id, "description": "Invalid link"})

    def test_only_approved_college_materials_and_no_card_state(self):
        resource = self.env["campus.digital.resource"].create({"name": "Faculty approved material", "filename": "notes.txt", "document": base64.b64encode(b"Library QA notes")})
        self.assertNotIn(resource.id, [row["id"] for row in self.library.get_workspace()["resources"]])
        resource.action_submit()
        resource.with_user(self.manager).action_approve()
        self.assertIn(resource.id, [row["id"] for row in self.library.get_workspace()["resources"]])
        self.card.active = False
        self.assertFalse(self.library.get_workspace()["staff"]["active"])
