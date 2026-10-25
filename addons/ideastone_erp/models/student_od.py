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
    category = fields.Selection([
        ("undetermined", "To be determined by Mentor / HOD"),
        ("special", "Special OD"), ("general", "General OD"),
    ], required=True, readonly=True, default="undetermined")
    purpose = fields.Text(required=True, readonly=True)
    venue = fields.Char(required=True, readonly=True)
    date_from = fields.Date(required=True, readonly=True)
    date_to = fields.Date(required=True, readonly=True)
    session_from = fields.Selection([("forenoon", "Forenoon"), ("afternoon", "Afternoon")], required=True, readonly=True)
    session_to = fields.Selection([("forenoon", "Forenoon"), ("afternoon", "Afternoon")], required=True, readonly=True)
    token_cost = fields.Integer(required=True, readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("pending_mentor", "Pending Mentor"), ("pending_hod", "Pending HOD"),
        ("withheld", "Withheld / Proof Pending"), ("proof_review", "Proof Under Review"),
        ("completed", "Completed"), ("rejected", "Rejected"), ("returned", "Returned to Student"),
        ("invalid", "Invalid / Proof Missing"), ("cancelled", "Cancelled"),
    ], required=True, default="pending_mentor", tracking=True, readonly=True)
    proof_requirements = fields.Text(readonly=True)
    proof_deadline = fields.Date(readonly=True)
    proof_file = fields.Binary(attachment=True, readonly=True)
    proof_filename = fields.Char(readonly=True)
    mentor_note = fields.Text(readonly=True)
    mentor_reviewed_by_id = fields.Many2one("res.users", readonly=True)
    mentor_reviewed_at = fields.Datetime(readonly=True)
    hod_note = fields.Text(readonly=True)
    hod_reviewed_by_id = fields.Many2one("res.users", readonly=True)
    hod_reviewed_at = fields.Datetime(readonly=True)
    support_file = fields.Binary(attachment=True, readonly=True)
    support_filename = fields.Char(readonly=True)
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
        if any(vals.get("state", "pending_mentor") not in {"draft", "pending_mentor"}
               or vals.get("category") != "undetermined" for vals in vals_list):
            raise AccessError(_("Student OD requests must start as drafts or await mentor review."))
        records = super().create(vals_list)
        for record in records:
            record._record_event("Draft saved" if record.state == "draft" else "Submitted for mentor review")
        return records

    def write(self, vals):
        allowed = ({"state", "mentor_note", "mentor_reviewed_by_id", "mentor_reviewed_at"}
                   if self.env.context.get("campus_od_mentor_review") else
                   {"state", "category", "proof_requirements", "proof_deadline", "hod_note",
                    "hod_reviewed_by_id", "hod_reviewed_at"}
                   if self.env.context.get("campus_od_hod_review") else
                   {"state"} if self.env.context.get("campus_od_proof_expiry") else
                   {"state"} if self.env.context.get("campus_od_student_cancel")
                   or self.env.context.get("campus_od_student_activate") else
                   {"proof_file", "proof_filename", "state"} if self.env.context.get("campus_od_student_proof") else set())
        if not self.env.su or not set(vals) <= allowed:
            raise AccessError(_("OD decisions and submitted details cannot be edited here."))
        for rec in self:
            if self.env.context.get("campus_od_mentor_review") and (
                rec.state != "pending_mentor" or rec.mentor_id != self.env.user
                or rec.routing_id.advisor_id != self.env.user or not rec.routing_id.active
                or rec.company_id != self.env.company or vals.get("state") not in {"pending_hod", "returned"}
                or vals.get("mentor_reviewed_by_id") != self.env.uid or not vals.get("mentor_reviewed_at")
                or not self.env.user.has_group("openeducat_core.group_op_faculty")
            ):
                raise AccessError(_("Only the assigned mentor may decide a pending OD request."))
            if self.env.context.get("campus_od_hod_review"):
                if (not self.env.user.has_group("ideastone_erp.group_od_hod_approver")
                        or rec.hod_id != self.env.user or rec.routing_id.hod_id != self.env.user
                        or not rec.routing_id.active or rec.company_id != self.env.company
                        or vals.get("hod_reviewed_by_id") != self.env.uid or not vals.get("hod_reviewed_at")):
                    raise AccessError(_("Only the assigned HOD may decide this OD request."))
                next_state = vals.get("state")
                if rec.state == "pending_hod":
                    if next_state not in {"completed", "withheld", "rejected"}:
                        raise AccessError(_("This OD is not awaiting a valid HOD decision."))
                    if next_state == "completed" and vals.get("category") != "general":
                        raise AccessError(_("General OD must be confirmed without proof."))
                    if next_state == "withheld" and (vals.get("category") != "special"
                            or not vals.get("proof_requirements") or not vals.get("proof_deadline")):
                        raise AccessError(_("Special OD requires proof instructions and a separate deadline."))
                elif rec.state == "withheld":
                    if next_state != "withheld" or not vals.get("proof_requirements") or not vals.get("proof_deadline"):
                        raise AccessError(_("Only proof instructions may be updated while evidence is pending."))
                elif rec.state == "proof_review":
                    if next_state not in {"completed", "withheld", "invalid"} or not rec.proof_file:
                        raise AccessError(_("Only submitted proof may be reviewed."))
                else:
                    raise AccessError(_("This request is not awaiting HOD action."))
            if self.env.context.get("campus_od_proof_expiry") and (
                rec.state != "withheld" or vals != {"state": "invalid"}
                or not rec.proof_deadline or rec.proof_deadline >= fields.Date.context_today(rec)
            ):
                raise AccessError(_("Only overdue proof requests may expire."))
            if self.env.context.get("campus_od_student_cancel") and (rec.state != "pending_mentor" or vals != {"state": "cancelled"}):
                raise AccessError(_("Only a request awaiting mentor review may be cancelled by the student."))
            if self.env.context.get("campus_od_student_activate") and (rec.state not in {"draft", "returned"} or vals != {"state": "pending_mentor"}):
                raise AccessError(_("Only a saved draft or returned request may be submitted for mentor review."))
            if self.env.context.get("campus_od_student_proof") and (rec.category != "special" or rec.state != "withheld" or vals.get("state") != "proof_review"
                    or not vals.get("proof_file") or not rec.proof_deadline or fields.Date.context_today(rec) > rec.proof_deadline):
                raise AccessError(_("Proof can be submitted only while an approved Special OD is awaiting evidence."))
        result = super().write(vals)
        if "state" in vals and not (self.env.context.get("campus_od_mentor_review")
                                     or self.env.context.get("campus_od_hod_review")
                                     or self.env.context.get("campus_od_proof_expiry")):
            self._record_event({"cancelled": "Cancelled by student", "pending_mentor": "Submitted for mentor review",
                                "proof_review": "Proof submitted for HOD review"}[vals["state"]])
        return result

    @api.model
    def _cron_expire_proof(self):
        today = fields.Date.context_today(self)
        records = self.sudo().search([("state", "=", "withheld"), ("proof_deadline", "<", today)])
        for record in records:
            record._lock()
            if record.state == "withheld" and record.proof_deadline < today:
                record.with_context(campus_od_proof_expiry=True).write({"state": "invalid"})
                record._record_event("Proof deadline passed; OD invalidated")

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
        pending = len(current.filtered(lambda rec: rec.state in {"pending_mentor", "pending_hod", "withheld", "proof_review"}))
        states = dict(self.env["campus.student.od"]._fields["state"].selection)
        data["od"] = {
            "total": limit, "used": used, "reserved": reserved, "pending": pending,
            "remaining": limit - used - reserved,
            "term": placement.academic_term_id.name if placement and placement.academic_term_id else "No semester assigned",
            "charge_rule": student.company_id.campus_od_token_rule,
            "can_submit": bool(placement and placement.state == "running" and placement.academic_term_id
                               and placement.academic_term_id.term_start_date and placement.academic_term_id.term_end_date
                               and route and limit > used + reserved),
            "route": bool(route), "submission_key": uuid.uuid4().hex,
            "rows": [{"id": rec.id, "reference": "OD%07d" % rec.id, "name": rec.name,
                      "category": dict(rec._fields["category"].selection)[rec.category],
                      "venue": rec.venue, "purpose": rec.purpose, "date_from": self._dates(rec.date_from),
                      "date_to": self._dates(rec.date_to), "tokens": rec.token_cost, "state": rec.state,
                      "status": states[rec.state], "can_cancel": rec.state == "pending_mentor",
                      "can_submit_draft": rec.state in {"draft", "returned"}, "has_support": bool(rec.support_file),
                      "mentor_note": rec.mentor_note or "",
                      "can_upload": rec.category == "special" and rec.state == "withheld" and rec.proof_deadline and fields.Date.context_today(self) <= rec.proof_deadline,
                      "proof_requirements": rec.proof_requirements or "", "proof_deadline": self._dates(rec.proof_deadline),
                      "events": [{"action": event.action, "by": event.actor_id.name, "at": self._dates(event.create_date)}
                                 for event in rec.event_ids.sorted("id")]} for rec in records],
        }
        data["od"]["actions"] = [
            {"id": row["id"], "reference": row["reference"], "name": row["name"],
             "state": row["state"], "deadline": row["proof_deadline"],
             "title": {"draft": "Draft ready to submit", "returned": "Mentor requested changes", "pending_mentor": "Mentor review pending",
                       "pending_hod": "HOD review pending", "withheld": "Proof requested",
                       "proof_review": "Proof under review"}[row["state"]]}
            for row in data["od"]["rows"]
            if row["state"] in {"draft", "returned", "pending_mentor", "pending_hod", "withheld", "proof_review"}
        ][:4]
        data["od"]["proof_ready"] = any(row["can_upload"] for row in data["od"]["rows"])
        index = next((index for index, item in enumerate(data["navigation"]) if item[0] == "requests"), len(data["navigation"]))
        data["navigation"].insert(index, ("on-duty", "OD Management", "briefcase"))
        return data

    @api.model
    def act(self, operation, payload=None):
        if operation not in {"od_submit", "od_draft", "od_activate", "od_cancel", "od_proof"}:
            return super().act(operation, payload)
        student = self._identity()
        if not isinstance(payload, dict):
            raise ValidationError(_("Invalid OD form submission."))
        self._serialize(student)
        if operation in {"od_submit", "od_draft"}:
            return self._submit_od(student, payload, draft=operation == "od_draft")
        try:
            record_id = int(payload.get("od_id") or 0)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose a valid OD request.")) from exc
        rec = self._od_scope(student).filtered(lambda item: item.id == record_id)
        if not rec:
            raise AccessError(_("This OD request does not belong to your account."))
        rec._lock()
        if operation == "od_activate":
            placement = rec.enrolment_id
            if placement.state != "running" or rec.term_id != placement.academic_term_id or not rec.routing_id.active or rec.mentor_id != rec.routing_id.advisor_id:
                raise ValidationError(_("The saved draft needs an active semester and approval route before submission."))
            self._check_od_allowance(student, placement, rec.date_from, rec.date_to, rec.token_cost, rec.id)
            rec.with_context(campus_od_student_activate=True).write({"state": "pending_mentor"})
        elif operation == "od_cancel":
            rec.with_context(campus_od_student_cancel=True).write({"state": "cancelled"})
        else:
            content, filename = self.env["campus.service.request"].sudo()._portal_upload(payload.get("file"), payload.get("filename"), 10)
            if not content:
                raise ValidationError(_("Attach the required proof file."))
            rec.with_context(campus_od_student_proof=True).write({"proof_file": content, "proof_filename": filename, "state": "proof_review"})
        return {"saved": True}

    def _check_od_allowance(self, student, placement, start, end, cost, ignore_id=0):
        current = self._od_scope(student).filtered(lambda rec: rec.term_id == placement.academic_term_id)
        active = current.filtered(lambda rec: rec.id != ignore_id and rec.state in {
            "pending_mentor", "pending_hod", "withheld", "proof_review", "completed",
        })
        if any(rec.date_from <= end and rec.date_to >= start for rec in active):
            raise ValidationError(_("An active OD already covers some of these dates."))
        limit = placement.campus_od_tokens_override or student.company_id.campus_od_default_tokens
        if limit <= 0 or cost > limit - sum(active.mapped("token_cost")):
            raise ValidationError(_("This request exceeds your remaining semester OD tokens."))

    def _submit_od(self, student, payload, draft=False):
        key = str(payload.get("key") or "")
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValidationError(_("Reload the OD form before submitting."))
        existing = self._od_scope(student).filtered(lambda rec: rec.submission_key == key)
        if existing:
            return {"saved": True}
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
        session_from = payload.get("od_from_session")
        session_to = payload.get("od_to_session")
        if session_from not in {"forenoon", "afternoon"} or session_to not in {"forenoon", "afternoon"}:
            raise ValidationError(_("Choose a forenoon or afternoon session for both dates."))
        term = placement.academic_term_id
        if not start or not end or end < start or not term.term_start_date or not term.term_end_date or start < term.term_start_date or end > term.term_end_date:
            raise ValidationError(_("OD dates must fall within your active semester."))
        if start == end and session_from == "afternoon" and session_to == "forenoon":
            raise ValidationError(_("On the same date, the end session cannot precede the start session."))
        if placement.campus_date_from and start < placement.campus_date_from or placement.campus_date_to and end > placement.campus_date_to:
            raise ValidationError(_("OD dates must fall within your active enrolment."))
        cost = 1 if student.company_id.campus_od_token_rule == "request" else (end - start).days + 1
        if not draft:
            self._check_od_allowance(student, placement, start, end, cost)
        support = {}
        if payload.get("file"):
            content, filename = self.env["campus.service.request"].sudo()._portal_upload(
                payload.get("file"), payload.get("filename"), 10,
            )
            support = {"support_file": content, "support_filename": filename}
        self.env["campus.student.od"].sudo().with_context(campus_od_portal_submit=True).create({
            "name": name, "student_id": student.id, "enrolment_id": placement.id, "term_id": term.id,
            "company_id": student.company_id.id, "routing_id": route.id, "mentor_id": route.advisor_id.id,
            "hod_id": route.hod_id.id, "initiated_by_id": self.env.uid, "submission_key": key,
            "category": "undetermined", "purpose": purpose, "venue": venue, "date_from": start,
            "date_to": end, "session_from": session_from, "session_to": session_to,
            "token_cost": cost, "state": "draft" if draft else "pending_mentor",
            **support,
        })
        return {"saved": True}
