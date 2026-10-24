import mimetypes
from collections import Counter
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class HodODUI(models.AbstractModel):
    _name = "campus.hod.od.ui"
    _description = "Assigned HOD On Duty workspace"

    def _routes(self):
        user = self.env.user
        if not user.active or not user.has_group("ideastone_erp.group_od_hod_approver"):
            raise AccessError(_("This workspace requires an assigned OD HOD account."))
        if not user.dept_id:
            raise AccessError(_("Assign a department to this HOD account before reviewing OD requests."))
        routes = self.env["campus.student.leave.routing"].sudo().search([
            ("hod_id", "=", user.id), ("company_id", "=", self.env.company.id), ("active", "=", True),
        ])
        return routes.filtered(lambda route: any(
            placement.state == "running" and placement.company_id == self.env.company
            and placement.course_id.department_id == user.dept_id
            for placement in route.student_id.course_detail_ids
        ))

    @api.model
    def get_proof(self, request_id):
        routes = self._routes()
        try:
            request_id = int(request_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid OD request.")) from exc
        record = self.env["campus.student.od"].sudo().search([
            ("id", "=", request_id), ("hod_id", "=", self.env.uid),
            ("routing_id", "in", routes.ids), ("company_id", "=", self.env.company.id),
            ("state", "in", ["proof_review", "completed"]),
        ], limit=1)
        if not record or not record.proof_file:
            raise AccessError(_("No submitted proof is available for this assigned request."))
        filename = record.proof_filename or "od-proof"
        return {"filename": filename, "mimetype": mimetypes.guess_type(filename)[0] or "application/octet-stream",
                "content": record.proof_file.decode() if isinstance(record.proof_file, bytes) else record.proof_file}

    @api.model
    def get_page_data(self, class_key=None):
        routes = self._routes()
        today = fields.Date.context_today(self)
        term = self.env["op.academic.term"].sudo().search([
            ("company_id", "=", self.env.company.id),
            ("term_start_date", "<=", today), ("term_end_date", ">=", today),
        ], order="term_start_date desc, id desc", limit=1)
        classes = {}
        for route in routes:
            for placement in route.student_id.course_detail_ids.filtered(
                    lambda item: item.company_id == self.env.company and item.state == "running"
                    and (not term or item.academic_term_id == term)):
                key = f"{placement.batch_id.id}:{placement.academic_term_id.id}"
                classes[key] = placement.batch_id.name or _("Unassigned class")
        if class_key and class_key not in classes:
            raise AccessError(_("This class is not assigned to your HOD account."))
        records = self.env["campus.student.od"].sudo().search([
            ("hod_id", "=", self.env.uid), ("routing_id", "in", routes.ids),
            ("company_id", "=", self.env.company.id),
        ] + ([("term_id", "=", term.id)] if term else []), order="create_date desc, id desc", limit=1000)
        if class_key:
            batch_id, term_id = (int(value) for value in class_key.split(":"))
            records = records.filtered(lambda rec: rec.enrolment_id.batch_id.id == batch_id and rec.term_id.id == term_id)
        status = dict(self.env["campus.student.od"]._fields["state"].selection)
        rows = [{
            "id": rec.id, "reference": "OD%07d" % rec.id, "student": rec.student_id.name,
            "student_id": rec.student_id.id, "name": rec.name, "purpose": rec.purpose,
            "venue": rec.venue, "date_from": fields.Date.to_string(rec.date_from),
            "date_to": fields.Date.to_string(rec.date_to), "created": fields.Datetime.to_string(rec.create_date),
            "state": rec.state, "status": status[rec.state], "category": rec.category,
            "proof_requirements": rec.proof_requirements or "",
            "proof_deadline": fields.Date.to_string(rec.proof_deadline) if rec.proof_deadline else "",
            "has_proof": bool(rec.proof_file), "hod_note": rec.hod_note or "",
            "can_decide": rec.state == "pending_hod", "can_request_proof": rec.state == "withheld",
            "can_verify": rec.state == "proof_review",
            "events": [{"action": event.action, "by": event.actor_id.name,
                        "at": fields.Datetime.to_string(event.create_date)}
                       for event in rec.event_ids.sorted("id")],
        } for rec in records]
        active = [row for row in rows if row["state"] not in {"draft", "returned", "rejected", "invalid", "cancelled"}]
        counts = Counter(row["student_id"] for row in active)
        overlapping = {first["student_id"] for index, first in enumerate(active) for second in active[index + 1:]
                       if first["student_id"] == second["student_id"]
                       and first["date_from"] <= second["date_to"] and second["date_from"] <= first["date_to"]}
        upcoming = Counter(row["student_id"] for row in active if row["date_from"] > str(today))
        actions = [row for row in rows if row["state"] in {"pending_hod", "withheld", "proof_review"}]
        actions.sort(key=lambda row: (row["proof_deadline"] or row["date_from"], row["id"]))
        week_start = today - timedelta(days=today.weekday())
        week_activity = [{"label": day.strftime("%a"), "sub": day.strftime("%d %b"),
                          "count": sum(row["created"][:10] == str(day) for row in rows)}
                         for day in (week_start + timedelta(days=offset) for offset in range(7))]
        month_activity = [{"label": _("Week %s") % (index + 1), "sub": start.strftime("%d %b"),
                           "count": sum(str(start) <= row["created"][:10] <= str(start + timedelta(days=6)) for row in rows)}
                          for index, start in enumerate(week_start - timedelta(days=offset * 7) for offset in (3, 2, 1, 0))]
        return {
            "role": "hod", "hod_name": self.env.user.name, "company_name": self.env.company.name,
            "semester": term.name or _("Current semester"), "class_key": class_key or "",
            "classes": [{"key": key, "label": name} for key, name in sorted(classes.items(), key=lambda item: item[1])],
            "rows": rows, "approved_rows": [row for row in rows if row["state"] == "completed"],
            "withheld_rows": [row for row in rows if row["state"] in {"withheld", "proof_review"}],
            "total": len(rows), "pending": sum(row["state"] in {"pending_hod", "proof_review"} for row in rows),
            "approved": sum(row["state"] == "completed" for row in rows),
            "rejected": sum(row["state"] in {"rejected", "invalid"} for row in rows),
            "students_on_od": len({row["student_id"] for row in rows if row["state"] == "completed"
                                   and row["date_from"] <= str(today) <= row["date_to"]}),
            "repeated_students": sum(count > 1 for count in counts.values()),
            "overlapping_students": len(overlapping),
            "upcoming_students": sum(count > 1 for count in upcoming.values()),
            "awaiting_proof": sum(row["state"] == "withheld" for row in rows),
            "actions": actions[:4], "week_activity": week_activity, "month_activity": month_activity,
        }

    @api.model
    def decide(self, request_id, decision, category="", note="", proof_requirements="", proof_deadline=""):
        routes = self._routes()
        if decision not in {"approve", "reject", "request_proof", "accept_proof", "return_proof"}:
            raise ValidationError(_("Choose a valid HOD decision."))
        try:
            request_id = int(request_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid OD request.")) from exc
        note, proof_requirements = str(note or "").strip(), str(proof_requirements or "").strip()
        if len(note) > 500 or len(proof_requirements) > 1000:
            raise ValidationError(_("Keep the decision note and proof requirements concise."))
        record = self.env["campus.student.od"].sudo().search([
            ("id", "=", request_id), ("hod_id", "=", self.env.uid),
            ("routing_id", "in", routes.ids), ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not record:
            raise AccessError(_("This OD request is not assigned to your HOD account."))
        record._lock()
        values = {"hod_reviewed_by_id": self.env.uid, "hod_reviewed_at": fields.Datetime.now()}
        if decision in {"approve", "reject"}:
            if record.state != "pending_hod" or not record.mentor_reviewed_by_id:
                raise ValidationError(_("Mentor authorization must precede the HOD decision."))
            if decision == "reject":
                if not note:
                    raise ValidationError(_("Give a reason for rejecting this request."))
                values.update(state="rejected", hod_note=note)
            elif category == "general":
                values.update(state="completed", category="general", hod_note=note)
            elif category == "special":
                values.update(state="withheld", category="special", hod_note=note)
                values.update(self._proof_fields(record, proof_requirements, proof_deadline))
            else:
                raise ValidationError(_("Select General or Special OD before approval."))
        elif decision == "request_proof":
            if record.state != "withheld" or record.category != "special":
                raise ValidationError(_("Only a withheld Special OD can request proof."))
            values.update(state="withheld", hod_note=note)
            values.update(self._proof_fields(record, proof_requirements, proof_deadline))
        elif decision in {"accept_proof", "return_proof"}:
            if record.state != "proof_review" or not record.proof_file:
                raise ValidationError(_("There is no submitted proof to verify."))
            if decision == "return_proof" and not note:
                raise ValidationError(_("Explain why the proof needs correction."))
            values.update(state="completed" if decision == "accept_proof" else "withheld", hod_note=note)
            if decision == "return_proof":
                values.update(self._proof_fields(record, proof_requirements, proof_deadline))
        record.with_context(campus_od_hod_review=True).write(values)
        record._record_event({
            "approve": "HOD approved General OD" if category == "general" else "HOD approved Special OD; proof pending",
            "reject": "HOD rejected OD", "request_proof": "HOD updated proof request",
            "accept_proof": "HOD verified proof; OD completed", "return_proof": "HOD returned proof for correction",
        }[decision] + (": " + note if note else ""))
        return {"reference": "OD%07d" % record.id, "state": record.state}

    def _proof_fields(self, record, requirements, deadline):
        try:
            due = fields.Date.to_date(deadline)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Set a valid proof submission deadline.")) from exc
        if not requirements or not due or due < record.date_to or due < fields.Date.context_today(self):
            raise ValidationError(_("Enter proof requirements and a deadline on or after the event ends."))
        return {"proof_requirements": requirements, "proof_deadline": due}
