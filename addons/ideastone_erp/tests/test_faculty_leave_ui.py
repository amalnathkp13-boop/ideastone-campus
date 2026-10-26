from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestFacultyLeaveUI(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="leave_ui_faculty", groups="openeducat_core.group_op_faculty", tz="UTC")
        cls.employee = cls.env["hr.employee"].create({"name": "Leave audit faculty", "user_id": cls.user.id})
        cls.kind = cls.env["hr.leave.type"].create({
            "name": "Casual leave audit", "sequence": -999, "requires_allocation": "yes",
            "allocation_validation_type": "no", "leave_validation_type": "hr", "request_unit": "half_day",
        })
        cls.today = fields.Date.today()
        cls.service = cls.env["campus.faculty.leave.ui"].with_user(cls.user)

    def allocate(self, days, first, last):
        allocation = self.env["hr.leave.allocation"].create({
            "name": "Leave audit allocation", "employee_id": self.employee.id,
            "holiday_status_id": self.kind.id, "number_of_days": days, "date_from": first, "date_to": last,
        })
        if allocation.state == "draft":
            allocation.action_confirm()
        if allocation.state != "validate":
            allocation.action_validate()
        return allocation

    def payload(self, **changes):
        day = self.today + timedelta(days=7)
        day += timedelta(days=(7 - day.weekday()) % 7)
        # Odoo demo data declares a mandatory working day next month; leave cannot be requested on it.
        mandatory = self.env["hr.leave.mandatory.day"].sudo()
        while mandatory.search_count([("start_date", "<=", day), ("end_date", ">=", day)]):
            day += timedelta(days=7)
        return dict({"leave_type_id": self.kind.id, "date_from": str(day), "date_to": str(day),
                     "from_session": "FN", "to_session": "AN", "reason": "Synthetic leave audit"}, **changes)

    def test_balance_uses_current_allocations_and_reserves_pending_leave(self):
        self.allocate(10, self.today - timedelta(days=500), self.today - timedelta(days=100))
        self.allocate(20, self.today + timedelta(days=100), self.today + timedelta(days=200))
        self.allocate(5, self.today - timedelta(days=10), self.today + timedelta(days=30))
        self.assertEqual(self.service.get_page_data()["balance"], 5)
        result = self.service.submit_leave(self.payload())
        leave = self.env["hr.leave"].browse(result["id"])
        self.assertEqual(leave.employee_id, self.employee)
        self.assertEqual(leave.state, "confirm")
        data = self.service.get_page_data()
        self.assertEqual(data["pending_count"], 1)
        self.assertEqual(data["balance"], 4)
        self.assertEqual(data["balance"], self.kind.get_allocation_data(self.employee, self.today)[self.employee][0][1]["virtual_remaining_leaves"])
        with self.assertRaises(UserError):
            leave.with_user(self.user).action_approve()
        officer = new_test_user(self.env, login="leave_ui_officer", groups="hr_holidays.group_hr_holidays_manager")
        leave.with_user(officer).action_approve()
        self.assertEqual(leave.state, "validate")
        self.assertEqual(self.service.get_page_data()["approved_count"], 1)
        self.assertEqual(self.service.get_page_data()["balance"], 4)

    def test_half_day_and_history_are_own_employee_only(self):
        self.allocate(5, self.today - timedelta(days=10), self.today + timedelta(days=30))
        result = self.service.submit_leave(self.payload(to_session="FN"))
        leave = self.env["hr.leave"].browse(result["id"])
        self.assertEqual(leave.number_of_days, 0.5)
        other = new_test_user(self.env, login="leave_ui_other", groups="base.group_user")
        self.env["hr.employee"].create({"name": "Other employee", "user_id": other.id})
        self.assertFalse(self.service.with_user(other).get_page_data()["history"])
        with self.assertRaises(UserError):
            self.service.submit_leave(self.payload(employee_id=leave.employee_id.id))

    def test_malformed_submissions_are_user_errors(self):
        for payload in [None, [], "invalid", self.payload(leave_type_id="invalid"), self.payload(leave_type_id=[]),
                        self.payload(leave_type_id=True), self.payload(reason=12), self.payload(reason="x" * 5001),
                        self.payload(date_from="bad"), self.payload(from_session="invalid")]:
            with self.subTest(payload=payload), self.assertRaises(UserError):
                self.service.submit_leave(payload)

    def test_portal_denied_and_missing_employee_has_clear_empty_state(self):
        portal = new_test_user(self.env, login="leave_ui_portal", groups="base.group_portal")
        with self.assertRaises(AccessError):
            self.service.with_user(portal).get_page_data()
        with self.assertRaises(AccessError):
            self.service.with_user(portal).submit_leave(self.payload())
        unlinked = new_test_user(self.env, login="leave_ui_unlinked", groups="base.group_user")
        self.assertFalse(self.service.with_user(unlinked).get_page_data()["can_apply"])
        with self.assertRaisesRegex(UserError, "linked to an employee"):
            self.service.with_user(unlinked).submit_leave(self.payload())
