from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class Faculty(models.Model):
    _inherit = "op.faculty"

    campus_coverage_revision = fields.Integer(copy=False)


class StaffLeaveCoverage(models.Model):
    _inherit = "hr.leave"

    campus_coverage = fields.Json(string="Teaching coverage", copy=False, readonly=True)
    campus_coverage_responses = fields.Json(copy=False, readonly=True, groups="base.group_no_one")
    campus_coverage_summary = fields.Text(compute="_compute_coverage_summary")

    def _coverage_faculty(self):
        self.ensure_one()
        employee = self.employee_id
        faculty = self.env["op.faculty"].sudo()
        if self.holiday_type != "employee" or not employee:
            return faculty.browse()
        identity = [("emp_id", "=", employee.id)]
        if employee.user_id:
            identity = ["|", ("user_id", "=", employee.user_id.id)] + identity
        return faculty.search([("company_id", "in", [False, self.company_id.id])] + identity)

    def _coverage_sessions(self):
        self.ensure_one()
        sessions = self.env["op.session"].sudo()
        if not self.date_from or not self.date_to:
            return sessions.browse()
        return sessions.search([
            ("faculty_id", "in", self._coverage_faculty().ids), ("company_id", "=", self.company_id.id),
            ("state", "in", ["confirm", "done"]), ("start_datetime", "<", self.date_to),
            ("end_datetime", ">", self.date_from),
        ], order="start_datetime, id")

    def _coverage_candidates(self):
        self.ensure_one()
        return self.env["op.faculty"].sudo().search([
            ("id", "not in", self._coverage_faculty().ids), ("company_id", "in", [False, self.company_id.id]),
            ("campus_category", "in", [False, "teaching"]),
            "|", ("user_id.active", "=", True), ("emp_id.user_id.active", "=", True),
        ], order="name, id")

    @api.model
    def _normalize_coverage(self, entries):
        if not isinstance(entries, list) or len(entries) > 500:
            raise ValidationError(_("Enter a valid class coverage plan. Split requests with more than 500 periods."))
        result = {}
        for row in entries:
            if not isinstance(row, dict) or set(row) != {"session_id", "faculty_id"}:
                raise ValidationError(_("Choose a substitute for each listed period."))
            session_id, faculty_id = row["session_id"], row["faculty_id"]
            if type(session_id) is not int or type(faculty_id) is not int or session_id <= 0 or faculty_id <= 0 or session_id in result:
                raise ValidationError(_("Each listed period must have exactly one substitute."))
            result[session_id] = faculty_id
        return result

    def _check_coverage(self, lock=False):
        self.ensure_one()
        sessions = self._coverage_sessions()
        plan = self._normalize_coverage(self.campus_coverage or [])
        if set(plan) - set(sessions.ids) or (lock and set(sessions.ids) != set(plan)):
            raise ValidationError(_("Assign a substitute to every affected class in Leave Requests before approval. Reload the timetable if it changed."))
        if not sessions:
            return
        candidates = self._coverage_candidates().filtered(lambda faculty: faculty.id in plan.values())
        if set(plan.values()) - set(candidates.ids):
            raise ValidationError(_("Choose active substitute teachers from this college. You cannot cover your own leave."))
        if lock:
            # Updating a revision makes a competing approval retry with a fresh snapshot.
            faculty_ids = tuple(sorted(set(plan.values()) | set(self._coverage_faculty().ids)))
            self.env.cr.execute("SELECT id FROM op_faculty WHERE id IN %s ORDER BY id FOR UPDATE", [faculty_ids])
            self.env.cr.execute(
                "UPDATE op_faculty SET campus_coverage_revision = COALESCE(campus_coverage_revision, 0) + 1 WHERE id IN %s",
                [faculty_ids],
            )
        available = self._coverage_availability(sessions, candidates)
        selected = {}
        for session in sessions.filtered(lambda session: session.id in plan):
            substitute = candidates.browse(plan[session.id])
            start, end = session.start_datetime, session.end_datetime
            overlaps = any(slot.start_datetime < end and slot.end_datetime > start for slot in selected.get(substitute.id, []))
            if substitute.id not in available[session.id] or overlaps:
                raise ValidationError(_("%(teacher)s is unavailable for %(subject)s at %(time)s. Choose another substitute.",
                    teacher=substitute.name, subject=session.subject_id.name,
                    time=fields.Datetime.context_timestamp(self, start).strftime("%d %b, %H:%M")))
            selected.setdefault(substitute.id, []).append(session)
        responses = self.sudo().campus_coverage_responses or {}
        if lock and any(responses.get(str(session.id)) != "Accepted" for session in sessions):
            raise ValidationError(_("Every affected class needs an accepted substitute before leave can be approved."))

    def _coverage_availability(self, sessions, candidates):
        if not sessions:
            return {}
        start = min(sessions.mapped("start_datetime"))
        end = max(sessions.mapped("end_datetime"))
        approved = self.sudo().search([
            ("id", "!=", self._origin.id or 0), ("company_id", "=", self.company_id.id), ("state", "=", "validate"),
            ("date_from", "<", end), ("date_to", ">", start),
        ])
        session_model = self.env["op.session"].sudo()
        commitments = {}
        busy = session_model.search([
            ("faculty_id", "in", candidates.ids), ("company_id", "=", self.company_id.id), ("state", "!=", "cancel"),
            ("start_datetime", "<", end), ("end_datetime", ">", start),
        ])
        for session in busy:
            commitments.setdefault(session.faculty_id.id, []).append((session.start_datetime, session.end_datetime))
        for other in approved:
            for substitute in candidates:
                if other.employee_id and (other.employee_id == substitute.emp_id or
                        (substitute.user_id and other.employee_id.user_id == substitute.user_id)):
                    commitments.setdefault(substitute.id, []).append((other.date_from, other.date_to))
            for slot in other.campus_coverage or []:
                period = session_model.browse(slot["session_id"]).exists()
                if period and period.state != "cancel":
                    commitments.setdefault(slot["faculty_id"], []).append((period.start_datetime, period.end_datetime))
        return {session.id: [faculty.id for faculty in candidates.sorted(
            lambda faculty, subject=session.subject_id: subject not in faculty.faculty_subject_ids
        ) if not any(first < session.end_datetime and last > session.start_datetime
                     for first, last in commitments.get(faculty.id, []))] for session in sessions}

    def _coverage_status(self, session_id, faculty_id):
        if not faculty_id:
            return "Not assigned"
        if self.state == "validate":
            return "Confirmed"
        if self.state == "refuse":
            return "Cancelled"
        return (self.sudo().campus_coverage_responses or {}).get(str(session_id), "Awaiting acceptance")

    def _coverage_row(self, session, faculty_id=False):
        faculty = self.env["op.faculty"].sudo().browse(faculty_id).exists()
        start = fields.Datetime.context_timestamp(self, session.start_datetime)
        end = fields.Datetime.context_timestamp(self, session.end_datetime)
        return {"id": session.id, "date": start.strftime("%d %b %Y"), "time": f"{start:%H:%M}–{end:%H:%M}",
                "subject": session.subject_id.name, "section": session.batch_id.name, "room": session.classroom_id.name or "",
                "faculty_id": faculty.id or False, "substitute": faculty.name or "", "teacher": session.faculty_id.name,
                "status": self._coverage_status(session.id, faculty.id),
                "start": fields.Datetime.to_string(session.start_datetime), "end": fields.Datetime.to_string(session.end_datetime)}

    def _coverage_rows(self):
        self.ensure_one()
        plan = self._normalize_coverage(self.campus_coverage or [])
        return [self._coverage_row(session, plan.get(session.id)) for session in self._coverage_sessions()]

    @api.depends("campus_coverage", "campus_coverage_responses", "date_from", "date_to", "employee_id", "state")
    def _compute_coverage_summary(self):
        for leave in self:
            rows = leave._coverage_rows()
            leave.campus_coverage_summary = "\n".join(
                _("%(date)s · %(time)s · %(subject)s / %(section)s → %(substitute)s (%(status)s)",
                  **dict(row, substitute=row["substitute"] or _("Substitute required"))) for row in rows
            ) if rows else _("No scheduled teaching periods in this request.")

    @api.model_create_multi
    def create(self, values):
        if not self.env.su and any({"campus_coverage", "campus_coverage_responses"} & value.keys() for value in values):
            raise AccessError(_("Set teaching coverage through Leave Requests."))
        records = super().create(values)
        if any(value.get("state") in ("validate", "validate1") for value in values):
            for leave in records.filtered(lambda record: record.state in ("validate", "validate1")):
                leave._check_coverage(lock=True)
        return records

    def write(self, values):
        if {"campus_coverage", "campus_coverage_responses"} & values.keys() and not self.env.su:
            raise AccessError(_("Set teaching coverage through Leave Requests."))
        result = super().write(values)
        approval = values.get("state") in ("validate", "validate1")
        changed_dates = set(values) & {"request_date_from", "request_date_to", "date_from", "date_to", "employee_id",
            "request_date_from_period", "request_unit_half", "request_unit_hours", "request_hour_from", "request_hour_to"}
        if approval or changed_dates:
            for leave in self.filtered(lambda record: record.state in ("validate", "validate1")):
                leave._check_coverage(lock=True)
        return result
