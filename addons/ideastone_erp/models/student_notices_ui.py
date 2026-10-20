from datetime import timedelta

from odoo.tools import html2plaintext, html_sanitize

from odoo import api, fields, models


class StudentNoticePriority(models.Model):
    _inherit = "campus.circular"

    campus_portal_priority = fields.Selection([("general", "General"), ("important", "Important"), ("action", "Action")],
                                              default="general", required=True, string="Student notice priority")


class StudentNoticesUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _calendar_item(self, key, name, start, end, category, tone="academic", location=""):
        local_start = fields.Datetime.context_timestamp(self, start)
        local_end = fields.Datetime.context_timestamp(self, end - timedelta(microseconds=1) if end > start else end)
        return {"key": key, "name": name, "start_day": local_start.date().isoformat(), "end_day": local_end.date().isoformat(),
                "start_utc": start.strftime("%Y%m%dT%H%M%SZ"), "end_utc": end.strftime("%Y%m%dT%H%M%SZ"),
                "when": self._dates(start), "end": self._dates(end), "month": local_start.strftime("%b").upper(),
                "number": local_start.strftime("%d"), "category": category, "tone": tone, "location": location}

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student = self._identity()
        records = {record.id: record for record in self._notice_records(student)}
        priorities = {"general": "General", "important": "Important", "action": "Action"}
        notices = []
        for row in data["notices"]:
            record = records[row["id"]]
            priority = record.campus_portal_priority
            notices.append(dict(row, reference=record.reference, priority=priority, priority_label=priorities[priority],
                                summary=html2plaintext(row["body"])[:300], expires=self._dates(record.date_to),
                                audience="Students" if record.audience == "student" else "Everyone",
                                tone="urgent" if priority == "important" else "soon" if priority == "action" else "new" if not row["read"] else "general"))
        now = fields.Datetime.now()
        # Events are public website publications belonging to this college only.
        event_records = self._records("event.event", [("company_id", "=", student.company_id.id), ("active", "=", True),
            ("is_published", "=", True), ("date_end", ">=", now - timedelta(days=366)), ("date_begin", "<=", now + timedelta(days=1096))], limit=2000, order="date_begin, id")
        calendar, events = [], []
        for event in event_records:
            category = event.event_type_id.name or "College event"
            label = category.lower()
            theme, tone = ("pink", "culture") if any(word in label for word in ("cultur", "music", "entertain")) else ("green", "sports") if any(word in label for word in ("sport", "fitness", "community", "wellbeing")) else ("orange", "academic") if any(word in label for word in ("career", "workshop", "learning")) else ("dark", "academic")
            item = self._calendar_item("event-%s" % event.id, event.name, event.date_begin, event.date_end, category, tone, event.address_id.name or "Venue not assigned")
            calendar.append(item)
            if event.date_end >= now:
                description = html_sanitize(event.description or "")
                events.append(dict(item, description=description, summary=event.subtitle or html2plaintext(description)[:260],
                                   theme=theme, period=item["start_day"][:7], organizer=event.organizer_id.name or data["company"]))
        for exam in self.env["op.exam"].sudo().browse([row["id"] for row in data["exams"]]):
            calendar.append(self._calendar_item("exam-%s" % exam.id, "%s · %s" % (exam.name, exam.subject_id.name), exam.start_time, exam.end_time, "Academic / exams"))
        calendar.sort(key=lambda item: (item["start_utc"], item["key"]))
        upcoming = [item for item in calendar if item["end_utc"] >= now.strftime("%Y%m%dT%H%M%SZ")]
        important = sorted(notices, key=lambda row: {"important": 0, "action": 1, "general": 2}[row["priority"]])[:3]
        data["notice_ui"] = {"notices": notices, "important": important, "categories": sorted({row["category"] for row in notices}),
                             "events": events, "event_categories": sorted({row["category"] for row in events}),
                             "periods": sorted({(row["period"], row["when"].split(',')[0][3:]) for row in events}),
                             "calendar": calendar, "upcoming": upcoming[:4],
                             "this_month": sum(item["start_day"][:7] <= data["today_iso"][:7] <= item["end_day"][:7] for item in calendar),
                             "next": next((item for item in upcoming if item["start_utc"] >= now.strftime("%Y%m%dT%H%M%SZ")), None)}
        return data
