"""Owner attendance monitoring. Source attendance is never edited here."""

from calendar import monthrange
from collections import defaultdict
from datetime import datetime

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


def owner_access(env):
    if not env.user.has_group("base.group_user") or not any(env.user.has_group(group) for group in
            ("ideastone_erp.group_mvp_owner", "base.group_system")):
        raise AccessError(_("An owner or administrator account is required."))


class OwnerAttendanceNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        modules = super()._owner_modules()
        if self.env.user.has_group("ideastone_erp.group_mvp_owner") or self.env.user.has_group("base.group_system"):
            return [(key, label, icon, [("Attendance overview", "action_owner_attendance_overview")] + entries
                if key == "attendance" else entries) for key, label, icon, entries in modules]
        return modules

    def _client_action_models(self):
        return dict(super()._client_action_models(), action_owner_attendance_overview="op.department")


class AttendanceReviewRequest(models.Model):
    _inherit = "campus.service.request"

    attendance_review_mode = fields.Selection([("staff", "Staff"), ("student", "Student")], index=True, copy=False)
    attendance_review_issue = fields.Char(index=True, copy=False)
    attendance_review_department = fields.Char(copy=False)
    attendance_review_assignee_id = fields.Many2one("res.users", check_company=True, copy=False, tracking=True)
    attendance_review_escalated = fields.Boolean(copy=False, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(any(key.startswith("attendance_review_") for key in vals) for vals in vals_list):
            owner_access(self.env)
        return super().create(vals_list)

    def write(self, vals):
        if any(key.startswith("attendance_review_") for key in vals):
            owner_access(self.env)
        return super().write(vals)


class OwnerAttendanceUI(models.AbstractModel):
    _name = "campus.owner.attendance.ui"
    _description = "Owner institutional attendance overview"

    def _records(self, model, domain):
        self.env[model].check_access_rights("read")
        return self.env["campus.dashboard"]._mvp_records(model, domain)

    def _period(self, mode, month):
        owner_access(self.env)
        today = fields.Date.context_today(self)
        if mode not in ("staff", "student") or not isinstance(month, (str, type(None))):
            raise ValidationError(_("Choose a valid attendance category and month."))
        try:
            start = datetime.strptime(month or today.strftime("%Y-%m"), "%Y-%m").date()
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose a valid attendance month.")) from exc
        if not 2000 <= start.year <= 2100 or start > today:
            raise ValidationError(_("Choose a recorded month, up to the current month."))
        return today, start, min(today, start.replace(day=monthrange(start.year, start.month)[1]))

    def _summary(self, lines):
        rows = self.env["campus.dashboard"]._attendance_rows(lines)
        held, present = sum(row["sessions"] for row in rows), sum(row["present"] for row in rows)
        return {"held": held, "present": present, "rate": round(present * 100 / held, 1) if held else None,
            "below": bool(held and present * 100 < self.env.company.campus_attendance_threshold * held), "subjects": rows}

    def _staff(self, today, start):
        company = self.env.company
        employees = self._records("hr.employee", [("company_id", "=", company.id), ("active", "=", True)])
        for model in ("hr.attendance", "hr.leave", "resource.calendar.leaves"):
            self.env[model].check_access_rights("read")
        faculty = self._records("op.faculty", [("company_id", "=", company.id), ("emp_id", "in", employees.ids)])
        academic = {person.emp_id.id: person.main_department_id for person in faculty if person.main_department_id.company_id == company}
        ui = self.env["campus.faculty.attendance.ui"]
        result = []
        months = [fields.Date.subtract(start, months=n) for n in reversed(range(4))]
        for employee in employees:
            department = academic.get(employee.id)
            key = f"a:{department.id}" if department else f"h:{employee.department_id.id}" if employee.department_id else "unassigned"
            name = department.name if department else employee.department_id.name or _("Unassigned department")
            data = {month: ui.get_dashboard(employee.id, month.year, month.month) for month in set(months + [today.replace(day=1)])}
            current = data[today.replace(day=1)]
            day = next((row for row in current["attendance"] if row["date"] == today.strftime("%d/%m/%Y")), {})
            schedule = employee.resource_calendar_id.attendance_ids.filtered(lambda row: row.dayofweek == str(today.weekday()))
            local_now = fields.Datetime.context_timestamp(self.with_context(tz=employee.resource_calendar_id.tz or "UTC"), fields.Datetime.now())
            elapsed = bool(schedule and (local_now.date() > today or (local_now.date() == today
                and local_now.hour + local_now.minute / 60 >= max(schedule.mapped("hour_to")))))
            scheduled = bool(schedule and today.strftime("%d/%m/%Y") not in {row["date"] for row in current["holidays"]})
            present, leave = day.get("status") == "Present", day.get("status") == "Leave"
            absent = bool(scheduled and elapsed and not present and not leave)
            missing = bool(present and elapsed and day.get("check_out") == "—")
            status = "Missing punch" if missing else "Delayed arrival" if day.get("late") else "Present" if present else "Approved leave" if leave else "Needs verification" if absent else "Awaiting check-in" if scheduled else "Not scheduled"
            result.append({"id": employee.id, "name": employee.name, "department_key": key, "department": name,
                "scheduled": int(scheduled), "present": int(present), "leave": int(leave), "absent": int(absent),
                "late": int(bool(day.get("late"))), "missing": int(missing), "status": status,
                "history": data[start]["attendance"], "months": [{"label": month.strftime("%Y-%m"),
                    "present": sum(row["status"] == "Present" for row in data[month]["attendance"]),
                    "held": sum(row["status"] in {"Present", "Absent"} for row in data[month]["attendance"])} for month in months]})
        return result

    def _students(self, today, start, end):
        dashboard = self.env["campus.dashboard"]
        company = [("company_id", "=", self.env.company.id)]
        enrolments = self._records("op.student.course", company + [("state", "=", "running"), ("student_id.active", "=", True),
            ("campus_date_from", "<=", end), "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", start)])
        batches = enrolments.batch_id.filtered(lambda batch: batch.company_id == self.env.company)
        filters = dashboard._mvp_filters({"date_from": str(fields.Date.subtract(start, months=3)), "date_to": str(end)})
        lines = self._records(*dashboard._mvp_source("attendance", filters)).filtered(lambda row: row.batch_id in batches and row.student_id in enrolments.student_id)
        selected = lines.filtered(lambda row: start <= row.attendance_date <= end)
        filters["date_from"] = start
        pending = self._records(*dashboard._admin_source("attendance_pending", filters))
        result = []
        for batch in batches.sorted("name"):
            department = batch.course_id.department_id
            if department and department.company_id != self.env.company:
                continue
            students = enrolments.filtered(lambda row, batch=batch: row.batch_id == batch).student_id
            class_lines = selected.filtered(lambda row, batch=batch: row.batch_id == batch)
            people = [{"id": student.id, "name": student.name, "roll": student.gr_no or "—",
                **self._summary(class_lines.filtered(lambda row, student=student: row.student_id == student))}
                for student in students.sorted("name")]
            result.append({"id": batch.id, "name": batch.name, "department_key": f"a:{department.id}" if department else "unassigned",
                "department": department.name or _("Unassigned department"), "students": people,
                "pending": len(pending.filtered(lambda row, batch=batch: row.batch_id == batch)), **self._summary(class_lines)})
        return result, lines

    def _reviews(self, mode, department):
        domain = [("company_id", "=", self.env.company.id), ("attendance_review_mode", "=", mode)]
        if department:
            domain.append(("attendance_review_department", "=", department))
        records = self._records("campus.service.request", domain).sorted("id", reverse=True)
        return [{"id": row.id, "issue": row.attendance_review_issue, "name": row.name,
            "department": row.attendance_review_department, "assignee": row.attendance_review_assignee_id.name,
            "due": str(row.date_to or ""), "note": row.description,
            "status": "Closed" if row.state in {"done", "cancelled"} else "In progress" if row.state == "approved"
                else "Escalated" if row.attendance_review_escalated else "Assigned"}
            for row in records]

    @api.model
    def get_dashboard(self, mode="staff", month=None, department=""):
        today, start, end = self._period(mode, month)
        if not isinstance(department, str):
            raise ValidationError(_("Choose a valid department."))
        staff = self._staff(today, start) if mode == "staff" else []
        classes, lines = self._students(today, start, end) if mode == "student" else ([], self.env["op.attendance.line"])
        grouped = {}
        for item in staff if mode == "staff" else classes:
            key = item["department_key"]
            group = grouped.setdefault(key, {"key": key, "name": item["department"], "staff": [], "classes": [],
                **dict.fromkeys(["scheduled", "present", "leave", "absent", "late", "missing", "pending", "held", "below", "students"], 0)})
            group["staff" if mode == "staff" else "classes"].append(item)
            if mode == "staff":
                for field in ("scheduled", "present", "leave", "absent", "late", "missing"):
                    group[field] += item[field]
            else:
                for field in ("held", "present", "pending"):
                    group[field] += item[field]
                group["students"] += len(item["students"])
                group["below"] += sum(row["below"] for row in item["students"])
        choices = [{"key": key, "name": row["name"]} for key, row in sorted(grouped.items(), key=lambda pair: pair[1]["name"])]
        if department and department not in grouped:
            raise AccessError(_("This department is outside your attendance scope."))
        groups = [row for row in grouped.values() if not department or row["key"] == department]
        issues = []
        for group in groups:
            denominator = max(0, group["scheduled"] - group["leave"]) if mode == "staff" else group["held"]
            group["rate"] = round(group["present"] * 100 / denominator, 1) if denominator else None
            specs = [("missing", "Missing punch verification", "HR"), ("absent", "Unverified staff absence", "HR"),
                ("late", "Delayed arrival review", "HR")] if mode == "staff" else [("pending", "Unsubmitted sessions", "HOD"), ("below", "Attendance shortage review", "HOD")]
            for field, title, target in specs:
                if group[field]:
                    issues.append({"id": f"{mode}:{today if mode == 'staff' else start}:{group['key']}:{field}", "department": group["key"],
                        "title": title, "description": f"{group['name']} · {group[field]} records to review", "target": target})
        selected_staff = [row for group in groups for row in group["staff"]]
        selected_keys = {row["key"] for row in groups}
        buckets = defaultdict(lambda: {"held": 0, "present": 0})
        if mode == "staff":
            for person in selected_staff:
                for item in person["history"]:
                    day = datetime.strptime(item["date"], "%d/%m/%Y").date()
                    if item["status"] in {"Present", "Absent"}:
                        bucket = buckets[f"Week {(day.day - 1) // 7 + 1}"]
                        bucket["held"] += 1
                        bucket["present"] += item["status"] == "Present"
            monthly = defaultdict(lambda: {"held": 0, "present": 0})
            for person in selected_staff:
                for row in person["months"]:
                    for field in ("held", "present"):
                        monthly[row["label"]][field] += row[field]
        else:
            monthly = defaultdict(lambda: {"held": 0, "present": 0})
            for line in lines:
                key = f"a:{line.course_id.department_id.id}" if line.course_id.department_id else "unassigned"
                if key not in selected_keys:
                    continue
                summary = self._summary(line)
                for field in ("held", "present"):
                    monthly[str(line.attendance_date)[:7]][field] += summary[field]
                    if start <= line.attendance_date <= end:
                        buckets[f"Week {(line.attendance_date.day - 1) // 7 + 1}"][field] += summary[field]
        def trend(values):
            return [{"label": label, "rate": round(row["present"] * 100 / row["held"], 1) if row["held"] else None}
                for label, row in sorted(values.items())]
        totals = {field: sum(row[field] for row in groups) for field in
            ("scheduled", "present", "leave", "absent", "late", "missing", "pending", "held", "below", "students")}
        denominator = totals["scheduled"] - totals["leave"] if mode == "staff" else totals["held"]
        totals["rate"] = round(totals["present"] * 100 / denominator, 1) if denominator > 0 else None
        reviews = self._reviews(mode, department)
        review_ids = [row["id"] for row in reviews]
        review_names = {row["id"]: row["name"] for row in reviews}
        audit = self._records("campus.mvp.audit", [("company_id", "=", self.env.company.id),
            ("model_name", "=", "campus.service.request"), ("record_id", "in", review_ids)]).sorted("id", reverse=True)
        assignees = self._assignees(mode, department) if department else []
        return {"today": str(today), "month": start.strftime("%Y-%m"), "threshold": self.env.company.campus_attendance_threshold,
            "choices": choices, "departments": sorted(groups, key=lambda row: row["name"]), "totals": totals,
            "issues": issues, "reviews": reviews, "weekly": trend(buckets), "monthly": trend(monthly), "assignees": assignees,
            "audit": [{"id": row.id, "name": row.name, "subject": review_names.get(row.record_id, ""), "reason": row.reason or "", "actor": row.actor_id.name,
                "at": str(fields.Datetime.context_timestamp(self, row.create_date))} for row in audit[:100]]}

    def _assignees(self, mode, department):
        users = self.env["res.users"].search([("active", "=", True), ("share", "=", False), ("company_ids", "in", self.env.company.ids)])
        if mode == "staff":
            users = users.filtered(lambda user: user.has_group("ideastone_erp.group_people"))
        else:
            dept_id = int(department[2:]) if department.startswith("a:") else 0
            placements = self._records("op.student.course", [("company_id", "=", self.env.company.id),
                ("state", "=", "running"), ("course_id.department_id", "=", dept_id)])
            mentors = self._records("campus.student.leave.routing", [("company_id", "=", self.env.company.id),
                ("active", "=", True), ("student_id", "in", placements.student_id.ids)]).advisor_id
            users = users.filtered(lambda user: user in mentors or (dept_id and user.dept_id.id == dept_id and (
                user.has_group("ideastone_erp.group_od_hod_approver") or user.has_group("ideastone_erp.group_mvp_hod"))))
        return [{"id": user.id, "name": user.name} for user in users]

    @api.model
    def review_options(self, mode, month, issue_id):
        data = self.get_dashboard(mode, month)
        issue = next((row for row in data["issues"] if row["id"] == issue_id), None)
        if not issue:
            raise ValidationError(_("This attendance issue is no longer in the current scope."))
        return self._assignees(mode, issue["department"])

    @api.model
    def assign_review(self, mode, month, issue_id, assignee_id, due, note):
        data = self.get_dashboard(mode, month)
        issue = next((row for row in data["issues"] if row["id"] == issue_id), None)
        if not issue or type(assignee_id) is not int or assignee_id not in [row["id"] for row in self._assignees(mode, issue["department"])]:
            raise AccessError(_("Choose an authorized HR manager or the department HOD for a current issue."))
        try:
            deadline = fields.Date.to_date(due) if isinstance(due, str) else None
        except ValueError as exc:
            raise ValidationError(_("Choose a valid review deadline.")) from exc
        if not deadline or deadline < fields.Date.context_today(self) or not isinstance(note, str) or not 1 <= len(note.strip()) <= 350:
            raise ValidationError(_("Enter instructions (up to 350 characters) and a deadline from today onwards."))
        source = self.env["campus.service.request"]
        source.check_access_rights("create")
        self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [self.env.company.id])
        existing = source.search([("company_id", "=", self.env.company.id), ("attendance_review_issue", "=", issue_id),
            ("state", "not in", ["done", "cancelled"])], limit=1)
        if existing:
            return existing.id
        department_name = next(row["name"] for row in data["departments"] if row["key"] == issue["department"])
        record = source.create({"name": f"{issue['title']} · {department_name}", "kind": "work", "company_id": self.env.company.id,
            "date_to": deadline, "description": note.strip(), "attendance_review_mode": mode,
            "attendance_review_issue": issue_id, "attendance_review_department": issue["department"],
            "attendance_review_assignee_id": assignee_id})
        record.action_submit()
        record.activity_schedule("mail.mail_activity_data_todo", user_id=assignee_id, date_deadline=deadline, summary=record.name)
        self.env["campus.mvp.audit"]._log(record, "Attendance review assigned", note.strip(), {"assignee_id": assignee_id, "issue": issue_id})
        return record.id

    @api.model
    def escalate_review(self, review_id):
        owner_access(self.env)
        if type(review_id) is not int or not 1 <= review_id <= 2147483647:
            raise ValidationError(_("Choose a valid attendance review."))
        record = self.env["campus.service.request"].search([("id", "=", review_id), ("company_id", "=", self.env.company.id),
            ("attendance_review_mode", "!=", False)], limit=1)
        if not record:
            raise AccessError(_("This review is outside your college."))
        record._lock()
        if record.state in {"approved", "done", "cancelled"}:
            raise ValidationError(_("This review is already being processed or is closed."))
        if not record.attendance_review_escalated:
            record.attendance_review_escalated = True
            record.message_post(body=_("Owner escalated this attendance review. Verify the source records using the authorized workflow."))
            self.env["campus.mvp.audit"]._log(record, "Attendance review escalated")
        return True
