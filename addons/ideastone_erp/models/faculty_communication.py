from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

KINDS = {
    "surveys": {"Draft", "Open", "Published", "Closed"},
    "events": {"New", "Announced", "Booked", "In progress", "Ended", "Cancelled"},
    "alumni": {"Active", "Needs review", "Archived"},
}


class FacultyCommunicationRecord(models.Model):
    _name = "campus.faculty.communication.record"
    _description = "Faculty communication workspace record"
    _order = "date asc, id asc"

    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="cascade")
    created_by = fields.Many2one("res.users", required=True, index=True, ondelete="restrict")
    kind = fields.Selection([(key, key.title()) for key in KINDS], required=True, index=True)
    name = fields.Char(required=True)
    owner = fields.Char(required=True)
    date = fields.Date(required=True)
    status = fields.Char(required=True)
    description = fields.Text()
    venue = fields.Char()
    end_date = fields.Date()
    start_time = fields.Char(default="09:00")
    end_time = fields.Char(default="10:00")
    website = fields.Char()
    registered = fields.Integer(default=0)
    attended = fields.Integer(default=0)
    success_ratio = fields.Float(default=0)
    average_score = fields.Float(default=0)
    average_duration = fields.Char(default="00:00")
    posts = fields.Integer(default=0)
    views = fields.Integer(default=0)


class FacultyCommunication(models.AbstractModel):
    _name = "campus.faculty.communication"
    _description = "Faculty communication workspace service"

    def _check_faculty(self):
        if not self.env.user.has_group("openeducat_core.group_op_faculty"):
            raise AccessError(_("The communication workspace requires a faculty account."))
        faculty = self.env["op.faculty"].sudo().search([
            ("user_id", "=", self.env.uid), ("active", "=", True),
            "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not faculty:
            raise AccessError(_("Link this account to an active faculty record in the current college."))

    @api.model
    def get_data(self):
        self._check_faculty()
        records = self.env["campus.faculty.communication.record"].sudo().search([
            ("company_id", "=", self.env.company.id),
        ], order="id desc", limit=300)
        rows = {kind: [] for kind in KINDS}
        for record in records:
            rows[record.kind].append({
                "id": record.id, "name": record.name, "owner": record.owner,
                "date": str(record.date), "status": record.status,
                "description": record.description or "", "venue": record.venue or "To be confirmed",
                "end": str(record.end_date or record.date), "start_time": record.start_time or "09:00",
                "end_time": record.end_time or "10:00", "website": record.website or "Internal forum",
                "registered": record.registered, "attended": record.attended,
                "success": record.success_ratio, "score": record.average_score,
                "duration": record.average_duration or "00:00", "posts": record.posts, "views": record.views,
            })
        for entries in rows.values():
            entries.sort(key=lambda row: (row["date"], row["id"]))
        # Keep the existing Odoo communication records visible during the page redesign.
        # A matching workspace record takes precedence so preview data is not doubled.
        seen = {kind: {row["name"].casefold() for row in entries} for kind, entries in rows.items()}
        surveys = self.env["survey.survey"].sudo().search([
            ("user_id.company_id", "=", self.env.company.id),
        ], limit=100)
        for survey in surveys:
            if survey.title.casefold() in seen["surveys"]:
                continue
            duration = round(float(survey.answer_duration_avg or 0))
            rows["surveys"].append({"id": f"native-survey-{survey.id}", "name": survey.title,
                "owner": survey.user_id.name or "College", "date": str(survey.create_date.date()),
                "status": "Closed" if not survey.active else "Published" if survey.answer_count else "Draft",
                "duration": f"{duration // 60:02d}:{duration % 60:02d}", "registered": survey.answer_count,
                "success": survey.success_ratio or 0, "score": survey.answer_score_avg or 0})
        events = self.env["event.event"].sudo().search([("company_id", "=", self.env.company.id)], limit=100)
        for event in events:
            if event.name.casefold() in seen["events"]:
                continue
            stage = event.stage_id.name or "New"
            rows["events"].append({"id": f"native-event-{event.id}", "name": event.name,
                "owner": event.user_id.name or "College", "date": str(event.date_begin.date()),
                "end": str(event.date_end.date()), "start_time": event.date_begin.strftime("%H:%M"),
                "end_time": event.date_end.strftime("%H:%M"), "venue": event.address_id.name or "To be confirmed",
                "registered": event.seats_taken, "attended": event.seats_used,
                "status": stage if stage in KINDS["events"] else "New"})
        forums = self.env["forum.forum"].sudo().search([
            "|", ("website_id", "=", False), ("website_id.company_id", "=", self.env.company.id),
        ], limit=100)
        for forum in forums:
            if forum.name.casefold() in seen["alumni"]:
                continue
            rows["alumni"].append({"id": f"native-forum-{forum.id}", "name": forum.name,
                "website": forum.website_id.name or "Internal forum", "posts": forum.total_posts,
                "views": forum.total_views, "status": "Active" if forum.active else "Archived",
                "date": str(forum.create_date.date())})
        for entries in rows.values():
            entries.sort(key=lambda row: (row["date"], str(row["id"])))
        return {"rows": rows, "today": str(fields.Date.context_today(self)), "company": self.env.company.name}

    @api.model
    def create_record(self, kind, values):
        self._check_faculty()
        if kind not in KINDS or not isinstance(values, dict):
            raise ValidationError(_("Choose a valid communication record type."))
        name = str(values.get("name") or "").strip()
        owner = str(values.get("owner") or "").strip()
        description = str(values.get("description") or "").strip()
        status = str(values.get("status") or "").strip()
        if not name or not owner or len(name) > 120 or len(owner) > 100 or len(description) > 4000:
            raise ValidationError(_("Enter a title and responsible person within the allowed lengths."))
        if status not in KINDS[kind]:
            raise ValidationError(_("Choose a valid status for this section."))
        try:
            date = fields.Date.to_date(values.get("date"))
        except (TypeError, ValueError):
            date = None
        if not date:
            raise ValidationError(_("Enter a valid date."))
        return self.env["campus.faculty.communication.record"].sudo().create({
            "company_id": self.env.company.id, "created_by": self.env.uid,
            "kind": kind, "name": name, "owner": owner, "date": date,
            "status": status, "description": description,
        }).id
