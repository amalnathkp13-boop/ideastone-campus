from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestCollegeCalendar(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nosubscribe=True))
        cls.owner = new_test_user(cls.env, login="calendar_owner", groups="ideastone_erp.group_mvp_owner")
        cls.viewer = new_test_user(cls.env, login="calendar_viewer", groups="ideastone_erp.group_mvp_readonly")
        cls.outsider = new_test_user(cls.env, login="calendar_outsider", groups="base.group_user")
        cls.events = cls.env["campus.calendar.event"].with_user(cls.owner)

    def event(self, **values):
        return self.events.create({"name": "Campus project expo", "date_start": "2026-10-28", **values})

    def test_saved_details_schedule_and_date_validation(self):
        event = self.event(schedule=[{"time": "10:00 AM", "title": "Project demonstrations"}], venue="Auditorium")
        self.assertEqual(event.date_start, event.date_end)
        row = next(row for row in self.events.get_workspace()["events"] if row["id"] == event.id)
        self.assertEqual(row["schedule"], [{"time": "10:00 AM", "title": "Project demonstrations"}])
        self.assertEqual(row["venue"], "Auditorium")
        event.write({"status": "completed", "venue": "Seminar Hall"})
        self.assertEqual(event.status, "completed")
        for values in ({"date_end": "2026-10-27"}, {"name": "   "},
                       {"schedule": [{"time": "10:00 AM", "title": ""}]}, {"schedule": {"time": "invalid"}}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.event(**values)

    def test_calendar_replaces_only_owner_timetable_module(self):
        dashboard = self.env["campus.dashboard"].with_user(self.owner)
        modules = dashboard.get_overview()["faculty_modules"]
        keys = [row["key"] for row in modules]
        self.assertIn("calendar", keys)
        self.assertNotIn("timetable", keys)
        self.assertLess(keys.index("staff"), keys.index("calendar"))
        self.assertLess(keys.index("calendar"), keys.index("attendance"))
        action = dashboard.get_owner_action("ideastone_erp.action_college_calendar")
        self.assertEqual(action["tag"], "ideastone_erp.college_calendar")
        self.assertEqual(action["context"]["campus_module"], "calendar")
        # Teaching allocation still uses the original session model.
        self.assertEqual(dashboard.get_owner_action("ideastone_erp.mvp_timetable")["res_model"], "op.session")

    def test_active_college_isolation_even_when_both_companies_allowed(self):
        own = self.event()
        other = self.env["res.company"].create({"name": "Other calendar college"})
        foreign = self.env["campus.calendar.event"].create({
            "name": "Private other college event", "date_start": "2026-11-03", "company_id": other.id,
        })
        self.owner.company_ids |= other
        source = self.events.with_context(allowed_company_ids=[self.env.company.id, other.id])
        ids = [row["id"] for row in source.get_workspace()["events"]]
        self.assertIn(own.id, ids)
        self.assertNotIn(foreign.id, ids)
        with self.assertRaises(AccessError):
            source.browse(foreign.id).read(["name"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            source.browse(foreign.id).write({"venue": "Forged"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            source.create({"name": "Wrong college", "date_start": "2026-11-03", "company_id": other.id})

    def test_viewer_and_outsider_permissions(self):
        event = self.event()
        viewer = self.env["campus.calendar.event"].with_user(self.viewer)
        self.assertFalse(viewer.get_workspace()["can_write"])
        self.assertFalse(viewer.get_workspace()["can_create"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            viewer.create({"name": "Denied", "date_start": "2026-10-28"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            event.with_user(self.viewer).write({"name": "Denied"})
        with self.assertRaises(AccessError):
            event.with_user(self.viewer).action_set_reminder()
        with self.assertRaises(AccessError):
            self.env["campus.calendar.event"].with_user(self.outsider).get_workspace()

    def test_personal_reminder_is_persistent_and_idempotent(self):
        event = self.event()
        event.action_set_reminder()
        event.action_set_reminder()
        activities = event.activity_ids.filtered(lambda row: row.user_id == self.owner)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.res_id, event.id)
        self.assertEqual(activities.res_model, "campus.calendar.event")
