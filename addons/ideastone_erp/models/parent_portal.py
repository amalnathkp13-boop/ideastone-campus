from datetime import timedelta
from urllib.parse import urlencode

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

NAVIGATION = [
    ("dashboard", "Overview", "home"), ("profile", "My Child", "user"),
    ("attendance", "Attendance", "calendar-check-o"), ("learning", "Learning & Homework", "book"),
    ("timetable", "Timetable & Calendar", "calendar"), ("exams", "Exams & Results", "file-text-o"),
    ("fees", "Fees & Payments", "inr"), ("notices", "School Updates", "bullhorn"),
    ("requests", "Requests & Contact", "comments-o"), ("documents", "Documents", "folder-open-o"),
]


class ParentPolicy(models.Model):
    _inherit = "res.company"

    campus_parent_portal_enabled = fields.Boolean(default=True, string="Enable Parent Portal")
    campus_parent_transport = fields.Boolean(string="Show approved transport allocations to parents")


class ParentPreferences(models.Model):
    _inherit = "res.users"

    campus_parent_notice_badge = fields.Boolean(default=True)


class ParentRequestType(models.Model):
    _inherit = "campus.student.request.type"

    portal_audience = fields.Selection([("student", "Student"), ("parent", "Parent"), ("both", "Student and parent")], default="student", required=True)
    parent_absence = fields.Boolean(string="Requires absence date range")


class ParentRequest(models.Model):
    _inherit = "campus.service.request"

    parent_absence_from = fields.Date(readonly=True)
    parent_absence_to = fields.Date(readonly=True)


class ParentNoticeRead(models.Model):
    _name = "campus.parent.notice.read"
    _description = "Parent notice acknowledgement per child"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    student_id = fields.Many2one("op.student", required=True, ondelete="cascade")
    notice_id = fields.Many2one("campus.circular", required=True, ondelete="cascade")
    _sql_constraints = [("parent_notice_unique", "unique(user_id,student_id,notice_id)", "Acknowledgement already recorded.")]


class ParentNotice(models.Model):
    _inherit = "campus.circular"

    parent_pinned = fields.Boolean(string="Pin in Parent Portal")


class ParentDocument(models.Model):
    _inherit = "campus.admission.document"

    parent_shared = fields.Boolean(readonly=True, copy=False, string="Released to linked parents")

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("parent_shared") for v in vals_list):
            raise AccessError(_("Release verified documents through the parent sharing action."))
        return super().create(vals_list)

    def write(self, vals):
        if "parent_shared" in vals:
            raise AccessError(_("Use the parent sharing action."))
        return super().write(vals)

    def action_parent_share(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        self._mvp_require("ideastone_erp.group_mvp_admissions", "ideastone_erp.group_mvp_registrar")
        for rec in self:
            if rec.company_id not in self.env.companies or rec.state != "verified":
                raise ValidationError(_("Release only verified documents in your college."))
            rec._mvp_lock()
            self.env.cr.execute("UPDATE campus_admission_document SET parent_shared=%s WHERE id=%s", [not rec.parent_shared, rec.id])
            rec.invalidate_recordset(["parent_shared"])
            rec._mvp_log("Parent document release changed")
        return True


class ParentPortal(models.AbstractModel):
    _name = "campus.parent.portal"
    _inherit = "campus.student.portal"
    _description = "Guardian-scoped projections over existing college records"

    def _children(self):
        user = self.env.user
        if not user.active or not user.has_group("base.group_portal") or user.has_group("base.group_user"):
            raise AccessError(_("This workspace requires a parent portal account."))
        parents = self.env["op.parent"].sudo().search([("user_id", "=", user.id), ("active", "=", True)])
        children = parents.student_ids.filtered(lambda s: s.active and s.company_id in user.company_ids and s.company_id.campus_parent_portal_enabled)
        if not children:
            raise AccessError(_("No active child is linked to this parent account. Contact the college office."))
        return children.sorted("id")

    def _identity(self):
        children = self._children()
        value = self.env.context.get("parent_child")
        if value:
            try:
                selected = children.filtered(lambda s: s.id == int(value))
            except (ValueError, TypeError):
                selected = children.browse()
            if not selected:
                raise AccessError(_("This child is not available to your parent account."))
            return selected
        return children[:1]

    def _request_audience(self):
        return "parent"

    def _records(self, model, domain, limit=5000, order=None):
        if model == "campus.admission.document":
            domain = domain + [("parent_shared", "=", True), ("state", "=", "verified")]
        return super()._records(model, domain, limit, order)

    def _notice_records(self, student):
        today = fields.Date.context_today(self)
        placements = student.course_detail_ids.filtered(lambda e: e.state == "running")
        return self._records("campus.circular", [
            ("company_id", "=", student.company_id.id), ("state", "=", "approved"), ("active", "=", True),
            ("audience", "in", ["all", "parent"]), ("date_from", "<=", today), "|", ("date_to", "=", False), ("date_to", ">=", today),
            "|", ("campus_managed", "=", False), ("campus_status", "=", "published"),
            "|", ("campus_course_id", "=", False), ("campus_course_id", "in", placements.course_id.ids),
            "|", ("campus_batch_id", "=", False), ("campus_batch_id", "in", placements.batch_id.ids),
            "|", ("campus_group_id", "=", False), ("campus_group_id", "in", self.env.user.groups_id.ids),
        ], limit=500, order="parent_pinned desc, date_from desc, id desc")

    @api.model
    def snapshot(self, child=None, enrolment=None, date_from=None, date_to=None):
        service = self.with_context(parent_child=child)
        student = service._identity()
        service = service.with_company(student.company_id)
        data = super(ParentPortal, service).snapshot(enrolment, date_from, date_to)
        placement = service._portal_context(enrolment, date_from, date_to)[1]
        assignments = service._learning_assignments(student, placement) if placement else self.env["op.assignment"]
        submissions = service._records("op.assignment.sub.line", [("assignment_id", "in", assignments.ids), ("student_id", "=", student.id)], limit=1000, order="id desc")
        now = fields.Datetime.now()
        homework = []
        for task in assignments:
            submission = submissions.filtered(lambda row, task=task: row.assignment_id == task)[:1]
            complete = submission.state in {"submit", "accept"}
            status = "Accepted" if submission.state == "accept" else "Submitted" if complete else "Revision requested" if submission.state == "change" else "Rejected" if submission.state == "reject" else "Closed" if task.state == "finish" else "Overdue" if task.submission_date < now else "Due soon"
            homework.append({"id": task.id, "name": task.name, "subject": task.subject_id.name, "teacher": task.faculty_id.name,
                "instructions": task.description, "issued": service._dates(task.issued_date), "due": service._dates(task.submission_date),
                "status": status, "pending": not complete and task.state != "finish", "date": task.submission_date.isoformat(),
                "feedback": submission.note if submission.campus_feedback_released else "",
                "score": submission.marks if submission.state == "accept" and submission.campus_feedback_released and task.marks else None, "maximum": task.marks})
        notices = service._notice_records(student)
        reads = self.env["campus.parent.notice.read"].sudo().search([("user_id", "=", self.env.uid), ("student_id", "=", student.id), ("notice_id", "in", notices.ids)]).notice_id
        for notice in data["notices"]:
            notice["read"] = notice["id"] in reads.ids
            notice["pinned"] = bool(notices.filtered(lambda n, notice=notice: n.id == notice["id"]).parent_pinned)
        data.update(parent_name=self.env.user.name, children=[{"id": s.id, "name": s.name} for s in service._children()],
                    homework=homework, pending_work=sum(row["pending"] for row in homework),
                    unread=len(notices - reads), notice_badge=self.env.user.campus_parent_notice_badge,
                    contact_edit=False, guardians=[], books=[], loans=[], updates=0)
        data["student"] = {key: value for key, value in data["student"].items() if key in {"name", "number", "register", "status", "admitted"}}
        data["filters"]["child"] = str(student.id)
        pending = [item for item in homework if item["pending"]]
        data["nearest_work"] = pending[0]["due"] if pending else ""
        due_dates = service._invoices(student).filtered(lambda i: i.amount_residual and i.invoice_date_due).mapped("invoice_date_due")
        data["nearest_fee"] = service._dates(min(due_dates)) if due_dates else ""
        query = urlencode(data["filters"])
        for payment in data["fees"]["payments"]:
            payment["url"] = f"/my/campus/parent/download/receipt/{payment['id']}?{query}"
        data["navigation"] = list(NAVIGATION)
        data["transport"] = []
        if student.company_id.campus_parent_transport and placement:
            routes = service._records("campus.transport.allocation", [("company_id", "=", student.company_id.id), ("student_id", "=", student.id), ("year_id", "=", placement.academic_years_id.id), ("state", "=", "approved"), ("active", "=", True), ("route_id.active", "=", True), ("stop_id.active", "=", True)])
            data["transport"] = [{"name": a.route_id.name, "stop": a.stop_id.name,
                "pickup": "%02d:%02d" % divmod(round(a.stop_id.pickup_time * 60) % 1440, 60),
                "contact": a.route_id.driver_phone or "Contact the college transport office"} for a in routes]
            if data["transport"]:
                data["navigation"].append(("transport", "Transport", "bus"))
        data["navigation"].append(("account", "Account & Help", "cog"))
        upcoming = []
        # ISO timestamps are used for ordering; display dates always come from the shared formatter.
        for session in service._records("op.session", [("id", "in", [row["id"] for row in data["schedule"]]), ("state", "=", "confirm"), ("start_datetime", ">=", now)], limit=500, order="start_datetime") if placement else []:
            upcoming.append({"key": "class-%s" % session.id, "name": session.subject_id.name, "kind": "Class", "when": service._dates(session.start_datetime), "sort": session.start_datetime.isoformat(), "target": "timetable"})
        for task in homework:
            if task["pending"] and task["date"] >= now.isoformat():
                upcoming.append({"key": "work-%s" % task["id"], "name": task["name"], "kind": "Assignment deadline", "when": task["due"], "sort": task["date"], "target": "learning"})
        for exam in data["exams"]:
            if exam["upcoming"]:
                record = self.env["op.exam"].sudo().browse(exam["id"])
                upcoming.append({"key": "exam-%s" % record.id, "name": exam["name"], "kind": "Examination", "when": exam["start"], "sort": record.start_time.isoformat(), "target": "exams"})
        data["upcoming"] = sorted(upcoming, key=lambda item: item["sort"])[:12]
        return data

    @api.model
    def act(self, operation, child=None, payload=None):
        service = self.with_context(parent_child=child)
        student = service._identity()
        service = service.with_company(student.company_id)
        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValidationError(_("Invalid form submission."))
        if operation == "notice":
            notice = service._notice_records(student).filtered(lambda n: n.id == int(payload.get("notice_id") or 0))
            if not notice or not isinstance(payload.get("read", True), bool):
                raise AccessError(_("This notice is not available."))
            service._serialize(student)
            model = self.env["campus.parent.notice.read"].sudo()
            domain = [("user_id", "=", self.env.uid), ("student_id", "=", student.id), ("notice_id", "=", notice.id)]
            existing = model.search(domain)
            if payload.get("read", True) and not existing:
                model.create({"user_id": self.env.uid, "student_id": student.id, "notice_id": notice.id})
            elif not payload.get("read", True):
                existing.unlink()
        elif operation == "preferences":
            if set(payload) != {"notice_badge"} or not isinstance(payload["notice_badge"], bool):
                raise ValidationError(_("Invalid notification preference."))
            self.env.user.sudo().campus_parent_notice_badge = payload["notice_badge"]
        elif operation in {"request", "reply", "cancel"}:
            return super(ParentPortal, service).act(operation, payload)
        else:
            raise AccessError(_("Parents may monitor records and submit permitted requests; official records cannot be changed."))
        return {"saved": True}

    def _create_request(self, student, payload):
        kind = self._types(student).filtered(lambda t: t.id == int(payload.get("type_id") or 0))
        first, last = False, False
        if kind.parent_absence:
            try:
                first, last = fields.Date.to_date(payload.get("absence_from")), fields.Date.to_date(payload.get("absence_to"))
                if not first or not last or first > last or last - first > timedelta(days=365):
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValidationError(_("Enter a valid absence date range of at most one year.")) from exc
        result = super()._create_request(student, payload)
        request = self._requests(student).filtered(lambda r: r.portal_reference == result["reference"])
        # A retry returns the original evidence, never changes dates or official attendance.
        if kind.parent_absence and not request.parent_absence_from:
            request._set_system_values({"parent_absence_from": first, "parent_absence_to": last})
        return result
