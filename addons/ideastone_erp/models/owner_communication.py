from datetime import datetime, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html_escape

from odoo import _, api, fields, models


class OwnerCommunicationNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        modules = super()._owner_modules()
        if not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            return modules
        return [(key, label, icon, [
            ("Communication overview", "action_owner_communication_overview"),
            ("Notices & audiences", "action_owner_communication_notices"),
            ("Student requests & support", "action_owner_communication_requests"),
        ] if key == "communication" else items) for key, label, icon, items in modules]

    def _client_action_models(self):
        return dict(super()._client_action_models(),
                    action_owner_communication_overview="campus.circular",
                    action_owner_communication_notices="campus.circular",
                    action_owner_communication_requests="campus.service.request")


class OwnerNoticeSchedule(models.Model):
    _inherit = "campus.circular"

    communication_publish_at = fields.Datetime(string="Planned publication time")

    def action_campus_publish(self):
        if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            raise AccessError(_("College administrator permission is required to publish notices."))
        self._lock()
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.campus_status != "draft" or rec.date_to and rec.date_to < today:
                raise ValidationError(_("Publish an unexpired draft notice."))
            if rec.campus_batch_id and rec.campus_batch_id.course_id != rec.campus_course_id:
                raise ValidationError(_("Target section must belong to the selected programme."))
            future = rec.communication_publish_at > now if rec.communication_publish_at else rec.date_from > today
            rec._set_system_values({"campus_status": "scheduled" if future else "published", "state": "submitted" if future else "approved",
                                    "approved_by": self.env.uid, "approved_on": now})
            self.env["campus.mvp.audit"]._log(rec, "Notice scheduled" if future else "Notice published")
        return True

    @api.model
    def _cron_publish_notices(self):
        result = super()._cron_publish_notices()
        now = fields.Datetime.now()
        for rec in self.search([("campus_managed", "=", True), ("campus_status", "=", "scheduled"),
                                ("communication_publish_at", "!=", False), ("communication_publish_at", "<=", now)]):
            rec._set_system_values({"campus_status": "published", "state": "approved"})
        return result


class OwnerRequestCategory(models.Model):
    _inherit = "campus.service.request"

    communication_category = fields.Selection([
        ("documents", "Certificates & documents"),
        ("fees", "Fees & scholarships"),
        ("it", "Portal / IT support"),
        ("affairs", "Student affairs"),
        ("other", "Other support"),
    ], string="Communication category")
    communication_due_at = fields.Datetime(string="Response target")


class OwnerCommunicationUI(models.AbstractModel):
    _name = "campus.owner.communication.ui"
    _description = "Owner communication workspace"

    def _check_owner(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            raise AccessError(_("Owner admin access is required for this workspace."))

    def _period(self, code):
        today = fields.Date.context_today(self)
        if code == "term":
            rec = self.env["op.academic.term"].search([("company_id", "=", self.env.company.id), ("term_start_date", "<=", today), ("term_end_date", ">=", today)], limit=1)
            if rec:
                return rec.term_start_date, rec.term_end_date, rec.name
        if code == "year":
            rec = self.env["op.academic.year"].search([("company_id", "=", self.env.company.id), ("start_date", "<=", today), ("end_date", ">=", today)], limit=1)
            if rec:
                return rec.start_date, rec.end_date, rec.name
        return today.replace(day=1), (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), today.strftime("%B %Y")

    def _notice_row(self, rec):
        status = "Needs approval" if rec.state == "submitted" and rec.campus_status == "draft" else dict(rec._fields["campus_status"].selection).get(rec.campus_status, "Draft")
        reads = self.env["campus.student.notice.read"].sudo().search_count([("notice_id", "=", rec.id), ("company_id", "=", self.env.company.id)]) if rec.campus_status == "published" else 0
        return {"id": rec.id, "reference": rec.reference, "name": rec.name, "category": rec.campus_category or "General",
                "audience": "Selected department / class" if rec.campus_course_id else "Specific student group" if rec.campus_group_id else dict(rec._fields["audience"].selection).get(rec.audience),
                "audience_code": rec.audience, "course_id": rec.campus_course_id.id or 0, "batch_id": rec.campus_batch_id.id or 0,
                "group_id": rec.campus_group_id.id or 0, "publish_at": fields.Datetime.to_string(rec.communication_publish_at) if rec.communication_publish_at else "",
                "date": str(rec.date_from), "owner": rec.create_uid.name, "reach": f"{reads} portal reads" if rec.campus_status == "published" else "—",
                "status": status, "status_code": "attention" if status == "Needs approval" else rec.campus_status,
                "body": rec.body or "", "updated": fields.Datetime.to_string(rec.write_date)}

    def _request_row(self, rec):
        priority = "High" if rec.portal_priority == "time_sensitive" else "Normal"
        office = dict(rec._fields["portal_requested_office"].selection).get(rec.portal_requested_office, "Route automatically")
        state = dict(rec._fields["state"].selection).get(rec.state, rec.state)
        return {"id": rec.id, "reference": rec.portal_reference or f"REQ-{rec.id:05d}", "student": rec.student_id.name or "—",
                "student_number": rec.student_id.gr_no or "", "category": dict(rec._fields["communication_category"].selection).get(rec.communication_category) or rec.portal_type_id.name or dict(rec._fields["kind"].selection).get(rec.kind),
                "type_id": rec.portal_type_id.id or 0, "name": rec.name, "office": office, "office_code": rec.portal_requested_office,
                "updated": fields.Datetime.to_string(rec.write_date), "priority": priority, "priority_code": rec.portal_priority,
                "state": state, "state_code": rec.state, "due_at": fields.Datetime.to_string(rec.communication_due_at) if rec.communication_due_at else "",
                "reply": rec.portal_reply or "", "description": rec.description or ""}

    @api.model
    def snapshot(self, period="month"):
        self._check_owner()
        first, last, label = self._period(period)
        company = self.env.company.id
        notices = self.env["campus.circular"].search([("company_id", "=", company), ("campus_managed", "=", True)], order="write_date desc, id desc", limit=300)
        requests = self.env["campus.service.request"].search([("company_id", "=", company), ("student_id", "!=", False)], order="write_date desc, id desc", limit=300)
        period_notices = notices.filtered(lambda r: first <= r.date_from <= last)
        period_requests = requests.filtered(lambda r: first <= r.date <= last)
        published = period_notices.filtered(lambda r: r.campus_status == "published")
        scheduled = period_notices.filtered(lambda r: r.campus_status == "scheduled")
        open_requests = requests.filtered(lambda r: r.state not in {"done", "cancelled", "rejected"})
        high = open_requests.filtered(lambda r: r.portal_priority == "time_sensitive")
        due = open_requests.filtered(lambda r: r.communication_due_at and fields.Datetime.context_timestamp(self, r.communication_due_at).date() == fields.Date.context_today(self))
        resolved = requests.filtered(lambda r: r.state == "done" and r.write_date and first <= fields.Datetime.context_timestamp(self, r.write_date).date() <= last)
        response_hours = []
        for rec in period_requests:
            first_response = rec.portal_event_ids.filtered(lambda event: event.name == "College response").sorted("create_date")[:1]
            if first_response:
                response_hours.append(max(0, (first_response.create_date - rec.create_date).total_seconds() / 3600))
        notice_rows = [self._notice_row(r) for r in notices]
        request_rows = [self._request_row(r) for r in requests]
        types = self.env["campus.student.request.type"].search(["|", ("company_id", "=", False), ("company_id", "=", company)])
        students = self.env["op.student"].search([("company_id", "=", company), ("user_id", "!=", False)], limit=500)
        courses = self.env["op.course"].search([("company_id", "=", company)], limit=200)
        batches = self.env["op.batch"].search([("company_id", "=", company)], limit=300)
        groups = self.env["res.groups"].search([], limit=300)
        return {"company": self.env.company.name, "period_label": label, "today": str(fields.Date.context_today(self)),
                "counts": {"published": len(published), "scheduled": len(scheduled), "drafts": len(period_notices.filtered(lambda r: r.campus_status == "draft" and r.state == "draft")),
                           "attention": len(period_notices.filtered(lambda r: r.campus_status == "draft" and r.state == "submitted")),
                           "open": len(open_requests), "high": len(high), "due": len(due), "resolved": len(resolved),
                           "avg_response": round(sum(response_hours) / len(response_hours), 1) if response_hours else False,
                           "reads": sum(self.env["campus.student.notice.read"].sudo().search_count([("notice_id", "=", r.id), ("company_id", "=", company)]) for r in published)},
                "notices": notice_rows, "requests": request_rows,
                "types": [{"id": r.id, "name": r.name, "kind": r.kind} for r in types],
                "students": [{"id": r.id, "name": r.name, "number": r.gr_no or ""} for r in students],
                "courses": [{"id": r.id, "name": r.name} for r in courses],
                "batches": [{"id": r.id, "name": r.name, "course_id": r.course_id.id} for r in batches],
                "groups": [{"id": r.id, "name": r.name} for r in groups]}

    def _local_datetime(self, value):
        if not value:
            return False
        try:
            local = datetime.fromisoformat(value)
            if local.tzinfo:
                return local.astimezone(pytz.UTC).replace(tzinfo=None)
            zone = pytz.timezone(self.env.user.tz or "UTC")
            return zone.localize(local).astimezone(pytz.UTC).replace(tzinfo=None)
        except (ValueError, TypeError, pytz.AmbiguousTimeError, pytz.NonExistentTimeError) as exc:
            raise ValidationError(_("Choose a valid date and time.")) from exc

    @api.model
    def save_notice(self, values, record_id=False, submit=False):
        self._check_owner()
        model = self.env["campus.circular"]
        model.check_access_rights("write" if record_id else "create")
        title = str(values.get("name") or "").strip()
        body = str(values.get("body") or "").strip()
        if not title or not body or len(title) > 200 or len(body) > 10000:
            raise ValidationError(_("Enter a notice title and message within the length limits."))
        category = str(values.get("category") or "General")
        if category not in {"Academic", "Examination", "Finance", "Events", "General"}:
            raise ValidationError(_("Choose a valid notice category."))
        audience = values.get("audience")
        if audience not in {"all", "student", "faculty", "department", "group"}:
            raise ValidationError(_("Choose a valid audience."))
        course = self.env["op.course"].browse(int(values.get("course_id") or 0)).exists()
        batch = self.env["op.batch"].browse(int(values.get("batch_id") or 0)).exists()
        group = self.env["res.groups"].browse(int(values.get("group_id") or 0)).exists()
        if audience == "department" and not course:
            raise ValidationError(_("Choose a programme for the selected department or class."))
        if course and course.company_id != self.env.company or batch and (batch.company_id != self.env.company or batch.course_id != course):
            raise AccessError(_("The selected class must belong to your college and programme."))
        if audience == "group" and not group:
            raise ValidationError(_("Choose a recipient group."))
        publish_at = self._local_datetime(values.get("publish_at"))
        local_date = fields.Datetime.context_timestamp(self, publish_at).date() if publish_at else fields.Date.context_today(self)
        vals = {"name": title, "body": "<p>" + html_escape(body).replace("\n", "<br/>") + "</p>", "campus_category": category,
                "audience": "student" if audience in {"department", "group"} else audience,
                "campus_course_id": course.id if audience == "department" else False,
                "campus_batch_id": batch.id if audience == "department" else False,
                "campus_group_id": group.id if audience == "group" else False,
                "date_from": local_date, "communication_publish_at": publish_at or False}
        if record_id:
            rec = model.search([("id", "=", int(record_id)), ("company_id", "=", self.env.company.id), ("campus_managed", "=", True)], limit=1)
            if not rec or rec.campus_status != "draft" or rec.state != "draft":
                raise AccessError(_("Only a draft notice in your college can be edited."))
            rec.write(vals)
        else:
            reference = self.env["ir.sequence"].next_by_code("campus.owner.communication")
            if not reference:
                raise ValidationError(_("Configure college communication numbering before creating notices."))
            vals.update(company_id=self.env.company.id, campus_managed=True,
                        reference=reference)
            rec = model.create(vals)
        if submit:
            rec.action_submit()
        return rec.id

    @api.model
    def publish_notice(self, record_id):
        self._check_owner()
        rec = self.env["campus.circular"].search([("id", "=", int(record_id)), ("company_id", "=", self.env.company.id),
                                                 ("campus_managed", "=", True)], limit=1)
        if not rec or rec.state != "submitted":
            raise ValidationError(_("Choose a notice awaiting approval."))
        rec.action_campus_publish()
        return True

    @api.model
    def log_request(self, values):
        self._check_owner()
        student = self.env["op.student"].search([("id", "=", int(values.get("student_id") or 0)),
                                                 ("company_id", "=", self.env.company.id)], limit=1)
        request_type = self.env["campus.student.request.type"].search([("id", "=", int(values.get("type_id") or 0)),
             "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)], limit=1)
        if not student or not student.user_id or self.env.company not in student.user_id.company_ids or not request_type:
            raise ValidationError(_("Choose a student with a portal account and a request category."))
        name = str(values.get("name") or "").strip()
        description = str(values.get("description") or "").strip()
        if not name or not description or len(name) > 200 or len(description) > 10000:
            raise ValidationError(_("Enter a request subject and details within the length limits."))
        office = values.get("office") or "auto"
        priority = values.get("priority") or "normal"
        category = values.get("category") or "other"
        due_at = self._local_datetime(values.get("due_at"))
        model = self.env["campus.service.request"]
        if office not in dict(model._fields["portal_requested_office"].selection) or priority not in dict(model._fields["portal_priority"].selection) or category not in dict(model._fields["communication_category"].selection):
            raise ValidationError(_("Choose a valid category, office and priority."))
        rec = model.create({"name": name, "description": description, "kind": request_type.kind, "portal_type_id": request_type.id,
                            "student_id": student.id, "requester_id": student.user_id.id, "company_id": self.env.company.id,
                            "portal_requested_office": office, "portal_priority": priority, "communication_category": category,
                            "communication_due_at": due_at or False})
        rec.action_submit()
        return rec.id

    @api.model
    def respond_request(self, record_id, reply, next_state=False):
        self._check_owner()
        rec = self.env["campus.service.request"].search([("id", "=", int(record_id)), ("company_id", "=", self.env.company.id),
                                                         ("portal_type_id", "!=", False)], limit=1)
        if not rec:
            raise AccessError(_("The request is outside your college workspace."))
        reply = str(reply or "").strip()
        if len(reply) > 10000:
            raise ValidationError(_("Keep the response within 10,000 characters."))
        if reply != (rec.portal_reply or ""):
            rec.write({"portal_reply": reply})
        if next_state and next_state != rec.state:
            if next_state not in {"information", "approved", "rejected", "ready", "done"}:
                raise ValidationError(_("Choose a valid request status."))
            rec.write({"state": next_state})
        return True
