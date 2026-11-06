"""Saved workflows behind the faculty My Task List panels."""

import math
from datetime import datetime, time, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext, plaintext2html

from odoo import _, api, fields, models


class FacultyDailyRegister(models.Model):
    _name = "campus.faculty.daily.register"
    _description = "Mentorship class daily attendance register"
    _inherit = "campus.record"

    batch_id = fields.Many2one("op.batch", required=True, check_company=True, ondelete="restrict")
    term_id = fields.Many2one("op.academic.term", required=True, check_company=True, ondelete="restrict")
    mentor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    date = fields.Date(required=True)
    period = fields.Selection([("FN", "Forenoon"), ("AN", "Afternoon"), ("FULL", "Full day")], required=True)
    entries = fields.Json(default=dict)
    submitted_by = fields.Many2one("res.users", readonly=True)
    submitted_on = fields.Datetime(readonly=True)
    _sql_constraints = [
        ("daily_register_slot", "unique(company_id,mentor_id,batch_id,term_id,date,period)", "This class register already exists."),
    ]


class FacultyCircularAcknowledgement(models.Model):
    _name = "campus.faculty.circular.ack"
    _description = "Faculty circular acknowledgement"

    circular_id = fields.Many2one("campus.circular", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    _sql_constraints = [
        ("circular_ack_once", "unique(circular_id,user_id)", "This notice has already been acknowledged."),
    ]


class FacultyTaskDetails(models.Model):
    _inherit = "campus.faculty.task"

    campus_diary = fields.Boolean(default=False)
    campus_area = fields.Char("Assigned area")
    priority = fields.Selection(selection_add=[("0m", "Medium"), ("1",)], ondelete={"0m": "set default"})


class FacultyLessonDetails(models.Model):
    _inherit = "campus.teaching.plan"

    campus_week = fields.Integer("Teaching week")
    campus_outcome = fields.Text("Expected learning outcome")


class FacultyCircularDetails(models.Model):
    _inherit = "campus.circular"

    campus_faculty_pinned = fields.Boolean("Pin in faculty circulars")


class FacultyAlternateRequest(models.Model):
    _inherit = "campus.service.request"

    campus_alternate_session_id = fields.Many2one("op.session", check_company=True, ondelete="restrict")
    campus_substitute_consent = fields.Selection([("accepted", "Accepted"), ("declined", "Declined")], copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("campus_substitute_consent"):
                raise AccessError(_("Substitute consent must come from the assigned substitute."))
            if vals.get("campus_alternate_session_id"):
                session = self.env["op.session"].browse(vals["campus_alternate_session_id"]).exists()
                replacement = self.env["op.faculty"].sudo().browse(vals.get("replacement_id")).exists()
                if (not session or session.company_id != self.env.company or session.state != "confirm"
                        or vals.get("kind") != "alternate" or vals.get("faculty_id") != session.faculty_id.id
                        or not replacement.active or not replacement.user_id.active or replacement == session.faculty_id
                        or replacement.company_id != session.company_id
                        or (not self.env.su and session.faculty_id.user_id != self.env.user)):
                    raise AccessError(_("Choose your confirmed teaching hour and an active substitute in this college."))
        return super().create(vals_list)

    def write(self, vals):
        if "campus_substitute_consent" in vals:
            raise AccessError(_("Use the substitute response action to record consent."))
        if "campus_alternate_session_id" in vals or (
            {"kind", "requester_id", "company_id", "faculty_id", "replacement_id"} & vals.keys()
            and self.filtered("campus_alternate_session_id")
        ):
            raise ValidationError(_("File a new request to change the teaching hour or substitute."))
        return super().write(vals)

    def _check_substitute_availability(self):
        self.ensure_one()
        session = self.campus_alternate_session_id
        substitute = self.replacement_id
        self.env.cr.execute("SELECT id FROM op_faculty WHERE id=%s FOR UPDATE", [substitute.id])
        self.env.cr.execute("SELECT id FROM op_session WHERE id=%s FOR UPDATE", [session.id])
        session.invalidate_recordset()
        if session.state != "confirm" or session.end_datetime <= fields.Datetime.now():
            raise ValidationError(_("This teaching hour is no longer available for coverage."))
        if self.env["op.session"].sudo().search_count([
            ("company_id", "=", self.company_id.id), ("faculty_id", "=", substitute.id),
            ("state", "!=", "cancel"), ("start_datetime", "<", session.end_datetime),
            ("end_datetime", ">", session.start_datetime),
        ]):
            raise ValidationError(_("The substitute already has a class at this time."))
        if self.sudo().search_count([
            ("id", "!=", self.id), ("company_id", "=", self.company_id.id),
            ("kind", "=", "alternate"), ("state", "in", ["approved", "done"]),
            ("campus_alternate_session_id", "!=", False), "|",
            ("campus_alternate_session_id", "=", session.id), "&", "&",
            ("replacement_id", "=", substitute.id),
            ("campus_alternate_session_id.start_datetime", "<", session.end_datetime),
            ("campus_alternate_session_id.end_datetime", ">", session.start_datetime),
        ]):
            raise ValidationError(_("Approved coverage already exists for this hour or substitute."))

    def _validate_transition(self, target):
        if target == "approved" and self.campus_alternate_session_id:
            if self.campus_substitute_consent != "accepted":
                raise ValidationError(_("The proposed substitute must accept before approval."))
            self._check_substitute_availability()
        return super()._validate_transition(target)


class FacultySop(models.AbstractModel):
    _inherit = "campus.faculty.task.list"

    def _sop_date(self, value):
        try:
            day = fields.Date.to_date(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Enter a valid date.")) from error
        if not day:
            raise ValidationError(_("Enter a valid date."))
        return day

    def _sop_text(self, value, maximum):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
            raise ValidationError(_("Enter the required text within %(limit)s characters.", limit=maximum))
        return value.strip()

    def _sop_id(self, value):
        if type(value) is not int or not 1 <= value <= 2147483647:
            raise ValidationError(_("Choose a valid saved record."))
        return value

    def _sop_scope(self):
        return self.env["campus.faculty.home"]._scope()

    def _sop_allocations(self, sessions):
        return list({
            (row.batch_id.id, row.subject_id.id): {
                "id": row.id, "subject": row.subject_id.name, "code": row.subject_id.code,
                "class": row.batch_id.name, "semester": row.batch_id.campus_term_id.name or "",
                "subject_id": row.subject_id.id, "class_id": row.batch_id.id,
            } for row in reversed(sessions)
        }.values())

    def _sop_session(self, session_id, sessions):
        record = sessions.filtered(lambda row: row.id == self._sop_id(session_id))
        if not record:
            raise AccessError(_("Choose one of your allocated teaching hours."))
        return record

    def _sop_session_row(self, row):
        start = fields.Datetime.context_timestamp(self, row.start_datetime)
        end = fields.Datetime.context_timestamp(self, row.end_datetime)
        return {"id": row.id, "subject": row.subject_id.name, "class": row.batch_id.name,
                "date": str(start.date()), "day": start.weekday(), "time": f"{start:%H:%M}–{end:%H:%M}",
                "room": row.classroom_id.name or "—", "status": "Completed" if row.state == "done" else "Scheduled",
                "term_id": row.batch_id.campus_term_id.id, "subject_key": f"{row.subject_id.id}:{row.batch_id.id}"}

    def _sop_notices(self, batches):
        today = fields.Date.context_today(self)
        return self.env["campus.circular"].sudo().search([
            ("company_id", "=", self.env.company.id), ("campus_status", "=", "published"),
            ("audience", "in", ["all", "faculty"]), ("date_from", "<=", today),
            "|", ("date_to", "=", False), ("date_to", ">=", today),
            "|", ("campus_batch_id", "=", False), ("campus_batch_id", "in", batches.ids),
            "|", ("campus_course_id", "=", False), ("campus_course_id", "in", batches.course_id.ids),
            "|", ("campus_group_id", "=", False), ("campus_group_id", "in", self.env.user.groups_id.ids),
        ], order="campus_faculty_pinned desc, date_from desc, id desc")

    def _sop_assignment_domain(self, faculty):
        return [
            ("company_id", "=", self.env.company.id), ("faculty_id", "=", faculty.id),
        ]

    def _sop_assignment_types(self):
        return self.env["grading.assignment.type"].browse([
            self.env.ref(f"ideastone_erp.faculty_sop_assignment_{kind}").id
            for kind in ("file", "written", "practical")
        ])

    def _sop_alternates(self, faculty):
        return self.env["campus.service.request"].sudo().search([
            ("company_id", "=", self.env.company.id), ("kind", "=", "alternate"),
            "|", ("requester_id", "=", self.env.uid), ("replacement_id", "=", faculty.id),
        ], order="date desc, id desc", limit=250)

    @api.model
    def get_sop_page(self, page):
        faculty, year, sessions, batches, _enrolments = self._sop_scope()
        today = fields.Date.context_today(self)
        result = {"user": self.env.user.name, "today": str(today), "year": year.name or "",
                  "demo": self.env.company.campus_demo, "rows": []}
        company = self.env.company
        if page == "timetable":
            first = today - timedelta(days=today.weekday())
            last = first + timedelta(days=7)
            result.update(week=str(first), rows=[self._sop_session_row(row) for row in sessions if
                first <= fields.Datetime.context_timestamp(self, row.start_datetime).date() < last])
            result["coverage"] = [dict(self._sop_session_row(row.campus_alternate_session_id),
                original=row.faculty_id.name, substitute=row.replacement_id.name, covering=row.replacement_id == faculty)
                for row in self._sop_alternates(faculty) if row.state in {"approved", "done"}
                and row.campus_alternate_session_id and row.campus_alternate_session_id.end_datetime >= fields.Datetime.now()]
            if not self.env.user.has_group("ideastone_erp.group_od_hod_approver"):
                _mentor, _classes, assigned = self._mentor_context()
                result["mentorship"] = assigned["label"] if assigned else False
        elif page == "tasks":
            records = self.env["campus.faculty.task"].search([
                ("company_id", "=", company.id), ("user_id", "=", self.env.uid), ("state", "!=", "cancelled"),
            ], limit=250)
            result.update(rows=[{"id": row.id, "title": row.name, "area": row.campus_area or row.kind,
                "date": str(row.deadline), "priority": {"1": "High", "0m": "Medium"}.get(row.priority, "Normal"),
                "done": row.state == "done"} for row in records if not row.campus_diary],
                diary=[{"id": row.id, "date": str(row.date), "note": html2plaintext(row.notes or "")}
                       for row in records.filtered("campus_diary").sorted("date", reverse=True)[:8]])
        elif page == "exams":
            exams = self.env["op.exam"].search([("company_id", "=", company.id),
                ("responsible_id", "=", faculty.id), ("campus_managed", "=", True)], order="start_time desc", limit=250)
            result["rows"] = [{"id": row.id, "name": row.name, "subject_id": row.subject_id.id,
                "subject": row.subject_id.name, "code": row.subject_id.code, "class": row.batch_id.name,
                "date": str(fields.Datetime.context_timestamp(self, row.start_time).date()), "status": row.campus_state}
                for row in exams]
        elif page == "assignments":
            result.update(allocations=self._sop_allocations(sessions),
                rows=[{"id": row.id, "title": row.name, "subject": row.subject_id.name, "class": row.batch_id.name,
                       "date": str(fields.Datetime.context_timestamp(self, row.submission_date).date()), "maximum": row.marks,
                       "students": len(row.allocation_ids), "status": row.state,
                       "submitted": len(row.assignment_sub_line.filtered(lambda line: line.state != "draft")),
                       "waiting": len(row.assignment_sub_line.filtered(lambda line: line.state == "submit"))}
                      for row in self.env["op.assignment"].search(self._sop_assignment_domain(faculty), limit=250)],
                types=self._sop_assignment_types().read(["name"]))
        elif page == "alternate":
            substitutes = self.env["op.faculty"].sudo().search([("company_id", "=", company.id),
                ("id", "!=", faculty.id), ("user_id.active", "=", True)], order="name")
            requests = self._sop_alternates(faculty)
            requested_slots = set(requests.filtered(lambda row:
                row.state in ("submitted", "approved", "done") and row.campus_substitute_consent != "declined"
            ).campus_alternate_session_id.ids)
            result.update(substitutes=[{"id": row.id, "name": row.name} for row in substitutes],
                sessions=[self._sop_session_row(row) for row in sessions if row.id not in requested_slots and row.state == "confirm"
                          and row.end_datetime > fields.Datetime.now()],
                rows=[{"id": row.id, "date": str(row.date_from or row.date),
                    "class": row.campus_alternate_session_id.batch_id.name or "—",
                    "time": self._sop_session_row(row.campus_alternate_session_id)["time"] if row.campus_alternate_session_id else "—",
                    "faculty": row.faculty_id.name, "substitute": row.replacement_id.name,
                    "reason": row.description, "state": row.state, "consent": row.campus_substitute_consent,
                    "can_reply": bool(row.campus_alternate_session_id and row.state == "submitted"
                                      and row.replacement_id == faculty and not row.campus_substitute_consent)}
                    for row in requests])
        elif page == "lessons":
            plans = self.env["campus.teaching.plan"].search([("company_id", "=", company.id),
                ("faculty_id", "=", faculty.id)], order="planned_date, id", limit=500)
            result.update(allocations=self._sop_allocations(sessions), rows=[{
                "id": row.id, "subject_id": row.subject_id.id, "class_id": row.batch_id.id,
                "week": row.campus_week or row.unit, "topic": row.topic, "date": str(row.planned_date),
                "outcome": row.campus_outcome or row.co_level or "", "done": bool(row.execution_date),
            } for row in plans])
        elif page == "circulars":
            notices = self._sop_notices(batches)
            read = self.env["campus.faculty.circular.ack"].sudo().search([
                ("user_id", "=", self.env.uid), ("circular_id", "in", notices.ids),
            ]).circular_id
            result["rows"] = [{"id": row.id, "title": row.name, "date": str(row.date_from),
                "category": row.campus_category or "General", "issuer": row.approved_by.name or company.name,
                "body": html2plaintext(row.body or ""), "pinned": row.campus_faculty_pinned, "read": row in read}
                for row in notices]
        else:
            raise ValidationError(_("Choose a My Task List page."))
        return result

    @api.model
    def save_sop_task(self, title, area, date, priority):
        self._faculty()
        if priority not in ("0", "0m", "1"):
            raise ValidationError(_("Choose a valid priority."))
        return self.env["campus.faculty.task"].create({"name": self._sop_text(title, 200),
            "campus_area": self._sop_text(area or _("Faculty work"), 200),
            "deadline": self._sop_date(date), "priority": priority}).id

    @api.model
    def save_sop_diary(self, date, note):
        self._faculty()
        day = self._sop_date(date)
        if day > fields.Date.context_today(self):
            raise ValidationError(_("Choose today or an earlier diary date."))
        return self.env["campus.faculty.task"].create({"name": _("Daily e-Diary"), "date": day, "deadline": day,
            "campus_diary": True, "state": "done", "notes": plaintext2html(self._sop_text(note, 5000))}).id

    @api.model
    def toggle_sop_task(self, record_id, completed):
        self._faculty()
        task = self.env["campus.faculty.task"].search([("id", "=", self._sop_id(record_id)),
            ("company_id", "=", self.env.company.id), ("user_id", "=", self.env.uid),
            ("campus_diary", "=", False), ("state", "!=", "cancelled")], limit=1)
        if not task or type(completed) is not bool:
            raise AccessError(_("Choose a task assigned to your account."))
        return task.write({"state": "done" if completed else "planned"})

    @api.model
    def save_sop_assignment(self, session_id, title, due, maximum, assignment_type):
        faculty, _year, sessions, _batches, enrolments = self._sop_scope()
        session = self._sop_session(session_id, sessions)
        day = self._sop_date(due)
        if day < fields.Date.context_today(self) or type(maximum) not in (int, float) or not 1 <= maximum <= 100:
            raise ValidationError(_("Choose a due date from today and maximum marks from 1 to 100."))
        name = self._sop_text(title, 200)
        students = enrolments.filtered(lambda row: row.batch_id == session.batch_id).student_id
        if not students:
            raise ValidationError(_("This class has no active enrolled students."))
        kind = self._sop_assignment_types().filtered(lambda row: row.id == self._sop_id(assignment_type))
        if not kind:
            raise ValidationError(_("Choose an assignment submission type."))
        zone = pytz.timezone(self.env.user.tz or "UTC")
        deadline = zone.localize(datetime.combine(day, time(23, 59))).astimezone(pytz.UTC).replace(tzinfo=None)
        record = self.env["op.assignment"].create({"name": name, "description": name, "campus_learning": True,
            "course_id": session.course_id.id, "batch_id": session.batch_id.id, "subject_id": session.subject_id.id,
            "faculty_id": faculty.id, "assignment_type": kind.id, "issued_date": fields.Datetime.now(),
            "submission_date": deadline, "allocation_ids": [fields.Command.set(students.ids)], "marks": maximum})
        record.act_publish()
        return record.id

    @api.model
    def get_sop_submissions(self, record_id):
        faculty = self._faculty()
        record = self.env["op.assignment"].search(
            self._sop_assignment_domain(faculty) + [("id", "=", self._sop_id(record_id))], limit=1)
        if not record:
            raise AccessError(_("Choose an assignment you teach."))
        submissions = {line.student_id.id: line for line in record.assignment_sub_line if line.state != "draft"}
        return [{"id": student.id, "name": student.name, "roll": student.gr_no or "",
                 "submission": submissions[student.id].id if student.id in submissions else False,
                 "state": submissions[student.id].state if student.id in submissions else "missing",
                 "marks": submissions[student.id].marks if student.id in submissions and submissions[student.id].campus_marks_entered else None,
                 "feedback": submissions[student.id].note or "" if student.id in submissions else "",
                 "file": submissions[student.id].campus_filename if student.id in submissions else False}
                for student in record.allocation_ids.sorted("name")]

    @api.model
    def save_sop_review(self, submission_id, marks, feedback):
        faculty = self._faculty()
        record = self.env["op.assignment.sub.line"].search([("id", "=", self._sop_id(submission_id)),
            ("company_id", "=", self.env.company.id), ("assignment_id.faculty_id", "=", faculty.id)], limit=1)
        if not record:
            raise AccessError(_("Choose a submission from your own assignment."))
        self.env.cr.execute("SELECT id FROM op_assignment_sub_line WHERE id=%s FOR UPDATE", [record.id])
        record.invalidate_recordset()
        if record.state != "submit":
            raise ValidationError(_("Only submitted work can receive a grade."))
        if type(marks) not in (int, float) or not math.isfinite(marks) or not 0 <= marks <= record.assignment_id.marks:
            raise ValidationError(_("Enter a score between zero and the assignment maximum."))
        return record.write({"marks": marks, "note": self._sop_text(feedback, 5000), "state": "accept"})

    @api.model
    def save_sop_alternate(self, session_id, replacement_id, reason):
        faculty, _year, sessions, _batches, _enrolments = self._sop_scope()
        session = self._sop_session(session_id, sessions)
        day = fields.Datetime.context_timestamp(self, session.start_datetime).date()
        if session.end_datetime <= fields.Datetime.now():
            raise ValidationError(_("Choose an upcoming hour."))
        self.env.cr.execute("SELECT id FROM op_session WHERE id=%s FOR UPDATE", [session.id])
        if self.env["campus.service.request"].sudo().search_count([
            ("campus_alternate_session_id", "=", session.id), ("state", "in", ["submitted", "approved", "done"]),
            ("campus_substitute_consent", "!=", "declined"),
        ]):
            raise ValidationError(_("This teaching hour already has a coverage request."))
        record = self.env["campus.service.request"].create({
            "name": _("Alternate hour · %s", session.subject_id.name), "kind": "alternate",
            "faculty_id": faculty.id, "replacement_id": self._sop_id(replacement_id),
            "campus_alternate_session_id": session.id, "date_from": day, "date_to": day,
            "description": self._sop_text(reason, 5000),
        })
        record.action_submit()
        return record.id

    @api.model
    def reply_sop_alternate(self, record_id, answer):
        faculty = self._faculty()
        record = self._sop_alternates(faculty).filtered(lambda row: row.id == self._sop_id(record_id))
        if not record or record.replacement_id != faculty or not record.campus_alternate_session_id:
            raise AccessError(_("Only the proposed substitute can respond."))
        record._lock()
        if record.state != "submitted" or record.campus_substitute_consent or answer not in ("accepted", "declined"):
            raise ValidationError(_("This coverage request cannot be answered again."))
        if answer == "accepted":
            record._check_substitute_availability()
        record._set_system_values({"campus_substitute_consent": answer})
        self.env["campus.mvp.audit"]._log(record, _("Substitute response: %s", answer))
        return True

    @api.model
    def save_sop_lesson(self, session_id, topic, week, date, outcome):
        faculty, _year, sessions, _batches, _enrolments = self._sop_scope()
        session = self._sop_session(session_id, sessions)
        day = self._sop_date(date)
        term = session.batch_id.campus_term_id
        if type(week) is not int or not 1 <= week <= 26 or not term or not term.term_start_date <= day <= term.term_end_date:
            raise ValidationError(_("Choose week 1–26 and a target date in the assigned semester."))
        topic = self._sop_text(topic, 200)
        return self.env["campus.teaching.plan"].create({"name": topic, "topic": topic, "faculty_id": faculty.id,
            "subject_id": session.subject_id.id, "batch_id": session.batch_id.id, "term_id": term.id,
            "unit": _("Week %s", week), "campus_week": week, "planned_date": day,
            "campus_outcome": self._sop_text(outcome, 5000)}).id

    @api.model
    def toggle_sop_lesson(self, record_id, completed):
        faculty = self._faculty()
        plan = self.env["campus.teaching.plan"].search([("id", "=", self._sop_id(record_id)),
            ("company_id", "=", self.env.company.id), ("faculty_id", "=", faculty.id)], limit=1)
        if not plan or type(completed) is not bool:
            raise AccessError(_("Choose your own lesson topic."))
        return plan.write({"execution_date": fields.Date.context_today(self) if completed else False,
                           "actual_hours": plan.actual_hours if completed else 0})

    @api.model
    def acknowledge_sop_circular(self, record_id):
        _faculty, _year, _sessions, batches, _enrolments = self._sop_scope()
        notice = self._sop_notices(batches).filtered(lambda row: row.id == self._sop_id(record_id))
        if not notice:
            raise AccessError(_("This circular is outside your current audience."))
        self.env.cr.execute("SELECT id FROM campus_circular WHERE id=%s FOR UPDATE", [notice.id])
        acknowledgements = self.env["campus.faculty.circular.ack"].sudo()
        if not acknowledgements.search_count([("circular_id", "=", notice.id), ("user_id", "=", self.env.uid)]):
            acknowledgements.create({"circular_id": notice.id, "user_id": self.env.uid})
        return True

    def _sop_exam(self, exam_id):
        faculty = self._faculty()
        exam = self.env["op.exam"].search([("id", "=", self._sop_id(exam_id)),
            ("company_id", "=", self.env.company.id), ("responsible_id", "=", faculty.id),
            ("campus_managed", "=", True)], limit=1)
        if not exam:
            raise AccessError(_("Choose an assessment assigned to you."))
        return exam

    @api.model
    def get_sop_marks(self, exam_id):
        exam = self._sop_exam(exam_id)
        results = {row.student_id.id: row for row in exam.campus_result_ids}
        students = exam.campus_result_ids.student_id
        if exam.campus_state in {"draft", "entry"}:
            students |= exam._campus_roster_enrolments().student_id
        previous = self.env["op.exam"].search([("company_id", "=", self.env.company.id),
            ("responsible_id", "in", exam.responsible_id.ids), ("batch_id", "=", exam.batch_id.id),
            ("subject_id", "=", exam.subject_id.id), ("start_time", "<", exam.start_time),
            ("campus_state", "in", ["submitted", "locked", "published"])], order="start_time desc", limit=1)
        earlier = {row.student_id.id: row.marks for row in previous.campus_result_ids if row.campus_entered}
        rows = []
        for student in students.sorted("name"):
            line = results.get(student.id)
            rows.append({"id": student.id, "name": student.name, "roll": student.gr_no or "",
                         "marks": line.marks if line and line.campus_entered else None,
                         "previous": earlier.get(student.id)})
        return {"id": exam.id, "status": exam.campus_state, "maximum": exam.total_marks,
                "previous_maximum": previous.total_marks or 0, "rows": rows}

    @api.model
    def save_sop_marks(self, exam_id, values, submit=False):
        exam = self._sop_exam(exam_id)
        exam._campus_can_enter()
        exam._mvp_lock()
        if (exam.campus_state not in {"draft", "entry"} or not isinstance(values, dict)
                or type(submit) is not bool or len(values) > 2000):
            raise ValidationError(_("Enter marks on an open, assigned assessment."))
        exam.action_campus_roster()
        lines = {str(line.student_id.id): line for line in exam.campus_result_ids}
        if set(values) - set(lines):
            raise AccessError(_("Enter marks only for the assessment roster."))
        for key, marks in values.items():
            if marks is None and not submit:
                lines[key].write({"campus_entered": False})
                continue
            if type(marks) not in (int, float) or not math.isfinite(marks) or not 0 <= marks <= exam.total_marks:
                raise ValidationError(_("Enter marks between zero and the assessment maximum."))
            lines[key].write({"marks": marks})
        if submit:
            exam.action_campus_submit()
        return True

    def _sop_daily_records(self, selected):
        batch_id, term_id = map(int, selected["key"].split(":"))
        return self.env["campus.faculty.daily.register"].sudo(), [
            ("company_id", "=", self.env.company.id), ("mentor_id", "=", self.env.uid),
            ("batch_id", "=", batch_id), ("term_id", "=", term_id),
        ]

    def _sop_daily_protected(self, student_ids, day, period):
        first = day.toordinal() * 2 + (period == "AN")
        last = day.toordinal() * 2 + (period != "FN")
        company = self.env.company.id
        leave = self.env["campus.student.leave"].sudo().search([("company_id", "=", company),
            ("student_id", "in", student_ids), ("state", "=", "approved"), ("date", "<=", day), ("deadline", ">=", day)])
        od = self.env["campus.student.od"].sudo().search([("company_id", "=", company),
            ("student_id", "in", student_ids), ("state", "=", "completed"), ("date_from", "<=", day), ("date_to", ">=", day)])
        return {row.student_id.id for row in leave if
                row.date.toordinal() * 2 + (row.green_card and row.green_from_session == "AN") <= last
                and row.deadline.toordinal() * 2 + (not row.green_card or row.green_to_session == "AN") >= first} | {
                row.student_id.id for row in od if row.date_from.toordinal() * 2 + (row.session_from == "afternoon") <= last
                and row.date_to.toordinal() * 2 + (row.session_to == "afternoon") >= first}

    def _sop_daily_roster(self, selected, day):
        batch_id, term_id = map(int, selected["key"].split(":"))
        return self.env["op.student.course"].sudo().search([
            ("company_id", "=", self.env.company.id), ("batch_id", "=", batch_id),
            ("academic_term_id", "=", term_id), ("student_id", "in", list(selected["student_ids"])),
            ("student_id.active", "=", True), ("campus_date_from", "<=", day),
            "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", day),
        ]).student_id.sorted("name")

    @api.model
    def get_sop_daily(self, class_key=False, date=False, period="FN"):
        _faculty, classes, selected = self._mentor_context(class_key)
        day = self._sop_date(date) if date else fields.Date.context_today(self)
        if period not in ("FN", "AN", "FULL"):
            raise ValidationError(_("Choose a daily attendance session."))
        result = {"user": self.env.user.name, "today": str(fields.Date.context_today(self)),
                  "demo": self.env.company.campus_demo, "date": str(day), "period": period,
                  "classes": [{"key": row["key"], "label": row["label"]} for row in classes.values()],
                  "class_key": selected["key"] if selected else "", "rows": [], "history": [], "locked": False}
        if not selected:
            return result
        records, domain = self._sop_daily_records(selected)
        register = records.search(domain + [("date", "=", day), ("period", "=", period)], limit=1)
        saved = register.entries or {}
        students = self._sop_daily_roster(selected, day)
        locked = bool(register.submitted_on)
        protected = self._sop_daily_protected(students.ids, day, period) if not locked else set()
        for row in students:
            entry = saved.get(str(row.id), {})
            if locked and not entry:
                continue
            status = entry.get("status", "unmarked")
            if not locked:
                status = "excused" if row.id in protected else ("unmarked" if status == "excused" else status)
            result["rows"].append({"id": row.id, "name": row.name, "roll": row.gr_no or "",
                "status": status, "remark": entry.get("remark", ""), "protected": status == "excused"})
        result.update(locked=locked, history=[{
            "id": row.id, "date": str(row.date), "period": row.period,
            **{status: sum(entry["status"] == status for entry in (row.entries or {}).values())
               for status in ("present", "late", "absent", "excused")}}
            for row in records.search(domain + [("submitted_on", "!=", False)], order="date desc, id desc", limit=20)])
        return result

    @api.model
    def save_sop_daily(self, class_key, date, period, entries, submit=False):
        _faculty, _classes, selected = self._mentor_context(class_key)
        day = self._sop_date(date)
        if (not selected or day > fields.Date.context_today(self) or period not in ("FN", "AN", "FULL")
                or not isinstance(entries, dict) or type(submit) is not bool):
            raise ValidationError(_("Choose your class, a current or past date and a valid daily register."))
        batch_id, term_id = map(int, selected["key"].split(":"))
        term = self.env["op.academic.term"].sudo().browse(term_id)
        if not term.term_start_date <= day <= term.term_end_date:
            raise ValidationError(_("Choose a day within the mentorship semester."))
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", [77480, batch_id])
        records, domain = self._sop_daily_records(selected)
        domain += [("date", "=", day)]
        register = records.search(domain + [("period", "=", period)], limit=1)
        if register.submitted_on:
            raise ValidationError(_("This daily register is submitted and locked."))
        overlap = ("period", "!=", "FULL") if period == "FULL" else ("period", "=", "FULL")
        if records.search_count(domain + [overlap, ("submitted_on", "!=", False)]):
            raise ValidationError(_("A submitted full-day or half-day register already covers this session."))
        students = self._sop_daily_roster(selected, day)
        student_keys = {str(row.id) for row in students}
        if not student_keys or set(entries) - student_keys:
            raise AccessError(_("Enter attendance only for your assigned class roster."))
        protected = self._sop_daily_protected(students.ids, day, period)
        values = {}
        for student in students:
            key = str(student.id)
            entry = entries.get(key, {})
            if not isinstance(entry, dict):
                raise ValidationError(_("Enter a valid status and remark."))
            status = entry.get("status", "unmarked")
            remark = entry.get("remark", "")
            if student.id in protected:
                values[key] = {"status": "excused", "remark": ""}
                continue
            if (status not in ("present", "absent", "late", "unmarked") or not isinstance(remark, str)
                    or len(remark) > 500 or (submit and status == "unmarked")):
                raise ValidationError(_("Mark every student before submission and keep remarks within 500 characters."))
            values[key] = {"status": status, "remark": remark.strip()}
        vals = {"entries": values}
        if submit:
            vals.update(submitted_by=self.env.uid, submitted_on=fields.Datetime.now())
        if register:
            register.write(vals)
        else:
            records.create(dict(vals, name=_("Daily attendance · %s", selected["label"]),
                company_id=self.env.company.id, mentor_id=self.env.uid, batch_id=batch_id,
                term_id=term_id, date=day, period=period))
        return True
