from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture


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


@tagged("post_install", "-at_install")
class TestStaffTeachingCoverage(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env["hr.employee"].create({"name": self.teacher.name, "user_id": self.teacher.id})
        self.substitute_user = new_test_user(self.env, login="coverage_substitute", groups="openeducat_core.group_op_faculty")
        self.substitute_employee = self.env["hr.employee"].create({"name": "Coverage teacher", "user_id": self.substitute_user.id})
        self.substitute = self.env["op.faculty"].create({
            "first_name": "Coverage", "last_name": "Teacher", "gender": "male", "birth_date": "1990-01-01",
            "main_department_id": self.department.id, "partner_id": self.substitute_user.partner_id.id,
            "emp_id": self.substitute_employee.id,
        })
        self.kind = self.env.ref("ideastone_erp.staff_on_duty_leave_type")
        self.officer = new_test_user(self.env, login="coverage_officer", groups="hr_holidays.group_hr_holidays_manager")
        self.service = self.env["campus.faculty.leave.ui"].with_user(self.teacher)
        self.day = self.today + timedelta(days=(7 - self.today.weekday()))
        while self.env["hr.leave.mandatory.day"].sudo().search_count([("start_date", "<=", self.day), ("end_date", ">=", self.day)]):
            self.day += timedelta(days=7)
        self.morning = self.period(10)
        self.afternoon = self.period(14)

    def period(self, hour):
        return self.session(start_datetime=datetime.combine(self.day, time(hour)), end_datetime=datetime.combine(self.day, time(hour + 1)))

    def payload(self, **changes):
        return dict({"leave_type_id": self.kind.id, "date_from": str(self.day), "date_to": str(self.day),
            "from_session": "FN", "to_session": "AN", "reason": "Staff training"}, **changes)

    def test_staff_od_coverage_is_required_and_released_to_substitute_on_approval(self):
        self.assertEqual([row["id"] for row in self.service.get_coverage(self.payload(to_session="FN"))["rows"]], self.morning.ids)
        rows = self.service.get_coverage(self.payload())["rows"]
        self.assertEqual([row["id"] for row in rows], (self.morning | self.afternoon).ids)
        with self.assertRaisesRegex(ValidationError, "cannot cover your own"), self.env.cr.savepoint():
            self.service.submit_leave(self.payload(coverage=[{"session_id": row["id"], "faculty_id": self.faculty.id} for row in rows]))
        plan = [{"session_id": row["id"], "faculty_id": self.substitute.id} for row in rows]
        leave = self.env["hr.leave"].browse(self.service.submit_leave(self.payload(coverage=plan[:1]))["id"])
        with self.assertRaisesRegex(ValidationError, "every affected class"), self.env.cr.savepoint():
            leave.with_user(self.officer).action_approve()
        self.service.save_coverage(leave.id, plan)
        substitute_page = self.service.with_user(self.substitute_user)
        self.assertEqual([row["status"] for row in substitute_page.get_page_data()["assigned_coverage"]],
                         ["Awaiting acceptance", "Awaiting acceptance"])
        with self.assertRaises(AccessError):
            substitute_page.save_coverage(leave.id, plan)
        with self.assertRaises(AccessError):
            self.service.respond_to_coverage(leave.id, self.morning.id, True)
        substitute_page.respond_to_coverage(leave.id, self.morning.id, True)
        substitute_page.respond_to_coverage(leave.id, self.afternoon.id, False)
        with self.assertRaisesRegex(ValidationError, "accepted substitute"), self.env.cr.savepoint():
            leave.with_user(self.officer).action_approve()
        self.service.save_coverage(leave.id, plan[:1])
        self.service.save_coverage(leave.id, plan)
        substitute_page.respond_to_coverage(leave.id, self.afternoon.id, True)
        leave.with_user(self.officer).action_approve()
        self.assertEqual(leave.state, "validate")
        self.assertEqual([row["id"] for row in substitute_page.get_page_data()["assigned_coverage"]], [row["id"] for row in rows])
        self.assertEqual(self.morning.faculty_id, self.faculty)
        leave.with_user(self.officer).action_refuse()
        self.assertFalse(substitute_page.get_page_data()["assigned_coverage"])

    def test_native_approval_checks_plan_and_substitute_availability(self):
        leave = self.env["hr.leave"].create({"employee_id": self.employee.id, "holiday_status_id": self.kind.id,
            "request_date_from": self.day, "request_date_to": self.day, "private_name": "Native leave request"})
        with self.assertRaisesRegex(ValidationError, "every affected class"), self.env.cr.savepoint():
            leave.with_user(self.officer).action_approve()
        plan = [{"session_id": session.id, "faculty_id": self.substitute.id} for session in self.morning | self.afternoon]
        self.service.save_coverage(leave.id, plan)
        other = self.env["hr.leave"].create({"employee_id": self.substitute_employee.id, "holiday_status_id": self.kind.id,
            "request_date_from": self.day, "request_date_to": self.day, "private_name": "Substitute away"})
        other.with_user(self.officer).action_approve()
        with self.assertRaisesRegex(ValidationError, "unavailable"), self.env.cr.savepoint():
            leave.with_user(self.officer).action_approve()
        self.assertEqual(leave.state, "confirm")
