from datetime import datetime

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields


@tagged("post_install", "-at_install")
class TestCampusWorkflows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
        cls.manager = new_test_user(cls.env, login="qa_campus_manager", groups="ideastone_erp.group_manager")
        cls.operator = new_test_user(cls.env, login="qa_campus_operator", groups="ideastone_erp.group_services")
        cls.outsider = new_test_user(cls.env, login="qa_campus_outsider", groups="base.group_user")
        cls.faculty_user = new_test_user(cls.env, login="qa_campus_faculty", groups="openeducat_core.group_op_faculty")
        cls.student = cls.env["op.student"].create({
            "first_name": "Workflow", "last_name": "Student", "gender": "o",
            "partner_id": cls.env["res.partner"].create({"name": "Workflow Student"}).id,
        })
        cls.second_student = cls.env["op.student"].create({
            "first_name": "Second", "last_name": "Student", "gender": "o",
            "partner_id": cls.env["res.partner"].create({"name": "Second Student"}).id,
        })
        cls.faculty = cls.env["op.faculty"].create({
            "first_name": "Workflow", "last_name": "Faculty", "gender": "male", "birth_date": "1990-01-01",
            "partner_id": cls.env["res.partner"].create({"name": "Workflow Faculty", "user_id": cls.faculty_user.id}).id,
        })
        calendar = cls.env["resource.calendar"].create({
            "name": "QA eight-hour calendar", "tz": "UTC", "attendance_ids": [(5, 0, 0)] + [
                (0, 0, {"name": "QA day", "dayofweek": str(day), "hour_from": 8, "hour_to": 16, "day_period": "morning"})
                for day in range(7)
            ],
        })
        cls.employee = cls.env["hr.employee"].create({"name": "Payroll Fixture", "resource_calendar_id": calendar.id})

    def _approve(self, record):
        record = record.with_user(self.manager)
        record.action_submit()
        record.action_approve()
        return record

    def test_approval_cannot_be_forged_or_bypassed(self):
        model = self.env["campus.service.request"].with_user(self.operator)
        with self.assertRaises(AccessError):
            model.create({"name": "Forged", "description": "Test", "state": "approved"})
        rec = model.create({"name": "Approval", "description": "Test"})
        rec.action_submit()
        with self.assertRaises(AccessError):
            rec.action_approve()
        rec.with_user(self.manager).action_approve()
        self.assertEqual(rec.approved_by, self.manager)
        with self.assertRaises(ValidationError):
            rec.write({"description": "Changed after approval"})
        with self.assertRaises(ValidationError):
            rec.write({"state": "approved", "description": "Bypass"})
        with self.assertRaises(ValidationError):
            rec.unlink()

    def test_room_capacity_and_residence_dates(self):
        room = self.env["campus.hostel.room"].create({"name": "QA-1", "building": "Fixture", "capacity": 1})
        model = self.env["campus.hostel.allocation"]
        first = model.create({"name": "First residence", "student_id": self.student.id, "room_id": room.id, "date_from": "2026-01-01", "date_to": "2026-01-31"})
        self._approve(first)
        second = model.create({"name": "Overlap", "student_id": self.second_student.id, "room_id": room.id, "date_from": "2026-01-15", "date_to": "2026-02-15"})
        second.action_submit()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.with_user(self.manager).action_approve()
        second.write({"date_from": "2026-02-01"})
        self._approve_after_submit(second)
        self.assertEqual(second.state, "approved")

    def _approve_after_submit(self, record):
        return record.with_user(self.manager).action_approve()

    def test_duplicate_student_residence(self):
        rooms = self.env["campus.hostel.room"].create([
            {"name": "QA-2", "building": "Fixture", "capacity": 2},
            {"name": "QA-3", "building": "Fixture", "capacity": 2},
        ])
        first = self.env["campus.hostel.allocation"].create({"name": "Residence", "student_id": self.student.id, "room_id": rooms[0].id, "date_from": "2026-01-01"})
        self._approve(first)
        second = self.env["campus.hostel.allocation"].create({"name": "Duplicate", "student_id": self.student.id, "room_id": rooms[1].id, "date_from": "2026-02-01"})
        second.action_submit()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            second.with_user(self.manager).action_approve()

    def test_company_and_role_boundaries(self):
        room = self.env["campus.hostel.room"].create({"name": "Private room", "building": "Fixture", "capacity": 2})
        with self.assertRaises(AccessError):
            room.with_user(self.outsider).read(["name"])
        other = self.env["res.company"].create({"name": "Other QA Company"})
        secret = self.env["campus.hostel.room"].create({"name": "Other room", "building": "Fixture", "capacity": 1, "company_id": other.id})
        with self.assertRaises(AccessError):
            secret.with_user(self.operator).with_context(allowed_company_ids=[self.env.company.id]).read(["name"])

    def test_faculty_owns_only_their_details(self):
        self.faculty.with_user(self.faculty_user).write({"campus_alternate_email": "qa@example.invalid"})
        with self.assertRaises(AccessError):
            self.faculty.with_user(self.faculty_user).write({"user_id": self.outsider.id})
        own = self.env["campus.faculty.detail"].create({"name": "English", "kind": "language", "faculty_id": self.faculty.id})
        self.assertEqual(own.with_user(self.faculty_user).read(["name"])[0]["name"], "English")
        other = self.env["op.faculty"].create({"first_name": "Other", "last_name": "Faculty", "gender": "female", "birth_date": "1990-01-01", "partner_id": self.env["res.partner"].create({"name": "Other Faculty"}).id})
        secret = self.env["campus.faculty.detail"].create({"name": "Private", "faculty_id": other.id})
        with self.assertRaises(AccessError):
            secret.with_user(self.faculty_user).read(["name"])
        with self.assertRaises(AccessError):
            own.with_user(self.faculty_user).action_verify()

    def test_biometric_import_is_idempotent(self):
        model = self.env["campus.biometric.event"].with_user(self.manager)
        events = model.create([
            {"name": "Punch A", "device": "Fixture", "external_reference": "A", "employee_id": self.employee.id, "check_in": "2026-01-01 08:00:00", "check_out": "2026-01-01 16:00:00"},
            {"name": "Punch B", "device": "Fixture", "external_reference": "B", "employee_id": self.employee.id, "check_in": "2026-01-02 08:00:00", "check_out": "2026-01-02 16:00:00"},
        ])
        events.action_import()
        self.assertEqual(len(events.attendance_id), 2)
        ids = events.attendance_id.ids
        events.action_import()
        self.assertEqual(events.attendance_id.ids, ids)
        with self.assertRaises(ValidationError):
            events.write({"check_in": "2026-01-03 08:00:00"})

    def test_payroll_uses_attendance_and_configured_contributions(self):
        agreement = self.env["campus.salary.agreement"].create({
            "name": "January agreement", "employee_id": self.employee.id, "date_from": "2026-01-01", "date_to": "2026-01-31",
            "basic": 1000, "allowance": 200, "pf_base": 1000, "pf_rate": 10, "daily_hours": 8,
        })
        self._approve(agreement)
        self.env["hr.attendance"].create({"employee_id": self.employee.id, "check_in": datetime(2026, 1, 1, 8), "check_out": datetime(2026, 1, 1, 16)})
        slip = self.env["campus.payslip"].with_user(self.manager).create({"name": "January payroll", "agreement_id": agreement.id, "date_from": "2026-01-01", "date_to": "2026-01-31", "working_days": 2})
        slip.action_compute()
        self.assertAlmostEqual(slip.gross, 600)
        self.assertAlmostEqual(slip.pf, 50)
        self.assertAlmostEqual(slip.net, 550)
        with self.assertRaises(AccessError):
            slip.write({"net": 999999})
        self._approve(slip)
        slip.write({"payment_reference": "QA-ONLY"})
        slip.action_done()
        self.assertEqual(slip.state, "done")

    def test_late_punches_have_two_paid_days_then_one_day_deduction(self):
        agreement = self._approve(self.env["campus.salary.agreement"].create({
            "name": "Late punch salary", "employee_id": self.employee.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "basic": 3000, "daily_hours": 8,
        }))
        attendance = self.env["hr.attendance"]
        for day, hour, minute in [(1, 9, 1), (2, 9, 10), (3, 9, 15), (4, 9, 0), (5, 8, 0)]:
            attendance.create({"employee_id": self.employee.id,
                               "check_in": datetime(2026, 1, day, hour, minute),
                               "check_out": datetime(2026, 1, day, 17 if day == 4 else 16)})
        # A second punch on one day must not use a second monthly allowance.
        attendance.create({"employee_id": self.employee.id,
                           "check_in": datetime(2026, 1, 3, 17), "check_out": datetime(2026, 1, 3, 18)})
        slip = self.env["campus.payslip"].with_user(self.manager).create({
            "name": "January late punch payroll", "agreement_id": agreement.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "working_days": 5,
        })
        slip.action_compute()
        self.assertEqual((slip.late_days, slip.late_grace_days, slip.late_deducted_days), (3, 2, 1))
        self.assertEqual(slip.late_deduction_dates, "2026-01-03")
        self.assertEqual(slip.late_deduction, 600)
        self.assertEqual(slip.gross, 3000)
        self.assertEqual(slip.net, 2400)
        with self.assertRaises(AccessError):
            slip.write({"late_deduction": 0})

    def test_late_allowance_resets_each_month_and_uses_local_time(self):
        self.employee.resource_calendar_id.tz = "Asia/Kolkata"
        agreement = self._approve(self.env["campus.salary.agreement"].create({
            "name": "Local-time salary", "employee_id": self.employee.id,
            "date_from": "2026-01-01", "date_to": "2026-02-28", "basic": 3000, "daily_hours": 8,
        }))
        attendance = self.env["hr.attendance"]
        # 03:31 UTC is 09:01 local; 03:30 UTC is exactly 09:00 local.
        for day in (1, 2, 3):
            attendance.create({"employee_id": self.employee.id,
                               "check_in": datetime(2026, 1, day, 3, 31),
                               "check_out": datetime(2026, 1, day, 11, 31)})
        attendance.create({"employee_id": self.employee.id,
                           "check_in": datetime(2026, 2, 1, 3, 31),
                           "check_out": datetime(2026, 2, 1, 11, 31)})
        attendance.create({"employee_id": self.employee.id,
                           "check_in": datetime(2026, 2, 2, 3, 30),
                           "check_out": datetime(2026, 2, 2, 11, 30)})
        for month, expected in [(1, (3, 1, 600)), (2, (1, 0, 0))]:
            last = 31 if month == 1 else 28
            slip = self.env["campus.payslip"].with_user(self.manager).create({
                "name": f"Month {month} salary", "agreement_id": agreement.id,
                "date_from": f"2026-{month:02d}-01", "date_to": f"2026-{month:02d}-{last}",
                "working_days": 5,
            })
            slip.action_compute()
            self.assertEqual((slip.late_days, slip.late_deducted_days, slip.late_deduction), expected)

    def test_paid_late_permission_does_not_excuse_early_checkout(self):
        agreement = self._approve(self.env["campus.salary.agreement"].create({
            "name": "Short shift salary", "employee_id": self.employee.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "basic": 1000,
        }))
        self.env["hr.attendance"].create({"employee_id": self.employee.id,
                                           "check_in": datetime(2026, 1, 1, 9, 15),
                                           "check_out": datetime(2026, 1, 1, 12)})
        slip = self.env["campus.payslip"].with_user(self.manager).create({
            "name": "Short shift payslip", "agreement_id": agreement.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "working_days": 1,
        })
        slip.action_compute()
        self.assertEqual(slip.late_grace_days, 1)
        self.assertEqual(slip.late_deduction, 0)
        self.assertEqual(slip.gross, 500)

    def test_open_punch_blocks_payroll_computation(self):
        agreement = self._approve(self.env["campus.salary.agreement"].create({
            "name": "Open punch salary", "employee_id": self.employee.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "basic": 3000,
        }))
        self.env["hr.attendance"].create({"employee_id": self.employee.id,
                                           "check_in": datetime(2026, 1, 1, 9, 1)})
        slip = self.env["campus.payslip"].with_user(self.manager).create({
            "name": "Incomplete payroll", "agreement_id": agreement.id,
            "date_from": "2026-01-01", "date_to": "2026-01-31", "working_days": 5,
        })
        with self.assertRaises(ValidationError):
            slip.action_compute()

    def test_unapproved_purchase_cannot_generate_order(self):
        dept = self.env["op.department"].search([], limit=1)
        product = self.env["product.product"].create({"name": "Fixture equipment", "purchase_ok": True})
        vendor = self.env["res.partner"].create({"name": "Fixture supplier"})
        indent = self.env["campus.purchase.request"].with_user(self.manager).create({
            "name": "QA indent", "department_id": dept.id, "product_id": product.id, "vendor_id": vendor.id,
            "quantity": 2, "unit_price": 100, "required_on": fields.Date.today(), "justification": "Workflow fixture", "comparative_quote": "Fixture quotations",
        })
        with self.assertRaises(ValidationError):
            indent.action_purchase()
        indent.action_submit()
        with self.assertRaises(ValidationError):
            indent.action_approve()
        indent.action_department_review()
        indent.action_finance_review()
        indent.action_approve()
        indent.action_purchase()
        first_id = indent.purchase_id.id
        indent.action_purchase()
        self.assertEqual(indent.purchase_id.id, first_id)
        self.assertEqual(indent.purchase_id.order_line.product_qty, 2)

    def test_trip_validation_and_mileage(self):
        year = self.env["op.academic.year"].search([], limit=1)
        route = self.env["campus.transport.route"].create({"name": "Fixture route", "year_id": year.id, "vehicle_registration": "QA-ONLY", "capacity": 1})
        trip = self.env["campus.transport.trip"].create({"name": "Fixture trip", "route_id": route.id, "odometer_start": 100, "odometer_end": 200, "fuel_litres": 10})
        self.assertEqual(trip.mileage, 10)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            trip.write({"odometer_end": 50})

    def test_feedback_validation(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["campus.feedback"].create({"name": "Missing student", "kind": "parent", "period": "2026", "score": 3})

    def test_all_declared_views_and_dashboard_actions_resolve(self):
        dashboard = self.env["campus.dashboard"].with_user(self.manager).get_overview()
        self.assertGreater(len(dashboard["navigation"]), 25)
        for item in dashboard["navigation"]:
            action = self.env.ref(item["action"])
            self.assertTrue(action.exists())
            if item["allowed"] and action._name == "ir.actions.act_window":
                self.env[action.res_model].with_user(self.manager).get_views([(False, "form"), (False, "tree")])
            if not item["allowed"]:
                self.assertFalse(self.env[item["model"]].with_user(self.manager).check_access_rights("read", raise_exception=False))
        with self.assertRaises(AccessError):
            portal_user = new_test_user(self.env, login="qa_portal", groups="base.group_portal")
            self.env["campus.dashboard"].with_user(portal_user).get_overview()
