from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAdminOverviewUI(OwnerMVPFixture, TransactionCase):
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
