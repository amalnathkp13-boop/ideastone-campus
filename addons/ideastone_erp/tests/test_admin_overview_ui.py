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
            before = {row["kind"]: row for row in dashboard.get_owner_metrics()["overview_ui"]["kpis"]}
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
            self.assertEqual([row["kind"] for row in kpis], ["active_students", "admissions", "staff_delayed", "collection",
                "dues", "staff_present", "fleet", "services"])
            cards = {row["kind"]: row for row in kpis}
            self.assertEqual(cards["staff_present"]["value"], before["staff_present"]["value"] + 3)
            self.assertEqual(cards["staff_delayed"]["value"], before["staff_delayed"]["value"] + 1)
            action = dashboard.get_owner_overview_action("staff_delayed")
            shown = self.env["hr.attendance"].with_user(user).search(action["domain"])
            self.assertIn(staff[1], shown.employee_id)
            self.assertNotIn(staff[0], shown.employee_id)
            self.assertNotIn(foreign, shown.employee_id)
            self.assertEqual(len(shown.employee_id), cards["staff_delayed"]["value"])
        limited = self.env["campus.dashboard"].with_user(self.admissions)
        hidden = {row["kind"]: row for row in limited.get_owner_metrics()["overview_ui"]["kpis"]}
        self.assertFalse(hidden["staff_present"]["allowed"])
        self.assertEqual(hidden["staff_delayed"]["value"], "—")
        with self.assertRaises(AccessError):
            limited.get_owner_overview_action("staff_present")

    def test_fleet_counts_distinct_active_registrations_in_the_academic_year(self):
        user = new_test_user(self.env, login="overview_fleet_owner", groups="ideastone_erp.group_mvp_owner,ideastone_erp.group_manager")
        dashboard = self.env["campus.dashboard"].with_user(user)
        filters = {"year_id": self.year.id}
        def count():
            return next(row["value"] for row in dashboard.get_owner_metrics(filters)["overview_ui"]["kpis"] if row["kind"] == "fleet")
        baseline = count()
        routes = self.env["campus.transport.route"]
        for name, registration in [("Overview bus A", "QA 99 BUS 01"), ("Overview A second route", "qa-99-bus-01"),
                                    ("Overview bus B", "QA 99 BUS 02")]:
            routes.create({"name": name, "year_id": self.year.id, "vehicle_registration": registration})
        routes.create({"name": "Archived bus", "year_id": self.year.id, "vehicle_registration": "QA99BUS03", "active": False})
        old_year = self.year.copy({"name": "Old fleet year", "code": "FLEET-OLD",
            "start_date": self.year.start_date - timedelta(days=730), "end_date": self.year.start_date - timedelta(days=365)})
        historic = routes.create({"name": "Old bus", "year_id": old_year.id, "vehicle_registration": "QA99BUS04"})
        self.assertEqual(count(), baseline + 2)
        action = dashboard.get_owner_overview_action("fleet", filters)
        self.assertNotIn(historic, routes.with_user(user).search(action["domain"]))
        limited = self.env["campus.dashboard"].with_user(self.admissions)
        self.assertFalse(next(row["allowed"] for row in limited.get_owner_metrics()["overview_ui"]["kpis"] if row["kind"] == "fleet"))
        with self.assertRaises(AccessError):
            limited.get_owner_overview_action("fleet")

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
        ui = dashboard.get_owner_metrics(filters)["overview_ui"]
        self.assertEqual(len(ui["fee_months"]), 6)
        self.assertEqual(ui["fee_months"][-1], {"label": self.today.strftime("%Y-%m"), "target": 500, "collected": 300, "percent": 60.0})
        self.assertEqual(ui["fee_percent"], 60)
        self.assertTrue(all(row["target"] == 0 and row["percent"] is None for row in ui["fee_months"][:-1]))
        payment.campus_reversal_reason = "Preview correction"
        payment.action_campus_reverse()
        ui = dashboard.get_owner_metrics(filters)["overview_ui"]
        self.assertEqual(ui["fee_months"][-1]["collected"], 0)
        self.assertEqual(ui["fee_percent"], 0)
        limited = self.env["campus.dashboard"].with_user(self.admissions).get_owner_metrics(filters)["overview_ui"]
        self.assertFalse(limited["fee_allowed"])
        self.assertTrue(all(row["target"] == 0 for row in limited["fee_months"]))

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
        self.assertEqual(dashboard.get_owner_overview_action("create_event")["context"]["default_company_id"], self.env.company.id)
        with self.assertRaises(AccessError):
            dashboard.get_owner_overview_action("events", event_id=foreign.id)
        for invalid in (True, -1, 2147483648, "1"):
            with self.assertRaises(ValidationError):
                dashboard.get_owner_overview_action("events", event_id=invalid)
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.outsider).get_owner_overview_action("events")

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
        self.assertEqual(ui["activity"][0]["attendance"], 0)
        self.assertEqual(next(row for row in ui["watchlist"] if row["kind"] == "attendance_pending")["count"], 0)
        self.assertTrue(any(row["source"] == "attendance" for row in ui["insights"]))
        self.assertTrue(ui["semester"])

    def test_service_watchlist_source_matches_count_and_permissions(self):
        request = self.env["campus.service.request"].create({"name": "Overdue room review", "description": "Room availability review", "kind": "room",
            "date_from": self.today - timedelta(days=3), "date_to": self.today - timedelta(days=1)})
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        ui = dashboard.get_owner_metrics()["overview_ui"]
        row = next(item for item in ui["watchlist"] if item["kind"] == "overdue_services")
        action = dashboard.get_owner_overview_action("overdue_services")
        records = self.env["campus.service.request"].with_user(self.owner).search(action["domain"])
        self.assertIn(request, records)
        self.assertEqual(row["count"], len(records))
        limited = self.env["campus.dashboard"].with_user(self.admissions).get_owner_metrics()["overview_ui"]
        self.assertFalse(limited["event_allowed"])
        self.assertEqual(limited["events"], [])
        with self.assertRaises(AccessError):
            self.env["campus.dashboard"].with_user(self.admissions).get_owner_overview_action("events")
