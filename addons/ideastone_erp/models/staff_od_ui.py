from collections import Counter
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StaffODUI(models.AbstractModel):
    _name = "campus.staff.od.ui"
    _description = "Assigned mentor On Duty workspace"

    def _assigned_routes(self):
        user = self.env.user
        if not user.active or not user.has_group("base.group_user"):
            raise AccessError(_("An active internal staff account is required."))
        return self.env["campus.student.leave.routing"].sudo().search([
            ("advisor_id", "=", user.id), ("company_id", "=", self.env.company.id), ("active", "=", True),
        ])

    def _classes(self, routes):
        classes = {}
        for route in routes:
            placements = route.student_id.course_detail_ids.filtered(
                lambda row: row.company_id == self.env.company and row.state == "running"
                and row.batch_id and row.academic_term_id
            )
            placement = placements[:1]
            if not placement:
                continue
            key = f"{placement.batch_id.id}:{placement.academic_term_id.id}"
            entry = classes.setdefault(key, {
                "key": key,
                "label": placement.batch_id.name or _("Unassigned class"),
                "programme": placement.course_id.name or "",
                "semester": placement.academic_term_id.name or "",
                "student_ids": set(),
                "route_ids": set(),
            })
            entry["student_ids"].add(route.student_id.id)
            entry["route_ids"].add(route.id)
        return classes

    @api.model
    def get_page_data(self, class_key=None):
        if self.env.user.has_group("ideastone_erp.group_od_hod_approver"):
            return self.env["campus.hod.od.ui"].get_page_data(class_key)
        routes = self._assigned_routes()
        classes = self._classes(routes)
        if class_key and class_key not in classes:
            raise AccessError(_("This mentorship class is not assigned to your account."))
        selected = classes.get(class_key) if class_key else next(iter(classes.values()), None)
        today = fields.Date.context_today(self)
        result = {
            "mentor_name": self.env.user.name,
            "company_name": self.env.company.name,
            "class_key": selected["key"] if selected else "",
            "class_label": selected["label"] if selected else _("No assigned class"),
            "class_programme": selected["programme"] if selected else "",
            "semester": selected["semester"] if selected else "",
            "classes": [{"key": item["key"], "label": item["label"], "semester": item["semester"]}
                        for item in classes.values()],
            "total_students": len(selected["student_ids"]) if selected else 0,
            "today": fields.Date.to_string(today),
            "timezone": self.env.context.get("tz") or self.env.user.tz or "UTC",
            "rows": [], "actions": [], "week_activity": [], "month_activity": [],
            "pending": 0, "approved": 0, "students_on_od": 0,
            "repeated_students": 0, "overlapping_students": 0, "urgent_reviews": 0,
        }
        if not selected:
            return result

        records = self.env["campus.student.od"].sudo().search([
            ("mentor_id", "=", self.env.uid), ("company_id", "=", self.env.company.id),
            ("routing_id", "in", list(selected["route_ids"])),
        ], order="create_date desc, id desc", limit=1000)
        records = records.filtered(
            lambda rec: rec.enrolment_id.batch_id.id == int(selected["key"].split(":")[0])
            and rec.term_id.id == int(selected["key"].split(":")[1])
        )
        state_labels = dict(self.env["campus.student.od"]._fields["state"].selection)
        rows = []
        for record in records:
            rows.append({
                "id": record.id, "reference": "OD%07d" % record.id,
                "student": record.student_id.name, "student_id": record.student_id.id,
                "name": record.name, "purpose": record.purpose, "venue": record.venue,
                "date_from": fields.Date.to_string(record.date_from),
                "date_to": fields.Date.to_string(record.date_to),
                "session_from": record.session_from, "session_to": record.session_to,
                "created": fields.Datetime.to_string(record.create_date),
                "submitted_date": fields.Date.to_string(fields.Datetime.context_timestamp(self, record.create_date).date()),
                "status": state_labels[record.state], "state": record.state,
                "category": dict(record._fields["category"].selection)[record.category],
                "can_review": record.state == "pending_mentor",
                "mentor_note": record.mentor_note or "",
                "events": [{"action": event.action, "by": event.actor_id.name,
                            "at": fields.Datetime.to_string(event.create_date)}
                           for event in record.event_ids.sorted("id")],
            })
        result["rows"] = rows
        result["pending"] = sum(row["state"] == "pending_mentor" for row in rows)
        result["approved"] = sum(row["state"] in {"withheld", "proof_review", "completed"} for row in rows)
        result["students_on_od"] = len({row["student_id"] for row in rows
                                             if row["state"] == "completed" and row["date_from"] <= result["today"] <= row["date_to"]})
        counts = Counter(row["student_id"] for row in rows if row["state"] not in {"draft", "cancelled"})
        result["repeated_students"] = sum(count > 1 for count in counts.values())
        overlapping = set()
        active = [row for row in rows if row["state"] not in {"draft", "returned", "rejected", "invalid", "cancelled"}]
        for index, first in enumerate(active):
            for second in active[index + 1:]:
                if first["student_id"] != second["student_id"] and first["date_from"] <= second["date_to"] and second["date_from"] <= first["date_to"]:
                    overlapping.update((first["student_id"], second["student_id"]))
        result["overlapping_students"] = len(overlapping)
        soon = fields.Date.to_string(today + timedelta(days=2))
        result["urgent_reviews"] = sum(row["can_review"] and row["date_from"] <= soon for row in rows)
        result["actions"] = sorted((row for row in rows if row["can_review"]), key=lambda row: (row["date_from"], row["id"]))[:4]

        week_start = today - timedelta(days=today.weekday())
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            count = sum(row["submitted_date"] == fields.Date.to_string(day) for row in rows)
            result["week_activity"].append({"label": day.strftime("%a"), "sub": day.strftime("%d %b"), "count": count})
        for offset in range(3, -1, -1):
            start = week_start - timedelta(days=offset * 7)
            end = start + timedelta(days=6)
            count = sum(fields.Date.to_string(start) <= row["submitted_date"] <= fields.Date.to_string(end) for row in rows)
            result["month_activity"].append({"label": _("Week %s") % (4 - offset), "sub": start.strftime("%d %b"), "count": count})
        return result

    @api.model
    def review_request(self, request_id, decision, note=""):
        routes = self._assigned_routes()
        if decision not in {"forward", "return"}:
            raise ValidationError(_("Choose a valid mentor decision."))
        note = str(note or "").strip()
        if len(note) > 250 or decision == "return" and not note:
            raise ValidationError(_("A return needs a review note of at most 250 characters."))
        try:
            request_id = int(request_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid OD request.")) from exc
        record = self.env["campus.student.od"].sudo().search([
            ("id", "=", request_id), ("mentor_id", "=", self.env.uid),
            ("routing_id", "in", routes.ids), ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not record:
            raise AccessError(_("This OD request is not assigned to your mentorship class."))
        record._lock()
        if record.state != "pending_mentor" or record.routing_id.advisor_id != self.env.user:
            raise ValidationError(_("This request is no longer awaiting your review. Refresh the page."))
        state = "pending_hod" if decision == "forward" else "returned"
        record.with_context(campus_od_mentor_review=True).write({
            "state": state, "mentor_note": note,
            "mentor_reviewed_by_id": self.env.uid,
            "mentor_reviewed_at": fields.Datetime.now(),
        })
        record._record_event(("Forwarded to HOD" if decision == "forward" else "Returned to student")
                             + (": " + note if note else ""))
        return {"state": state, "reference": "OD%07d" % record.id}
