from datetime import timedelta
from uuid import uuid4

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestHallAllocation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True))
        self.department = self.env["op.department"].create({"name": "Hall QA ECE", "code": "HALLQAECE"})
        self.other = self.env["op.department"].create({"name": "Hall QA CSE", "code": "HALLQACSE"})
        self.hod = new_test_user(self.env, login="hall_qa_hod", groups="ideastone_erp.group_mvp_hod")
        self.hod.dept_id = self.department
        self.other_hod = new_test_user(self.env, login="hall_qa_other", groups="ideastone_erp.group_mvp_hod")
        self.other_hod.dept_id = self.other
        self.staff = new_test_user(self.env, login="hall_qa_staff", groups="base.group_user")
        self.authority = new_test_user(self.env, login="hall_qa_allocator", groups="ideastone_erp.group_services")
        self.hall = self.env["campus.hall"].create({
            "name": "QA Seminar Hall", "capacity": 80, "location": "QA Block", "authority_id": self.authority.id,
        })
        self.ui = self.env["campus.hod.hall.ui"].with_user(self.hod)
        self.slot = {"date": str(fields.Date.today() + timedelta(days=3)), "start": "10:00", "end": "12:00"}
        self.payload = {"slot": self.slot, "hall_id": self.hall.id, "attendees": 40, "programme": "QA Workshop",
            "type": "Workshop", "coordinator": "QA Coordinator", "requirements": "Projector", "token": str(uuid4())}

    def test_booking_hold_idempotency_and_cancellation(self):
        row = self.ui.submit(self.payload)
        self.assertEqual(row["status"], "Pending")
        self.assertEqual(self.ui.submit(self.payload)["id"], row["id"])
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.ui.submit(dict(self.payload, token=str(uuid4())))
        with self.assertRaises(AccessError):
            self.ui.with_user(self.other_hod).cancel(row["id"])
        with self.assertRaises(AccessError):
            self.ui.with_user(self.staff).get_workspace(self.slot)
        # Adjacent times on the same day remain available.
        adjacent = self.ui.submit(dict(self.payload, slot={**self.slot, "start": "12:00", "end": "13:00"}, token=str(uuid4())))
        self.assertNotEqual(adjacent["id"], row["id"])
        self.ui.cancel(row["id"])
        self.assertTrue(self.ui.cancel(row["id"]))
        replacement = self.ui.submit(dict(self.payload, token=str(uuid4())))
        self.assertNotEqual(replacement["id"], row["id"])

    def test_authority_decision_and_confidential_department_details(self):
        data = self.ui.submit(self.payload)
        booking = self.env["campus.hall.booking"].browse(data["id"])
        with self.assertRaises(AccessError):
            booking.with_user(self.hod).write({"state": "approved"})
        with self.assertRaises(AccessError):
            booking.with_user(self.hod).action_approve()
        public = self.ui.with_user(self.other_hod).get_workspace(self.slot)
        self.assertNotIn(data["id"], [row["id"] for row in public["requests"]])
        schedule = next(row for row in public["bookings"] if row["id"] == data["id"])
        self.assertNotIn("requirements", schedule)
        self.assertNotIn("coordinator", schedule)
        booking.with_user(self.authority).action_approve()
        self.assertEqual(booking.state, "approved")
        self.assertEqual(booking.decided_by_id, self.authority)
        with self.assertRaises(ValidationError):
            self.ui.cancel(booking.id)

    def test_navigation_and_direct_creation_are_role_scoped(self):
        hod_modules = self.env["campus.dashboard"].with_user(self.hod).get_overview()["faculty_modules"]
        self.assertEqual(len([module for module in hod_modules if module["key"] == "hall-allocation"]), 1)
        staff_modules = self.env["campus.dashboard"].with_user(self.staff).get_overview()["faculty_modules"]
        self.assertNotIn("hall-allocation", [module["key"] for module in staff_modules])
        data = self.ui.submit(self.payload)
        booking = self.env["campus.hall.booking"].browse(data["id"])
        values = booking.copy_data()[0]
        values["message_follower_ids"] = []
        with self.assertRaises(AccessError):
            self.env["campus.hall.booking"].with_user(self.hod).create(values)

    def test_capacity_time_college_and_rejection_guards(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.ui.submit(dict(self.payload, attendees=81))
        with self.assertRaises(ValidationError):
            self.ui.get_workspace({**self.slot, "end": "09:00"})
        foreign_company = self.env["res.company"].create({"name": "Hall QA Other College"})
        foreign_authority = new_test_user(self.env, login="hall_foreign_allocator",
            groups="ideastone_erp.group_services", company_id=foreign_company.id, company_ids=[(6, 0, foreign_company.ids)])
        foreign_hall = self.env["campus.hall"].with_company(foreign_company).create({
            "name": "Foreign Hall", "capacity": 100, "location": "Other campus",
            "authority_id": foreign_authority.id,
        })
        with self.assertRaises(AccessError):
            self.ui.submit(dict(self.payload, hall_id=foreign_hall.id))
        data = self.ui.submit(self.payload)
        booking = self.env["campus.hall.booking"].browse(data["id"]).with_user(self.authority)
        with self.assertRaises(ValidationError):
            booking.action_reject()
        booking.decision_note = "Venue scheduled for maintenance."
        booking.action_reject()
        self.assertEqual(booking.state, "rejected")
        self.assertEqual(self.ui.get_workspace()["requests"][0]["reason"], "Venue scheduled for maintenance.")

    def test_context_cannot_override_initial_state_or_include_archived_halls(self):
        ui = self.ui.with_context(default_state="approved", default_active=False,
            default_decided_by_id=self.authority.id, default_decided_on=fields.Datetime.now(),
            default_reason="Injected approval", default_department_id=self.other.id,
            default_decision_note="Injected decision", default_requester_id=self.other_hod.id,
            default_message_follower_ids=[(0, 0, {"partner_id": self.other_hod.partner_id.id})], active_test=False)
        data = ui.submit(self.payload)
        booking = self.env["campus.hall.booking"].browse(data["id"])
        self.assertEqual(booking.state, "pending")
        self.assertTrue(booking.active)
        self.assertEqual(booking.department_id, self.department)
        self.assertEqual(booking.requester_id, self.hod)
        self.assertFalse(booking.decided_by_id or booking.decided_on or booking.reason or booking.decision_note)
        self.assertNotIn(self.other_hod.partner_id, booking.message_partner_ids)
        ui.cancel(booking.id)
        self.hall.active = False
        self.assertNotIn(self.hall.id, [hall["id"] for hall in ui.get_workspace()["halls"]])
        with self.assertRaises(AccessError):
            ui.submit(dict(self.payload, token=str(uuid4())))
