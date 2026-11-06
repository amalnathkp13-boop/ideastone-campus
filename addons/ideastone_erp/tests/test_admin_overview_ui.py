from datetime import datetime, time, timedelta

from freezegun import freeze_time
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAdminOverviewUI(OwnerMVPFixture, TransactionCase):
    def test_staff_kpis_count_people_once_and_reuse_local_first_punch_policy(self):
        user = new_test_user(self.env, login="overview_hr_owner", groups="ideastone_erp.group_mvp_owner,ideastone_erp.group_manager")
        user.tz = "Asia/Kolkata"
        dashboard = self.env["campus.dashboard"].with_user(user)
        calendar = self.env["resource.calendar"].create({"name": "Overview daily calendar", "tz": "Asia/Kolkata",
            "attendance_ids": [(0, 0, {"name": "Daily work", "dayofweek": str(day), "hour_from": 8, "hour_to": 17}) for day in range(7)]})
        staff = self.env["hr.employee"].create([{"name": name, "company_id": self.env.company.id,
            "resource_calendar_id": calendar.id} for name in ("Overview early", "Overview delayed", "Overview midnight")])
        with freeze_time(datetime.combine(self.today, time(12))):
            before_present, before_delayed, _ = dashboard._admin_staff_punches()
            for employee, start, end in [(staff[0], datetime.combine(self.today, time(3)), datetime.combine(self.today, time(3, 30))),
                                         (staff[0], datetime.combine(self.today, time(10)), datetime.combine(self.today, time(11))),
                                         (staff[1], datetime.combine(self.today, time(4)), False),
                                         (staff[2], datetime.combine(self.today - timedelta(days=1), time(20)), datetime.combine(self.today, time(1)))]:
                self.env["hr.attendance"].create({"employee_id": employee.id, "check_in": start, "check_out": end})
            foreign_company = self.env["res.company"].create({"name": "Overview foreign staff college"})
            user.company_ids += foreign_company
            foreign = self.env["hr.employee"].create({"name": "Foreign staff punch", "company_id": foreign_company.id,
                "resource_calendar_id": calendar.copy({"company_id": foreign_company.id}).id})
            self.env["hr.attendance"].create({"employee_id": foreign.id, "check_in": datetime.combine(self.today, time(4))})
            kpis = dashboard.get_owner_metrics()["overview_ui"]["kpis"]
            self.assertEqual([row["kind"] for row in kpis], ["active_students", "admissions", "attendance_today", "collection",
                "dues", "faculty", "fleet_delayed", "complaints"])
            present, delayed, allowed = dashboard._admin_staff_punches()
            self.assertTrue(allowed)
            self.assertEqual(len(present.employee_id), len(before_present.employee_id) + 3)
            self.assertEqual(len(delayed.employee_id), len(before_delayed.employee_id) + 1)
            action = dashboard.get_owner_overview_action("staff_delayed")
            shown = self.env["hr.attendance"].with_user(user).search(action["domain"])
            self.assertIn(staff[1], shown.employee_id)
            self.assertNotIn(staff[0], shown.employee_id)
            self.assertNotIn(foreign, shown.employee_id)
            self.assertEqual(len(shown.employee_id), len(delayed.employee_id))
        limited = self.env["campus.dashboard"].with_user(self.admissions)
        self.assertEqual(len(limited.get_owner_metrics()["overview_ui"]["kpis"]), 8)
        with self.assertRaises(AccessError):
            limited.get_owner_overview_action("staff_present")

    def test_fleet_counts_distinct_operating_buses_with_current_insurance(self):
        user = new_test_user(self.env, login="overview_fleet_owner", groups="ideastone_erp.group_mvp_owner,ideastone_erp.group_manager")
        dashboard = self.env["campus.dashboard"].with_user(user)
        filters = {"year_id": self.year.id}
        def count():
            return next(row["value"] for row in dashboard.get_owner_metrics(filters)["overview_ui"]["kpis"] if row["kind"] == "fleet_delayed")
        baseline = count()
        routes = self.env["campus.transport.route"]
        for name, registration in [("Overview bus A", "QA 99 BUS 01"), ("Overview A second route", "qa-99-bus-01"),
                                    ("Overview bus B", "QA 99 BUS 02")]:
            routes.create({"name": name, "year_id": self.year.id, "vehicle_registration": registration,
                "fleet_status": "delayed", "fleet_insured_until": self.today + timedelta(days=30)})
        routes.create({"name": "Unverified insurance", "year_id": self.year.id, "vehicle_registration": "QA99BUS05"})
        routes.create({"name": "Expired insurance", "year_id": self.year.id, "vehicle_registration": "QA99BUS06",
                       "fleet_insured_until": self.today - timedelta(days=1)})
        routes.create({"name": "Bus under repair", "year_id": self.year.id, "vehicle_registration": "QA99BUS07",
                       "fleet_insured_until": self.today + timedelta(days=30), "fleet_status": "maintenance"})
        routes.create({"name": "Archived bus", "year_id": self.year.id, "vehicle_registration": "QA99BUS03", "active": False})
        old_year = self.year.copy({"name": "Old fleet year", "code": "FLEET-OLD",
            "start_date": self.year.start_date - timedelta(days=730), "end_date": self.year.start_date - timedelta(days=365)})
        historic = routes.create({"name": "Old bus", "year_id": old_year.id, "vehicle_registration": "QA99BUS04"})
        self.assertEqual(count(), baseline + 2)
        action = dashboard.get_owner_overview_action("fleet_delayed", filters)
        self.assertNotIn(historic, routes.with_user(user).search(action["domain"]))
        limited = self.env["campus.dashboard"].with_user(self.admissions)
        self.assertFalse(next(row["allowed"] for row in limited.get_owner_metrics()["overview_ui"]["kpis"] if row["kind"] == "fleet_delayed"))
        with self.assertRaises(AccessError):
            limited.get_owner_overview_action("fleet_delayed")

    def test_decisions_use_submitted_budget_requests_and_active_college(self):
        user = new_test_user(self.env, login="overview_budget_owner", groups="ideastone_erp.group_mvp_owner,ideastone_erp.group_manager")
        source = self.env["campus.service.request"]
        request = source.create({"name": "Cultural budget approval", "kind": "work", "amount": 1200000,
            "date_to": self.today + timedelta(days=2), "description": "Increase student participation"})
        request.action_submit()
        source.create({"name": "Unsubmitted budget", "kind": "work", "amount": 700, "description": "Draft only"})
        zero = source.create({"name": "Non-budget request", "kind": "room", "description": "Room only"})
        zero.action_submit()
        other = self.env["res.company"].create({"name": "Foreign budget college"})
        user.company_ids += other
        foreign = request.copy({"name": "Foreign proposal", "company_id": other.id})
        foreign.action_submit()
        dashboard = self.env["campus.dashboard"].with_user(user)
        ui = dashboard.get_owner_metrics()["overview_ui"]
        self.assertEqual([row["id"] for row in ui["decisions"]], request.ids)
        self.assertEqual(ui["decision_count"], 1)
        self.assertEqual(ui["decision_budget"], 1200000)
        self.assertEqual(ui["decisions"][0]["days"], 2)
        self.assertEqual(ui["decisions"][0]["impact"], request.description)
        self.assertEqual(dashboard.get_owner_overview_action("decisions", event_id=request.id)["res_id"], request.id)
        with self.assertRaises(AccessError):
            dashboard.get_owner_overview_action("decisions", event_id=foreign.id)
        limited = self.env["campus.dashboard"].with_user(self.admissions)
        self.assertEqual(limited.get_owner_metrics()["overview_ui"]["decisions"], [])
        with self.assertRaises(AccessError):
            limited.get_owner_overview_action("decisions")

    def test_fee_bars_reconcile_billed_collected_and_reversed_amounts(self):
        fee = self.fee(self.enrolled().student_id)
        fee.action_campus_post()
        payment = self.payment(fee.invoice_id, 300).payment_id
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        filters = {"date_to": str(self.today), "year_id": self.year.id}
        ui = dashboard.get_owner_metrics(filters, self.year.id)["overview_ui"]
        self.assertEqual(len(ui["fee_months"]), 6)
        self.assertEqual(ui["fee_months"][-1], {"label": self.today.strftime("%Y-%m"), "target": 500, "collected": 300, "percent": 60.0})
        self.assertEqual(ui["fee_percent"], 60)
        annual = ui["annual_fees"]
        self.assertEqual((annual["billed"], annual["collected"], annual["balance"], annual["rate"]),
            (500, 300, 200, 60.0))
        self.assertEqual(annual["unpaid_students"], 1)
        self.assertTrue(all(row["target"] == 0 and row["percent"] is None for row in ui["fee_months"][:-1]))
        payment.campus_reversal_reason = "Preview correction"
        payment.action_campus_reverse()
        ui = dashboard.get_owner_metrics(filters, self.year.id)["overview_ui"]
        self.assertEqual(ui["fee_months"][-1]["collected"], 0)
        self.assertEqual(ui["fee_percent"], 0)
        self.assertEqual(ui["annual_fees"]["collected"], 0)
        self.assertEqual(ui["annual_fees"]["balance"], 500)
        limited = self.env["campus.dashboard"].with_user(self.admissions).get_owner_metrics(filters, self.year.id)["overview_ui"]
        self.assertFalse(limited["fee_allowed"])
        self.assertFalse(limited["annual_fees"]["allowed"])
        self.assertTrue(all(row["target"] == 0 for row in limited["fee_months"]))

    def test_chart_range_and_fee_year_are_independent(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        six = dashboard.get_owner_metrics({}, self.year.id, 6)["overview_ui"]
        eight = dashboard.get_owner_metrics({}, self.year.id, 8)["overview_ui"]
        self.assertEqual((len(six["activity"]), len(eight["activity"])), (6, 8))
        self.assertEqual(six["annual_fees"]["year_id"], self.year.id)
        with self.assertRaises(ValidationError):
            dashboard.get_owner_metrics({}, self.year.id, 7)
        foreign = self.env["res.company"].create({"name": "Foreign annual fee college"})
        foreign_year = self.year.copy({"name": "Foreign fee year", "code": "FEES-FOREIGN", "company_id": foreign.id})
        with self.assertRaises(AccessError):
            dashboard.get_owner_metrics({}, foreign_year.id, 8)

    def test_event_projection_and_actions_stay_in_active_college(self):
        user = new_test_user(self.env, login="overview_event_owner", groups="ideastone_erp.group_mvp_owner,event.group_event_manager")
        dashboard = self.env["campus.dashboard"].with_user(user)
        now = fields.Datetime.now()
        event = self.env["event.event"].create({"name": "Campus showcase", "company_id": self.env.company.id,
            "date_begin": now + timedelta(days=2), "date_end": now + timedelta(days=2, hours=4),
            "description": "<p>Student <b>innovation</b> showcase</p>"})
        other = self.env["res.company"].create({"name": "Overview foreign college"})
        user.company_ids += other
        foreign = event.copy({"name": "Foreign private event", "company_id": other.id})
        expired = event.copy({"name": "Expired event", "date_begin": now - timedelta(days=2), "date_end": now - timedelta(days=1)})
        ui = dashboard.get_owner_metrics()["overview_ui"]
        self.assertIn(event.id, [row["id"] for row in ui["events"]])
        self.assertNotIn(foreign.id, [row["id"] for row in ui["events"]])
        self.assertNotIn(expired.id, [row["id"] for row in ui["events"]])
        shown = next(row for row in ui["events"] if row["id"] == event.id)
        self.assertNotIn("<b>", shown["description"])
        action = dashboard.get_owner_overview_action("events", event_id=event.id)
        self.assertEqual(action["res_id"], event.id)
        calendar = dashboard.get_owner_overview_action("events")
        self.assertEqual(calendar["views"][0], (False, "calendar"))
        self.assertNotIn(foreign, self.env["event.event"].search(calendar["domain"]))
        with self.assertRaises(AccessError):
            dashboard.get_owner_overview_action("create_event")
        with self.assertRaises(AccessError):
            dashboard.get_owner_overview_action("events", event_id=foreign.id)
        for invalid in (True, -1, 2147483648, "1"):
            with self.assertRaises(ValidationError):
                dashboard.get_owner_overview_action("events", event_id=invalid)
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.outsider).get_owner_overview_action("events")

    def test_calendar_counts_only_scheduled_events_and_real_pending_requests(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        before = dashboard.get_owner_metrics()["overview_ui"]["calendar"]
        calendar = self.env["campus.calendar.event"]
        scheduled = calendar.create({"name": "Student symposium", "date_start": self.today,
            "date_end": self.today, "status": "upcoming"})
        calendar.create({"name": "Proposed workshop", "date_start": self.today + timedelta(days=2),
            "date_end": self.today + timedelta(days=2), "status": "planning"})
        calendar.create({"name": "Completed activity", "date_start": self.today - timedelta(days=2),
            "date_end": self.today - timedelta(days=1), "status": "completed"})
        after = dashboard.get_owner_metrics()["overview_ui"]["calendar"]
        self.assertEqual(after["upcoming"], before["upcoming"] + 1)
        self.assertIsNone(after["pending"])
        self.assertEqual(after["today"], before["today"] + 1)
        self.assertIn(scheduled.id, [row["id"] for row in after["rows"]])

    def test_activity_funnel_department_and_pending_registers_reconcile(self):
        self.enrolled()
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        f = {"date_from": str(self.today - timedelta(days=2)), "date_to": str(self.today), "year_id": self.year.id}
        session = self.session(start_datetime=fields.Datetime.now() - timedelta(days=1, hours=1), end_datetime=fields.Datetime.now() - timedelta(days=1))
        self.session(start_datetime=fields.Datetime.now() + timedelta(hours=1), end_datetime=fields.Datetime.now() + timedelta(hours=2))
        ui = dashboard.get_owner_metrics(f)["overview_ui"]
        pending = next(row for row in ui["watchlist"] if row["kind"] == "attendance_pending")
        self.assertEqual(pending["count"], 1)
        action = dashboard.get_owner_overview_action("attendance_pending", f)
        self.assertEqual(action["views"], [(False, "tree"), (False, "form")])
        self.assertEqual(self.env["op.session"].search(action["domain"]), session)
        sheet = self.sheet(session)
        sheet.action_campus_roster()
        sheet.attendance_line.write({"campus_status": "absent"})
        sheet.attendance_done()
        ui = dashboard.get_owner_metrics(f)["overview_ui"]
        self.assertEqual(len(ui["kpis"]), 8)
        self.assertEqual(sum(row["value"] for row in ui["funnel"]), 1)
        self.assertEqual(next(row for row in ui["funnel"] if row["label"] == "Enrolled / other")["value"], 1)
        self.assertEqual(ui["departments"], [{"label": self.department.name, "value": 0.0}])
        self.assertEqual(ui["activity"][-1]["attendance"], 0)
        self.assertEqual(next(row for row in ui["watchlist"] if row["kind"] == "attendance_pending")["count"], 0)
        self.assertTrue(any(row["source"] == "attendance" for row in ui["insights"]))
        self.assertTrue(ui["semester"])

    def test_complaint_watchlist_source_matches_count_and_permissions(self):
        student = self.enrolled().student_id
        request = self.env["campus.service.request"].create({"name": "Overdue student complaint", "description": "Follow-up requested", "kind": "student_complaint",
            "student_id": student.id, "complaint_category": "Classroom", "date_from": self.today - timedelta(days=3),
            "date_to": self.today - timedelta(days=1)})
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        ui = dashboard.get_owner_metrics()["overview_ui"]
        row = next(item for item in ui["watchlist"] if item["kind"] == "overdue_complaints")
        action = dashboard.get_owner_overview_action("overdue_complaints")
        records = self.env["campus.service.request"].with_user(self.owner).search(action["domain"])
        self.assertIn(request, records)
        self.assertEqual(row["count"], len(records))
        limited = self.env["campus.dashboard"].with_user(self.admissions).get_owner_metrics()["overview_ui"]
        self.assertFalse(limited["event_allowed"])
        self.assertEqual(limited["events"], [])
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.admissions).get_owner_overview_action("events")
