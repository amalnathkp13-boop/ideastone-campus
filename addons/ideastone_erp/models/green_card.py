"""Green Card projections use the existing assigned student-leave approval chain."""
import re

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

from .student_leave import StudentLeave


class GreenCardLeave(models.Model):
    _inherit = "campus.student.leave"

    green_card = fields.Boolean(index=True, copy=False)
    green_key = fields.Char(copy=False, index=True)
    green_type = fields.Selection([("announced", "Announced"), ("unannounced", "Unannounced")], copy=False)
    green_from_session = fields.Selection([("FN", "Morning (FN)"), ("AN", "Afternoon (AN)")], default="FN")
    green_to_session = fields.Selection([("FN", "Morning (FN)"), ("AN", "Afternoon (AN)")], default="AN")
    green_hold = fields.Selection([("proof", "Proof requested"), ("return", "Returned for clarification")], copy=False)
    green_hold_stage = fields.Selection([("advisor", "Mentor"), ("hod", "HOD")], copy=False)
    green_proof = fields.Binary(attachment=True, copy=False)
    green_proof_name = fields.Char(copy=False)
    green_parent_confirmed = fields.Boolean(copy=False)
    green_mentor_at = fields.Datetime(copy=False)
    green_hod_at = fields.Datetime(copy=False)
    green_history = fields.Json(default=list, copy=False)

    _sql_constraints = [("green_submission_unique", "unique(student_id,green_key)", "This Green Card is already submitted.")]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(any(k.startswith("green_") for k in v) for v in vals_list):
            raise AccessError(_("Use the authenticated Green Card workflow."))
        return super().create(vals_list)

    def _green_values(self, values):
        # Private workflow-only write after identity, assignment and row-lock checks.
        return super(StudentLeave, self).write(values)

    def _green_event(self, message, note=""):
        self.ensure_one()
        event = {"action": message, "note": note, "by": self.env.user.name, "at": str(fields.Datetime.now())}
        self._green_values({"green_history": (self.green_history or []) + [event]})
        self.env["campus.mvp.audit"]._log(self, "Green Card: " + message, note)

    def write(self, values):
        if any(k.startswith("green_") for k in values):
            raise AccessError(_("Green Card evidence is maintained by the verified workflow."))
        previous = {r.id: r.state for r in self.filtered("green_card")} if "state" in values else {}
        for rec in self.filtered("green_card") if "state" in values else []:
            if rec.green_hold and values["state"] != "rejected":
                raise ValidationError(_("Resolve the requested proof or clarification before approving."))
            if rec.state == "hod":
                self.env["campus.green.card.ui"]._review_record(rec.id)
        result = super().write(values)
        for rec in self.filtered("green_card") if previous else []:
            if previous[rec.id] == "advisor" and rec.state == "hod":
                rec._green_values({"green_mentor_at": fields.Datetime.now()})
                rec._green_event("Mentor approved and forwarded to HOD")
            elif previous[rec.id] == "hod" and rec.state in {"principal", "approved"}:
                rec._green_values({"green_hod_at": fields.Datetime.now()})
                rec._green_event("HOD approved" + ("; principal review required" if rec.state == "principal" else " Green Card"))
            elif rec.state == "rejected":
                rec._green_values({"green_hold": False, "green_hold_stage": False})
                rec._green_event("Request rejected", self.env.context.get("green_decision_note", ""))
            elif rec.state == "approved":
                rec._green_event("Final approval recorded")
        return result


class GreenCardStudentNavigation(models.AbstractModel):
    _inherit = "campus.student.portal"

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        index = next((i for i, item in enumerate(data["navigation"]) if item[0] == "attendance"), len(data["navigation"])) + 1
        data["navigation"].insert(index, ("green-card", "Green Card", "id-card-o"))
        return data


class GreenCardStaffNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _faculty_modules(self, visible, faculty, pages):
        modules = super()._faculty_modules(visible, faculty, pages)
        service = self.env["campus.green.card.ui"]
        try:
            role = service._role()
        except AccessError:
            return [m for m in modules if m["key"] != "green-card"]
        action = self.env.ref("ideastone_erp.action_green_card_" + role)
        attendance = next((module for module in modules if module["key"] == "attendance"), None)
        if attendance is None:
            attendance = {"key": "attendance", "label": "Attendance", "icon": "calendar-check-o", "items": []}
            modules.insert(next((i for i, row in enumerate(modules) if row["key"] == "od"), len(modules)), attendance)
        attendance["label"] = "Attendance"
        attendance["items"].append({"label": "Green Card", "action": action.get_external_id()[action.id], "action_id": action.id})
        return modules

    def _client_action_models(self):
        return dict(super()._client_action_models(), action_green_card_mentor="campus.student.leave", action_green_card_hod="campus.student.leave")


class GreenCardUI(models.AbstractModel):
    _name = "campus.green.card.ui"
    _description = "Authenticated student, assigned mentor and assigned HOD Green Cards"

    def _role(self):
        user = self.env.user
        if user.has_group("base.group_portal") and not user.has_group("base.group_user"):
            if user.child_ids:
                raise AccessError(_("Green Cards are available in the student's own login."))
            self.env["campus.student.portal"]._identity()
            return "student"
        if not user.active or user.has_group("base.group_system") or user.has_group("ideastone_erp.group_mvp_owner"):
            raise AccessError(_("Use your assigned student, mentor or HOD login."))
        if user.has_group("ideastone_erp.group_od_hod_approver"):
            if not user.dept_id:
                raise AccessError(_("The college must link a department to this HOD account."))
            return "hod"
        if user.has_group("openeducat_core.group_op_faculty"):
            return "mentor"
        raise AccessError(_("Use your assigned student, mentor or HOD login."))

    def _scope(self):
        role = self._role()
        source = self.env["campus.student.leave"].sudo()
        if role == "student":
            student = self.env["campus.student.portal"]._identity()
            domain = [("student_id", "=", student.id), ("company_id", "=", student.company_id.id)]
        else:
            routes = self.env["campus.hod.od.ui"]._routes() if role == "hod" else self.env["campus.staff.od.ui"]._assigned_routes()
            domain = [("routing_id", "in", routes.ids), ("company_id", "=", self.env.company.id)]
            if role == "hod":
                domain.append(("green_mentor_at", "!=", False))
        domain.append(("green_card", "=", True))
        if source.search_count(domain) > 5000:
            raise ValidationError(_("This Green Card register exceeds the supported 5,000 requests. Contact the college office."))
        return source.search(domain, order="id desc")

    def _record(self, record_id):
        if type(record_id) is not int or not 0 < record_id <= 2147483647:
            raise ValidationError(_("Choose a valid Green Card."))
        record = self._scope().filtered(lambda row: row.id == record_id)
        if not record:
            raise AccessError(_("This Green Card is not available in your assigned portal."))
        return record.with_user(self.env.user).sudo()

    def _review_record(self, record_id):
        role = self._role()
        if role == "student":
            raise AccessError(_("Students cannot approve Green Cards."))
        record = self._record(record_id)
        stage = "hod" if role == "hod" else "advisor"
        if record.state != stage or record[stage + "_id"].id != self.env.uid:
            raise AccessError(_("Only the currently assigned reviewer can decide this stage."))
        return record

    def _row(self, record):
        placement = record.student_id.course_detail_ids.filtered(lambda p: p.company_id == record.company_id and p.state == "running")[:1]
        stage = "mentor" if record.state == "advisor" else record.state
        state = stage + "_" + record.green_hold if record.green_hold else stage
        slots = (record.deadline - record.date).days * 2 + (record.green_to_session == "AN") - (record.green_from_session == "AN") + 1
        return {"id": record.id, "reference": f"GC-{record.id:06d}", "student": record.student_id.name,
                "register": record.student_id.gr_no or "—", "class": placement.batch_id.name or "—",
                "department": placement.course_id.department_id.name or "—", "type": record.green_type,
                "from": str(record.date), "to": str(record.deadline), "fromSession": record.green_from_session,
                "toSession": record.green_to_session, "days": slots / 2, "reason": record.reason,
                "state": state, "stage": record.state, "parent": record.green_parent_confirmed,
                "support": record.filename or "", "proof": record.green_proof_name or "",
                "mentorApproved": bool(record.green_mentor_at), "mentor": record.advisor_id.name,
                "hod": record.hod_id.name, "mentorAt": str(record.green_mentor_at or ""),
                "hodAt": str(record.green_hod_at or ""), "principal": bool(record.principal_id),
                "history": record.green_history or []}

    @api.model
    def get_workspace(self, expected_role=None):
        role = self._role()
        if expected_role and role != expected_role:
            raise AccessError(_("Open the Green Card page for your own login."))
        records = self._scope()
        student = self.env["campus.student.portal"]._identity() if role == "student" else None
        route = self.env["campus.student.leave.routing"].sudo().search([("student_id", "=", student.id),
            ("company_id", "=", student.company_id.id), ("active", "=", True)], limit=1) if student else None
        return {"role": role, "name": self.env.user.name, "today": str(fields.Date.context_today(self)),
                "route": bool(route) if student else True, "rows": [self._row(r) for r in records]}

    def _upload(self, payload):
        name = payload.get("filename") or ""
        content = payload.get("file")
        if content and (not isinstance(name, str) or not name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg"))):
            raise ValidationError(_("Use a PDF, PNG or JPEG file, up to 2 MB."))
        return self.env["campus.service.request"]._portal_upload(content, name)

    @api.model
    def submit(self, payload):
        if self._role() != "student" or not isinstance(payload, dict):
            raise AccessError(_("Only a linked student can submit this form."))
        student = self.env["campus.student.portal"]._identity()
        self.env["campus.student.portal"]._serialize(student)
        key = payload.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{32}", key):
            raise ValidationError(_("Refresh the form before submitting."))
        source = self.env["campus.student.leave"].sudo()
        duplicate = source.search([("student_id", "=", student.id), ("green_key", "=", key)], limit=1)
        if duplicate:
            return duplicate.id
        route = self.env["campus.student.leave.routing"].sudo().search([("student_id", "=", student.id),
            ("company_id", "=", student.company_id.id), ("active", "=", True)], limit=1)
        if not route:
            raise ValidationError(_("Ask the college to configure your mentor and HOD leave route first."))
        try:
            start, end = fields.Date.to_date(payload.get("from")), fields.Date.to_date(payload.get("to"))
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Enter valid leave dates.")) from exc
        first, last = payload.get("fromSession"), payload.get("toSession")
        today, kind = fields.Date.context_today(self), payload.get("type")
        reason = payload.get("reason")
        if not start or not end or start > end or (end - start).days > 366 or first not in {"FN", "AN"} or last not in {"FN", "AN"} or (start == end and first == "AN" and last == "FN"):
            raise ValidationError(_("Choose an ordered leave period and valid sessions, within one year."))
        if kind not in {"announced", "unannounced"} or (kind == "announced" and start < today) or (kind == "unannounced" and end > today):
            raise ValidationError(_("Announced leave starts today or later; unannounced leave covers an existing absence."))
        if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 500:
            raise ValidationError(_("Explain the leave in 8 to 500 characters."))
        a, b = start.toordinal() * 2 + (first == "AN"), end.toordinal() * 2 + (last == "AN")
        for rec in source.search([("student_id", "=", student.id), ("green_card", "=", True), ("state", "!=", "rejected"),
                                  ("date", "<=", end), ("deadline", ">=", start)]):
            if a <= rec.deadline.toordinal() * 2 + (rec.green_to_session == "AN") and b >= rec.date.toordinal() * 2 + (rec.green_from_session == "AN"):
                raise ValidationError(_("An active Green Card already covers one of these sessions."))
        content, filename = self._upload(payload)
        record = source.with_user(route.advisor_id).sudo().with_company(student.company_id).create({
            "name": "Green Card — " + student.name, "routing_id": route.id, "date": start, "deadline": end,
            "reason": reason.strip(), "kind": "mentoring", "green_card": True, "green_key": key,
            "green_type": kind, "green_from_session": first, "green_to_session": last,
            "document": content, "filename": filename})
        record.action_submit()
        record.with_user(self.env.user).sudo()._green_event("Student submitted for mentor review")
        return record.id

    @api.model
    def respond(self, record_id, payload):
        if self._role() != "student" or not isinstance(payload, dict):
            raise AccessError(_("Only the student can respond to this request."))
        record = self._record(record_id)
        record._lock()
        if record.state not in {"advisor", "hod"} or not record.green_hold:
            raise ValidationError(_("This application does not currently require a response."))
        if record.green_hold == "proof":
            content, filename = self._upload(payload)
            if not content:
                raise ValidationError(_("Upload the requested supporting document."))
            record._green_values({"green_proof": content, "green_proof_name": filename, "green_hold": False, "green_hold_stage": False})
            record._green_event("Student provided requested proof", filename)
        else:
            reason = payload.get("reason")
            if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 500:
                raise ValidationError(_("Enter a corrected explanation in 8 to 500 characters."))
            record._green_values({"reason": reason.strip(), "state": "advisor", "green_hold": False,
                "green_hold_stage": False, "green_mentor_at": False, "green_hod_at": False})
            record._green_event("Student corrected and resubmitted to mentor")
        return True

    @api.model
    def review(self, record_id, action, note="", verification="none"):
        record = self._review_record(record_id)
        record._lock()
        record = self._review_record(record_id)  # Recheck the stage after a concurrent decision.
        if action not in {"approve", "proof", "parent", "return", "reject"} or verification not in {"none", "parent"}:
            raise ValidationError(_("Choose a valid review action."))
        if not isinstance(note, str) or len(note) > 500 or (action in {"parent", "return", "reject", "proof"} and not note.strip()):
            raise ValidationError(_("Enter a clear review or verification note, up to 500 characters."))
        note = note.strip()
        if action == "parent" or verification == "parent":
            if not note:
                raise ValidationError(_("Record the parent contact outcome."))
            record._green_values({"green_parent_confirmed": True})
            record._green_event("Parent contact confirmed", note)
        if action in {"proof", "return"}:
            if record.green_hold:
                raise ValidationError(_("A student response is already outstanding."))
            record._green_values({"green_hold": action, "green_hold_stage": record.state,
                                  **({"green_proof": False, "green_proof_name": False} if action == "proof" else {})})
            record._green_event("Supporting proof requested" if action == "proof" else "Returned for clarification", note)
        elif action == "reject":
            record.decision_reason = note
            record.with_context(green_decision_note=note).action_reject()
        elif action == "approve":
            if record.green_hold:
                raise ValidationError(_("Wait for the student's requested proof or correction."))
            if note:
                record._green_event("Review remarks recorded", note)
            record.action_approve()
        return True
