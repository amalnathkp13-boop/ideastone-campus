import re
import uuid

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StudentODPolicy(models.Model):
    _inherit = "res.company"

    campus_od_default_tokens = fields.Integer(
        string="OD tokens per semester", default=30,
        groups="ideastone_erp.group_mvp_registrar,ideastone_erp.group_manager",
    )
    campus_od_token_rule = fields.Selection(
        [("request", "One token per request"), ("day", "One token per OD day")],
        string="OD token charging rule", default="request", required=True,
        groups="ideastone_erp.group_mvp_registrar,ideastone_erp.group_manager",
    )

    @api.constrains("campus_od_default_tokens")
    def _check_od_tokens(self):
        if any(company.campus_od_default_tokens < 0 for company in self):
            raise ValidationError(_("OD token allowance cannot be negative."))


class StudentODAllocation(models.Model):
    _inherit = "op.student.course"

    campus_od_tokens_override = fields.Integer(
        string="OD token allowance override",
        help="Set to zero to use the college's semester default.",
        groups="ideastone_erp.group_mvp_registrar,ideastone_erp.group_manager",
    )

    @api.constrains("campus_od_tokens_override")
    def _check_od_override(self):
        if any(enrolment.campus_od_tokens_override < 0 for enrolment in self):
            raise ValidationError(_("OD token allowance cannot be negative."))


class StudentOD(models.Model):
    _name = "campus.student.od"
    _description = "Student On Duty request"
    _inherit = "campus.record"
    _order = "id desc"

    student_id = fields.Many2one("op.student", required=True, readonly=True, ondelete="restrict", index=True)
    enrolment_id = fields.Many2one("op.student.course", required=True, readonly=True, ondelete="restrict")
    term_id = fields.Many2one("op.academic.term", required=True, readonly=True, ondelete="restrict", index=True)
    routing_id = fields.Many2one("campus.student.leave.routing", required=True, readonly=True, ondelete="restrict")
    mentor_id = fields.Many2one("res.users", required=True, readonly=True)
    hod_id = fields.Many2one("res.users", required=True, readonly=True)
    initiated_by_id = fields.Many2one("res.users", required=True, readonly=True)
    submission_key = fields.Char(required=True, readonly=True, copy=False)
    category = fields.Selection([("special", "Special OD"), ("general", "General OD")], required=True, readonly=True)
    purpose = fields.Text(required=True, readonly=True)
    venue = fields.Char(required=True, readonly=True)
    date_from = fields.Date(required=True, readonly=True)
    date_to = fields.Date(required=True, readonly=True)
    token_cost = fields.Integer(required=True, readonly=True)
    state = fields.Selection([
        ("pending_mentor", "Pending Mentor"), ("pending_hod", "Pending HOD"),
        ("withheld", "Withheld / Proof Pending"), ("proof_review", "Proof Under Review"),
        ("completed", "Completed"), ("rejected", "Rejected"),
        ("invalid", "Invalid / Proof Missing"), ("cancelled", "Cancelled"),
    ], required=True, default="pending_mentor", tracking=True, readonly=True)
    proof_requirements = fields.Text(readonly=True)
    proof_deadline = fields.Date(readonly=True)
    proof_file = fields.Binary(attachment=True, readonly=True)
    proof_filename = fields.Char(readonly=True)
    event_ids = fields.One2many("campus.student.od.event", "od_id", readonly=True)

    _sql_constraints = [
        ("od_submission_once", "unique(student_id,submission_key)", "This OD submission is already recorded."),
        ("od_dates_order", "CHECK(date_to >= date_from)", "OD end date must follow its start date."),
        ("od_positive_cost", "CHECK(token_cost > 0)", "OD token cost must be positive."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su or not self.env.context.get("campus_od_portal_submit"):
            raise AccessError(_("OD requests are created through the scoped student workflow."))
        if any(vals.get("state", "pending_mentor") != "pending_mentor" or vals.get("category") != "special" for vals in vals_list):
            raise AccessError(_("A student may initiate only a Special OD awaiting mentor review."))
        records = super().create(vals_list)
        records._record_event("Submitted for mentor review")
        return records

    def write(self, vals):
        allowed = {"state"} if self.env.context.get("campus_od_student_cancel") else (
            {"proof_file", "proof_filename", "state"} if self.env.context.get("campus_od_student_proof") else set()
        )
        if not self.env.su or not set(vals) <= allowed:
            raise AccessError(_("OD decisions and submitted details cannot be edited here."))
        for rec in self:
            if self.env.context.get("campus_od_student_cancel") and (rec.state != "pending_mentor" or vals != {"state": "cancelled"}):
                raise AccessError(_("Only a request awaiting mentor review may be cancelled by the student."))
            if self.env.context.get("campus_od_student_proof") and (rec.state != "withheld" or vals.get("state") != "proof_review"
                    or not vals.get("proof_file") or not rec.proof_deadline or fields.Date.context_today(rec) > rec.proof_deadline):
                raise AccessError(_("Proof can be submitted only while an approved Special OD is awaiting evidence."))
        result = super().write(vals)
        if "state" in vals:
            self._record_event("Cancelled by student" if vals["state"] == "cancelled" else "Proof submitted for HOD review")
        return result

    def unlink(self):
        raise AccessError(_("Retain OD requests and decisions for audit."))

    def _record_event(self, action):
        for rec in self:
            self.env["campus.student.od.event"].sudo().with_context(campus_od_event=True).create({
                "od_id": rec.id, "actor_id": self.env.uid, "action": action,
            })


class StudentODEvent(models.Model):
    _name = "campus.student.od.event"
    _description = "Immutable student OD history"
    _order = "id desc"

    od_id = fields.Many2one("campus.student.od", required=True, ondelete="restrict")
    actor_id = fields.Many2one("res.users", required=True, readonly=True)
    action = fields.Char(required=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su or not self.env.context.get("campus_od_event"):
            raise AccessError(_("OD history is recorded by the workflow."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("OD history cannot be changed."))

    def unlink(self):
        raise AccessError(_("OD history must be retained."))


class StudentODPortal(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _od_scope(self, student):
        return self._records("campus.student.od", [
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id),
        ], limit=5000, order="id desc")

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student, placement, _placements, _first, _last = self._portal_context(enrolment, date_from, date_to)
        route = self.env["campus.student.leave.routing"].sudo().search([
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("active", "=", True),
        ], limit=1)
        records = self._od_scope(student)
        current = records.filtered(lambda rec: rec.term_id == placement.academic_term_id) if placement and placement.academic_term_id else records.browse()
        limit = (placement.campus_od_tokens_override or student.company_id.campus_od_default_tokens) if placement else 0
        used = sum(current.filtered(lambda rec: rec.state == "completed").mapped("token_cost"))
        reserved = sum(current.filtered(lambda rec: rec.state in {"pending_mentor", "pending_hod", "withheld", "proof_review"}).mapped("token_cost"))
        states = dict(self.env["campus.student.od"]._fields["state"].selection)
        data["od"] = {
            "total": limit, "used": used, "reserved": reserved, "remaining": limit - used - reserved,
            "term": placement.academic_term_id.name if placement and placement.academic_term_id else "No semester assigned",
            "charge_rule": student.company_id.campus_od_token_rule,
            "can_submit": bool(placement and placement.state == "running" and placement.academic_term_id
                               and placement.academic_term_id.term_start_date and placement.academic_term_id.term_end_date
                               and route and limit > used + reserved),
            "route": bool(route), "submission_key": uuid.uuid4().hex,
            "rows": [{"id": rec.id, "name": rec.name, "category": dict(rec._fields["category"].selection)[rec.category],
                      "venue": rec.venue, "purpose": rec.purpose, "date_from": self._dates(rec.date_from),
                      "date_to": self._dates(rec.date_to), "tokens": rec.token_cost, "state": rec.state,
                      "status": states[rec.state], "can_cancel": rec.state == "pending_mentor",
                      "can_upload": rec.category == "special" and rec.state == "withheld" and rec.proof_deadline and fields.Date.context_today(self) <= rec.proof_deadline,
                      "proof_requirements": rec.proof_requirements or "", "proof_deadline": self._dates(rec.proof_deadline),
                      "events": [{"action": event.action, "by": event.actor_id.name, "at": self._dates(event.create_date)}
                                 for event in rec.event_ids.sorted("id")]} for rec in records],
        }
        index = next((index for index, item in enumerate(data["navigation"]) if item[0] == "requests"), len(data["navigation"]))
        data["navigation"].insert(index, ("on-duty", "On Duty Management", "briefcase"))
        return data

    @api.model
    def act(self, operation, payload=None):
        if operation not in {"od_submit", "od_cancel", "od_proof"}:
            return super().act(operation, payload)
        student = self._identity()
        if not isinstance(payload, dict):
            raise ValidationError(_("Invalid OD form submission."))
        self._serialize(student)
        if operation == "od_submit":
            return self._submit_od(student, payload)
        try:
            record_id = int(payload.get("od_id") or 0)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose a valid OD request.")) from exc
        rec = self._od_scope(student).filtered(lambda item: item.id == record_id)
        if not rec:
            raise AccessError(_("This OD request does not belong to your account."))
        rec._lock()
        if operation == "od_cancel":
            rec.with_context(campus_od_student_cancel=True).write({"state": "cancelled"})
        else:
            content, filename = self.env["campus.service.request"].sudo()._portal_upload(payload.get("file"), payload.get("filename"), 10)
            if not content:
                raise ValidationError(_("Attach the required proof file."))
            rec.with_context(campus_od_student_proof=True).write({"proof_file": content, "proof_filename": filename, "state": "proof_review"})
        return {"saved": True}

    def _submit_od(self, student, payload):
        key = str(payload.get("key") or "")
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValidationError(_("Reload the OD form before submitting."))
        existing = self._od_scope(student).filtered(lambda rec: rec.submission_key == key)
        if existing:
            return {"saved": True}
        if payload.get("category") != "special":
            raise AccessError(_("Students can submit Special OD requests. General OD is initiated by authorized staff."))
        student, placement, _placements, _first, _last = self._portal_context()
        if not placement or placement.state != "running" or not placement.academic_term_id:
            raise ValidationError(_("An active semester enrolment is required before requesting OD."))
        route = self.env["campus.student.leave.routing"].sudo().search([
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("active", "=", True),
        ], limit=1)
        if not route:
            raise ValidationError(_("Ask the college office to assign your mentor and HOD before requesting OD."))
        name, purpose, venue = (str(payload.get(field) or "").strip() for field in ("name", "purpose", "venue"))
        if not name or len(name) > 160 or not purpose or len(purpose) > 5000 or not venue or len(venue) > 200:
            raise ValidationError(_("Enter an event name, venue, and purpose within the displayed limits."))
        try:
            start = fields.Date.to_date(payload.get("od_date_from"))
            end = fields.Date.to_date(payload.get("od_date_to"))
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose valid OD dates.")) from exc
        term = placement.academic_term_id
        if not start or not end or end < start or not term.term_start_date or not term.term_end_date or start < term.term_start_date or end > term.term_end_date:
            raise ValidationError(_("OD dates must fall within your active semester."))
        if placement.campus_date_from and start < placement.campus_date_from or placement.campus_date_to and end > placement.campus_date_to:
            raise ValidationError(_("OD dates must fall within your active enrolment."))
        cost = 1 if student.company_id.campus_od_token_rule == "request" else (end - start).days + 1
        current = self._od_scope(student).filtered(lambda rec: rec.term_id == term)
        active = current.filtered(lambda rec: rec.state in {"pending_mentor", "pending_hod", "withheld", "proof_review", "completed"})
        if any(rec.date_from <= end and rec.date_to >= start for rec in active):
            raise ValidationError(_("An active OD already covers some of these dates."))
        limit = placement.campus_od_tokens_override or student.company_id.campus_od_default_tokens
        spent = sum(active.mapped("token_cost"))
        if limit <= 0 or cost > limit - spent:
            raise ValidationError(_("This request exceeds your remaining semester OD tokens."))
        self.env["campus.student.od"].sudo().with_context(campus_od_portal_submit=True).create({
            "name": name, "student_id": student.id, "enrolment_id": placement.id, "term_id": term.id,
            "company_id": student.company_id.id, "routing_id": route.id, "mentor_id": route.advisor_id.id,
            "hod_id": route.hod_id.id, "initiated_by_id": self.env.uid, "submission_key": key,
            "category": "special", "purpose": purpose, "venue": venue, "date_from": start,
            "date_to": end, "token_cost": cost,
        })
        return {"saved": True}
