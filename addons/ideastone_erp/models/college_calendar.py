"""Owner/admin college activities, independent of teaching timetable sessions."""

from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class CollegeCalendarEvent(models.Model):
    _name = "campus.calendar.event"
    _description = "College calendar event"
    _inherit = "campus.record"
    _order = "date_start, id"

    date_start = fields.Date(required=True, default=fields.Date.context_today, index=True, tracking=True)
    date_end = fields.Date(required=True, index=True, tracking=True)
    time = fields.Char(default="All day")
    category = fields.Selection([
        ("academic", "Academic"), ("cultural", "Cultural & campus life"),
        ("exam", "Examination / deadline"), ("holiday", "Holiday / observance"),
        ("workshop", "Workshop / professional"),
    ], required=True, default="academic", tracking=True)
    status = fields.Selection([
        ("planning", "Planning"), ("upcoming", "Upcoming"), ("completed", "Completed"),
    ], required=True, default="planning", tracking=True)
    venue = fields.Char()
    organizer = fields.Char(string="Organizing department / club")
    contact = fields.Char(string="Coordinator / contact")
    audience = fields.Char(default="All campus")
    description = fields.Text()
    schedule = fields.Json(default=list, help="Ordered schedule entries with time and title.")
    is_sample = fields.Boolean(default=False, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("date_end"):
                vals["date_end"] = vals.get("date_start") or fields.Date.context_today(self)
        return super().create(vals_list)

    @api.constrains("name", "date_start", "date_end", "schedule")
    def _validate_calendar_event(self):
        for event in self:
            if not event.name.strip():
                raise ValidationError(_("Enter an event title."))
            if event.date_end < event.date_start:
                raise ValidationError(_("The end date must be on or after the start date."))
            schedule = event.schedule or []
            if not isinstance(schedule, list) or len(schedule) > 100 or any(
                not isinstance(row, dict) or set(row) != {"time", "title"}
                or any(not isinstance(row[key], str) or not row[key].strip() or len(row[key]) > 500
                       for key in ("time", "title")) for row in schedule
            ):
                raise ValidationError(_("Add up to 100 schedule entries, each with a time and activity."))

    @api.model
    def get_workspace(self):
        self.check_access_rights("read")
        domain = [("company_id", "=", self.env.company.id)]
        if self.search_count(domain) > 5000:
            raise ValidationError(_("Archive older events before loading more than 5,000 calendar entries."))
        events = self.search_read(domain, [
            "name", "date_start", "date_end", "time", "category", "status", "venue",
            "organizer", "contact", "audience", "description", "schedule", "is_sample",
        ])
        return {"events": events, "today": str(fields.Date.context_today(self)),
                "company": self.env.company.name,
                "can_create": self.check_access_rights("create", raise_exception=False),
                "can_write": self.check_access_rights("write", raise_exception=False)}

    def action_set_reminder(self):
        self.ensure_one()
        self.check_access_rights("write")
        self.check_access_rule("write")
        today = fields.Date.context_today(self)
        # Repeated clicks update this user's reminder rather than creating duplicates.
        activity = self.activity_ids.filtered(lambda item: item.user_id == self.env.user
            and item.activity_type_id == self.env.ref("mail.mail_activity_data_todo"))[:1]
        deadline = max(today, self.date_start)
        if activity:
            activity.write({"date_deadline": deadline})
        else:
            self.activity_schedule("mail.mail_activity_data_todo", user_id=self.env.uid,
                date_deadline=deadline, summary=_("Campus event: %s", self.name))
        return True
