import base64
import binascii
from pathlib import PurePath

from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression

from odoo import _, api, fields, models

CATEGORIES = [
    ("infrastructure", "Infrastructure / maintenance"),
    ("work", "Work or service issue"),
    ("staff", "Staff conduct"),
    ("student", "Student conduct"),
    ("academic", "Academic issue"),
    ("fees", "Fees or accounts"),
    ("safety", "Safety / incident"),
    ("other", "Other"),
]
KINDS = [("complaint", "Complaint"), ("incident", "Incident"), ("feedback", "Feedback")]
STATES = [
    ("submitted", "Submitted"), ("assigned", "Assigned"), ("progress", "In progress"),
    ("resolved", "Resolved"), ("reopened", "Reopened"), ("closed", "Closed"),
]


class CampusComplaint(models.Model):
    _name = "campus.complaint"
    _description = "College complaint, incident and feedback case"
    _order = "create_date desc, id desc"

    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="restrict")
    reporter_id = fields.Many2one("res.users", required=True, index=True, ondelete="restrict")
    source = fields.Selection([("student", "Student"), ("parent", "Parent"), ("staff", "Staff")], required=True)
    student_id = fields.Many2one("op.student", ondelete="restrict")
    subject = fields.Char(required=True)
    description = fields.Text(required=True)
    kind = fields.Selection(KINDS, required=True, default="complaint")
    category = fields.Selection(CATEGORIES, required=True)
    location = fields.Char()
    incident_date = fields.Date()
    target_user_id = fields.Many2one("res.users", string="Person concerned", ondelete="restrict", index=True)
    target_student_id = fields.Many2one("op.student", string="Student concerned", ondelete="restrict")
    assigned_user_id = fields.Many2one("res.users", string="In-charge", ondelete="restrict", index=True)
    state = fields.Selection(STATES, required=True, default="submitted", index=True)
    resolution = fields.Text()
    respondent_statement = fields.Text()
    anonymous_to_respondent = fields.Boolean(default=True)
    resolved_at = fields.Datetime()
    closed_at = fields.Datetime()
    evidence = fields.Binary(attachment=True, copy=False)
    evidence_filename = fields.Char()
    event_ids = fields.One2many("campus.complaint.event", "complaint_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Submit complaints through the college complaints workspace."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Use the complaint workflow to update a case."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Complaint records must be retained."))

    def _lock_case(self):
        if self:
            self.env.cr.execute("SELECT id FROM campus_complaint WHERE id IN %s ORDER BY id FOR UPDATE", [tuple(self.ids)])
            self.invalidate_recordset()

    @api.constrains("company_id", "student_id", "target_student_id", "target_user_id", "assigned_user_id", "reporter_id")
    def _check_scope(self):
        for rec in self:
            if any(student and student.company_id != rec.company_id for student in (rec.student_id, rec.target_student_id)):
                raise ValidationError(_("Students on a complaint must belong to its college."))
            if any(user and rec.company_id not in user.company_ids for user in
                   (rec.reporter_id, rec.target_user_id, rec.assigned_user_id)):
                raise ValidationError(_("People on a complaint must belong to its college."))
            if rec.assigned_user_id and (rec.assigned_user_id == rec.reporter_id or rec.assigned_user_id == rec.target_user_id):
                raise ValidationError(_("A complainant or person concerned cannot be their own case handler."))


class CampusComplaintEvent(models.Model):
    _name = "campus.complaint.event"
    _description = "Immutable complaint case history"
    _order = "id"

    complaint_id = fields.Many2one("campus.complaint", required=True, ondelete="restrict", index=True)
    actor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    action = fields.Char(required=True)
    note = fields.Text()
    created_at = fields.Datetime(required=True, default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Complaint history is recorded by the workflow."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Complaint history cannot be changed."))

    def unlink(self):
        raise AccessError(_("Complaint history cannot be deleted."))


class CampusComplaintRoute(models.Model):
    _name = "campus.complaint.route"
    _description = "College complaint category in-charge"

    company_id = fields.Many2one("res.company", required=True, ondelete="restrict")
    category = fields.Selection(CATEGORIES, required=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    _sql_constraints = [("company_category_unique", "unique(company_id, category)", "Assign one in-charge per category and college.")]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Only the owner can configure complaint routing."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_("Only the owner can configure complaint routing."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Complaint routes must be reassigned rather than deleted."))

    @api.constrains("company_id", "user_id")
    def _check_route(self):
        for rec in self:
            if not rec.user_id.active or rec.user_id.share or rec.company_id not in rec.user_id.company_ids:
                raise ValidationError(_("Choose an active internal in-charge in this college."))


class ComplaintsUI(models.AbstractModel):
    _name = "campus.complaints.ui"
    _description = "Role scoped complaints workspace"

    def _owner(self):
        return self.env.user.has_group("ideastone_erp.group_mvp_owner")

    def _identity(self, child=None):
        user = self.env.user
        if not user.active or user._is_public():
            raise AccessError(_("Sign in with an active college account."))
        if user.has_group("base.group_user"):
            return "staff", self.env.company, False
        if not user.has_group("base.group_portal"):
            raise AccessError(_("A college account is required."))
        if user.is_parent or user.child_ids or self.env["op.parent"].sudo().search_count([("user_id", "=", user.id)]):
            student = self.env["campus.parent.portal"].with_context(parent_child=child)._identity()
            return "parent", student.company_id, student
        student = self.env["campus.student.portal"]._identity()
        return "student", student.company_id, student

    def _cases(self, company):
        domain = [("company_id", "=", company.id)]
        if not self._owner():
            uid = self.env.uid
            domain = expression.AND([domain, expression.OR([
                [("reporter_id", "=", uid)], [("target_user_id", "=", uid)], [("assigned_user_id", "=", uid)],
            ])])
        return self.env["campus.complaint"].sudo().search(domain, order="create_date desc, id desc")

    def _row(self, case):
        viewer = self.env.user
        owner = self._owner()
        concerned = case.target_user_id == viewer
        reporter = case.reporter_id == viewer
        assigned = case.assigned_user_id == viewer
        hide_reporter = concerned and case.anonymous_to_respondent and not owner and not reporter
        return {
            "id": case.id, "reference": f"CMP-{case.id:05d}",
            "subject": case.subject, "description": case.description,
            "source": case.source, "kind": case.kind, "category": case.category,
            "location": case.location or "", "incident_date": str(case.incident_date or ""),
            "created": str(case.create_date or "")[:16], "state": case.state,
            "reporter": "Identity withheld" if hide_reporter else case.reporter_id.name,
            "student": case.student_id.name if not hide_reporter else "",
            "concerned": case.target_student_id.name or case.target_user_id.name or "",
            "assigned": case.assigned_user_id.name or "Awaiting assignment",
            "resolution": case.resolution or "", "statement": case.respondent_statement or "",
            "has_evidence": bool(case.evidence) and not hide_reporter,
            "mine": reporter, "about_me": concerned, "assigned_to_me": assigned,
            "can_assign": owner and not concerned,
            "can_work": (owner or assigned) and not reporter and not concerned,
            "can_reopen": reporter and case.state == "resolved",
            "can_respond": concerned and case.state not in {"closed", "resolved"},
            "history": [{
                "id": event.id,
                "action": event.action, "note": event.note or "",
                "actor": "Reporter" if hide_reporter and event.actor_id == case.reporter_id else event.actor_id.name,
                "date": str(event.created_at or "")[:16],
            } for event in case.event_ids],
        }

    @api.model
    def get_page_data(self, page="dashboard", child=None):
        if page not in {"dashboard", "students", "staff"}:
            raise ValidationError(_("Choose a complaints page."))
        source, company, student = self._identity(child)
        cases = self._cases(company)
        page_cases = cases.filtered(lambda case: page == "dashboard" or
                                     (case.source in {"student", "parent"}) == (page == "students"))
        users = self.env["res.users"].sudo().search([
            ("active", "=", True), ("share", "=", False), ("company_ids", "in", company.id),
        ], order="name", limit=500)
        targets = [{"id": user.id, "name": user.name} for user in users if user.id != self.env.uid]
        feedback = []
        earlier_requests = []
        if self._owner() and page == "dashboard":
            feedback = [{
                "id": rec.id, "subject": rec.name, "reporter": rec.respondent_id.name,
                "kind": rec.kind, "score": rec.score, "comments": rec.comments or "",
                "date": str(rec.create_date or "")[:10],
            } for rec in self.env["campus.feedback"].sudo().search([
                ("company_id", "=", company.id),
            ], order="create_date desc, id desc", limit=20)]
            earlier_requests = [{
                "id": rec.id, "subject": rec.name, "reporter": rec.requester_id.name,
                "kind": rec.kind, "state": rec.state, "description": rec.description or "",
                "date": str(rec.create_date or "")[:10],
            } for rec in self.env["campus.service.request"].sudo().search([
                ("company_id", "=", company.id), ("kind", "in", ["grievance", "student_complaint"]),
            ], order="create_date desc, id desc", limit=20)]
        return {
            "rows": [self._row(case) for case in page_cases],
            "counts": {
                "submitted": len(cases.filtered(lambda c: c.state in {"submitted", "reopened"})),
                "assigned": len(cases.filtered(lambda c: c.state in {"assigned", "progress"})),
                "resolved": len(cases.filtered(lambda c: c.state in {"resolved", "closed"})),
                "about_me": len(cases.filtered(lambda c: c.target_user_id.id == self.env.uid)),
                "mine": len(cases.filtered(lambda c: c.reporter_id.id == self.env.uid)),
                "in_charge": len(cases.filtered(lambda c: c.assigned_user_id.id == self.env.uid and c.state not in {"closed", "resolved"})),
            },
            "owner": self._owner(), "source": source, "company": company.name,
            "student_id": student.id if student else False,
            "categories": CATEGORIES, "kinds": KINDS, "states": STATES, "staff_targets": targets,
            "routes": [{
                "category": route.category, "user_id": route.user_id.id, "user": route.user_id.name,
            } for route in self.env["campus.complaint.route"].sudo().search([("company_id", "=", company.id)])
                ] if self._owner() else [],
            "earlier_feedback": feedback, "earlier_requests": earlier_requests,
        }

    def _evidence(self, content, filename):
        if not content:
            return False, False
        filename = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        if not filename or len(filename) > 120 or any(ord(c) < 32 for c in filename):
            raise ValidationError(_("Use a safe evidence filename."))
        if len(content) > 7_000_000:
            raise ValidationError(_("Evidence must be at most 5 MB."))
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError(_("Evidence is not a valid file.")) from exc
        suffix = PurePath(filename).suffix.lower()
        valid = (suffix == ".pdf" and raw.startswith(b"%PDF-") or
                 suffix == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n") or
                 suffix in {".jpg", ".jpeg"} and raw.startswith(b"\xff\xd8\xff"))
        if not raw or len(raw) > 5 * 1024 * 1024 or not valid:
            raise ValidationError(_("Attach a PDF, PNG or JPEG of at most 5 MB."))
        return base64.b64encode(raw), filename

    def _handler(self, company, category, excluded):
        route = self.env["campus.complaint.route"].sudo().search([
            ("company_id", "=", company.id), ("category", "=", category),
        ], limit=1)
        if route.user_id.active and not route.user_id.share and company in route.user_id.company_ids and route.user_id.id not in excluded:
            return route.user_id
        groups = {
            "infrastructure": "group_services", "work": "group_services",
            "staff": "group_people", "student": "group_academic",
            "academic": "group_academic", "fees": "group_mvp_accountant",
            "safety": "group_manager", "other": "group_manager",
        }
        group = self.env.ref("ideastone_erp." + groups[category])
        candidates = group.sudo().users.filtered(
            lambda user: user.active and company in user.company_ids and user.id not in excluded)
        nonowners = candidates.filtered(lambda user: not user.has_group("ideastone_erp.group_mvp_owner"))
        return (nonowners or candidates)[:1]

    @api.model
    def save_route(self, category, user_id):
        if not self._owner():
            raise AccessError(_("Only the owner can configure complaint routing."))
        if category not in dict(CATEGORIES):
            raise ValidationError(_("Choose a valid complaint category."))
        try:
            user_id = int(user_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid in-charge staff member.")) from exc
        user = self.env["res.users"].sudo().browse(user_id).exists()
        if not user or not user.active or user.share or self.env.company not in user.company_ids:
            raise AccessError(_("Choose an active staff member in this college."))
        routes = self.env["campus.complaint.route"].sudo()
        route = routes.search([("company_id", "=", self.env.company.id), ("category", "=", category)], limit=1)
        if route:
            route.write({"user_id": user.id})
        else:
            routes.create({"company_id": self.env.company.id, "category": category, "user_id": user.id})
        return True

    @api.model
    def submit(self, values, child=None):
        source, company, student = self._identity(child)
        if self._owner():
            raise AccessError(_("The owner workspace reviews submitted cases."))
        if not isinstance(values, dict):
            raise ValidationError(_("Enter the complaint details."))
        subject = str(values.get("subject") or "").strip()
        description = str(values.get("description") or "").strip()
        category = values.get("category")
        kind = values.get("kind") or "complaint"
        location = str(values.get("location") or "").strip()
        if not subject or len(subject) > 180 or not description or len(description) > 5000 or len(location) > 200:
            raise ValidationError(_("Enter a subject and description within the allowed lengths."))
        if category not in dict(CATEGORIES) or kind not in dict(KINDS):
            raise ValidationError(_("Choose a valid case type and category."))
        incident_date = fields.Date.to_date(values.get("incident_date")) if values.get("incident_date") else False
        if incident_date and incident_date > fields.Date.context_today(self):
            raise ValidationError(_("The incident date cannot be in the future."))
        target_user = self.env["res.users"]
        target_student = self.env["op.student"]
        if category == "staff" and values.get("target_user_id"):
            try:
                target_id = int(values["target_user_id"])
            except (TypeError, ValueError) as exc:
                raise ValidationError(_("Choose a valid staff member.")) from exc
            target_user = self.env["res.users"].sudo().browse(target_id).exists()
            if not target_user or not target_user.active or target_user.share or company not in target_user.company_ids or target_user.id == self.env.uid:
                raise AccessError(_("Choose another active staff member in this college."))
        if category == "student" and values.get("student_number"):
            number = str(values["student_number"]).strip()
            target_student = self.env["op.student"].sudo().search([
                ("company_id", "=", company.id), ("gr_no", "=", number),
            ], limit=1)
            if not target_student:
                raise ValidationError(_("Enter a valid student register number."))
            target_user = target_student.user_id
            if target_user.id == self.env.uid:
                raise ValidationError(_("Choose another student."))
        if category in {"staff", "student"} and kind != "feedback" and not (target_user or target_student):
            raise ValidationError(_("Identify the person concerned for this type of complaint."))
        evidence, filename = self._evidence(values.get("evidence"), values.get("evidence_filename"))
        handler = self._handler(company, category, {self.env.uid, target_user.id})
        case = self.env["campus.complaint"].sudo().create({
            "company_id": company.id, "reporter_id": self.env.uid, "source": source,
            "student_id": student.id if student else False,
            "subject": subject, "description": description, "kind": kind, "category": category,
            "location": location, "incident_date": incident_date,
            "target_user_id": target_user.id, "target_student_id": target_student.id,
            "assigned_user_id": handler.id, "state": "assigned" if handler else "submitted",
            "anonymous_to_respondent": values.get("anonymous_to_respondent", True) in (True, 1, "1", "true"),
            "evidence": evidence, "evidence_filename": filename,
        })
        self.env["campus.complaint.event"].sudo().create({
            "complaint_id": case.id, "actor_id": self.env.uid, "action": "Submitted",
        })
        return {"id": case.id, "reference": f"CMP-{case.id:05d}"}

    @api.model
    def act(self, case_id, operation, values=None, child=None):
        _source, company, _student = self._identity(child)
        try:
            case_id = int(case_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid complaint.")) from exc
        case = self._cases(company).filtered(lambda c: c.id == case_id)[:1]
        if not case:
            raise AccessError(_("This complaint is not available to your account."))
        case._lock_case()
        values = values if isinstance(values, dict) else {}
        owner = self._owner()
        reporter = case.reporter_id.id == self.env.uid
        concerned = case.target_user_id.id == self.env.uid
        assigned = case.assigned_user_id.id == self.env.uid
        if operation == "assign" and owner and not concerned and case.state not in {"closed", "resolved"}:
            try:
                user_id = int(values.get("user_id") or 0)
            except (TypeError, ValueError) as exc:
                raise ValidationError(_("Choose an in-charge staff member.")) from exc
            user = self.env["res.users"].sudo().browse(user_id).exists()
            if not user or not user.active or user.share or company not in user.company_ids or user in (case.reporter_id, case.target_user_id):
                raise AccessError(_("The in-charge must be another active staff member in this college."))
            updates, label = {"assigned_user_id": user.id, "state": "assigned"}, "Assigned"
        elif operation == "start" and (assigned or owner) and not reporter and not concerned and case.state in {"assigned", "submitted", "reopened"}:
            updates, label = {"state": "progress"}, "Work started"
        elif operation == "resolve" and (assigned or owner) and not reporter and not concerned and case.state in {"assigned", "progress", "reopened"}:
            resolution = str(values.get("resolution") or "").strip()
            if not resolution or len(resolution) > 5000:
                raise ValidationError(_("Record a resolution before resolving the case."))
            updates, label = {"state": "resolved", "resolution": resolution, "resolved_at": fields.Datetime.now()}, "Resolved"
        elif operation == "close" and owner and not concerned and not reporter and case.state == "resolved":
            updates, label = {"state": "closed", "closed_at": fields.Datetime.now()}, "Closed"
        elif operation == "reopen" and reporter and case.state == "resolved":
            note = str(values.get("note") or "").strip()
            if not note or len(note) > 2000:
                raise ValidationError(_("Explain why the case needs another review."))
            updates, label = {"state": "reopened"}, "Reopened"
        elif operation == "respond" and concerned and case.state not in {"closed", "resolved"}:
            note = str(values.get("note") or "").strip()
            if not note or len(note) > 3000:
                raise ValidationError(_("Enter a statement within 3000 characters."))
            updates, label = {"respondent_statement": note}, "Response from person concerned"
        else:
            raise AccessError(_("This case action is unavailable for your role or its current status."))
        case.sudo().write(updates)
        self.env["campus.complaint.event"].sudo().create({
            "complaint_id": case.id, "actor_id": self.env.uid, "action": label,
            "note": note if operation in {"reopen", "respond"} else updates.get("resolution", ""),
        })
        return self._row(case)

    @api.model
    def evidence(self, case_id, child=None):
        _source, company, _student = self._identity(child)
        try:
            case_id = int(case_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid complaint.")) from exc
        case = self._cases(company).filtered(lambda c: c.id == case_id)[:1]
        if not case or not case.evidence or (
            case.target_user_id.id == self.env.uid and case.anonymous_to_respondent
            and not self._owner() and case.reporter_id.id != self.env.uid
        ):
            raise AccessError(_("Evidence is not available to this account."))
        return case.evidence.decode() if isinstance(case.evidence, bytes) else case.evidence, case.evidence_filename or "evidence"


class ComplaintsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if not self.env.user.has_group("base.group_user"):
            return data
        actions = [("Dashboard", "dashboard"), ("Student complaints", "students"), ("Staff complaints", "staff")]
        items = [{
            "label": label, "action": f"ideastone_erp.action_complaints_{page}",
            "action_id": self.env.ref(f"ideastone_erp.action_complaints_{page}").id,
            "model": "res.users", "allowed": True, "group": "Complaints",
        } for label, page in actions]
        data["faculty_modules"].append({"key": "complaints", "label": "Complaints", "icon": "commenting-o", "items": items})
        data["navigation"].extend(items)
        return data

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{
            f"action_complaints_{page}": "res.users" for page in ("dashboard", "students", "staff")
        })
