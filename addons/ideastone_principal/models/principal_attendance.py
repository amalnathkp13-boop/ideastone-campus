"""Read-only institutional attendance, scoped to the Principal's active college."""

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

import pytz
from odoo.addons.ideastone_erp.models.late_punch import LATE_CUTOFF
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


def rate(present, held):
    return round(present * 100 / held, 1) if held else None


def minute(value):
    try:
        clock = time.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return clock.hour * 60 + clock.minute


class PrincipalAttendance(models.AbstractModel):
    _name = "ideastone.principal.attendance"
    _description = "Principal attendance oversight"

    def _snapshot_date(self, value, default):
        try:
            return fields.Date.to_date(value) if value else default
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError(_("Enter a valid attendance date.")) from error

    @api.model
    def get_workspace(self, filters=None):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            raise AccessError(_("Only a principal can view institutional attendance."))
        if filters is not None and not isinstance(filters, dict):
            raise ValidationError(_("Invalid attendance filters."))
        filters = filters or {}
        company = self.env.company
        today = self.env["campus.fleet.ui"]._today()
        scope = [("company_id", "=", company.id)]
        years = self.env["op.academic.year"].search(scope, order="start_date desc, id desc")
        year_id = filters.get("year_id") or 0
        department = filters.get("department") or ""
        if type(year_id) is not int or not isinstance(department, str) or len(department) > 40:
            raise ValidationError(_("Choose a valid academic year and department."))
        year = years.filtered(lambda item: item.id == year_id)
        if year_id and not year:
            raise AccessError(_("Choose an academic year in your active college."))
        start = self._snapshot_date(filters.get("date_from"), today.replace(day=1))
        end = self._snapshot_date(filters.get("date_to"), today)
        if start > end or end > today or (end - start).days > 92:
            raise ValidationError(_("Choose up to 93 days ending on or before today."))
        first, last = (max(start, year.start_date), min(end, year.end_date)) if year else (start, end)
        # The Principal sees company-wide summaries. Each elevated read below has an
        # explicit active-college domain, and private notes never leave this service.
        service = self.sudo().with_company(company)
        departments = service._departments()
        if department and department not in {item["key"] for item in departments}:
            raise ValidationError(_("Choose a department in your active college."))
        staff, students, fleet, leave, correction_count = [], [], [], {}, 0
        if first <= last:
            staff, leave = service._staff_rows(first, last, today, department)
            students, correction_count = service._student_rows(first, last, year, department)
            fleet = service._fleet_rows(last, year)
        timezone = self.env.user.tz or company.partner_id.tz or "UTC"
        login = self.env.user.login_date
        return {
            "company": company.name,
            "year_id": year_id,
            "years": [{"id": item.id, "name": item.name} for item in years],
            "departments": departments,
            "effective_from": str(first), "date_from": str(start), "date_to": str(end), "as_of": str(last), "today": str(today),
            "last_login": fields.Datetime.context_timestamp(self.with_context(tz=timezone), login).strftime("%d %b %Y · %I:%M %p") if login else "",
            "threshold": company.campus_attendance_threshold,
            "staff": staff, "students": students, "fleet": fleet, "leave": leave,
            "corrections": correction_count,
        }

    def _departments(self):
        company_id = self.env.company.id
        result = [{"key": f"a:{row.id}", "name": row.name} for row in
                  self.env["op.department"].search([("company_id", "=", company_id)])]
        result += [{"key": f"h:{row.id}", "name": row.name} for row in
                   self.env["hr.department"].search([("company_id", "=", company_id)])]
        result.append({"key": "unassigned", "name": _("Unassigned department")})
        return sorted(result, key=lambda item: (item["name"].casefold(), item["key"]))

    def _staff_rows(self, start, end, today, department):
        company = self.env.company
        employees = self.env["hr.employee"].search([("company_id", "=", company.id)], order="name, id")
        linked = self.env["op.faculty"].search([
            ("company_id", "=", company.id), ("emp_id", "in", employees.ids),
        ])
        faculty = {row.emp_id.id: row for row in linked}
        groups = {}
        for employee in employees:
            teacher = faculty.get(employee.id)
            academic = teacher.main_department_id if teacher else self.env["op.department"]
            hr = employee.department_id
            key = f"a:{academic.id}" if academic.company_id == company else f"h:{hr.id}" if hr.company_id == company else "unassigned"
            groups[employee.id] = (key, academic.name if key.startswith("a:") else hr.name if key.startswith("h:") else _("Unassigned department"))
        employees = employees.filtered(lambda employee: not department or groups[employee.id][0] == department)
        zones = {emp.id: pytz.timezone(emp.resource_calendar_id.tz or company.partner_id.tz or "UTC") for emp in employees}
        now = fields.Datetime.now()
        punches = defaultdict(list)
        for entry in self.env["hr.attendance"].search([
            ("employee_id", "in", employees.ids),
            ("check_in", ">=", datetime.combine(start - timedelta(days=1), time.min)),
            ("check_in", "<", datetime.combine(end + timedelta(days=2), time.min)),
        ], order="check_in, id"):
            employee_id = entry.employee_id.id
            day = pytz.UTC.localize(entry.check_in).astimezone(zones[employee_id]).date()
            if start <= day <= end:
                punches[employee_id, day].append(entry)
        leaves = self.env["hr.leave"].search([
            ("employee_id", "in", employees.ids), ("state", "in", ["confirm", "validate1", "validate"]),
            ("request_date_from", "<=", end), ("request_date_to", ">=", start),
        ])
        leave_days = defaultdict(set)
        approved = leaves.filtered(lambda row: row.state == "validate")
        for row in approved:
            first, last = max(start, row.request_date_from), min(end, row.request_date_to)
            leave_days[row.employee_id.id].update(first + timedelta(days=i) for i in range((last - first).days + 1))
        holidays = self.env["resource.calendar.leaves"].search([
            ("company_id", "in", [False, company.id]), ("resource_id", "=", False),
            ("calendar_id", "in", [False, *employees.resource_calendar_id.ids]),
            ("date_from", "<", datetime.combine(end + timedelta(days=2), time.min)),
            ("date_to", ">", datetime.combine(start - timedelta(days=1), time.min)),
        ])
        holiday_windows = defaultdict(list)
        for row in holidays:
            holiday_windows[row.calendar_id.id].append((row.date_from, row.date_to))
        result = []
        scheduled_days = 0
        for employee in employees:
            zone = zones[employee.id]
            teacher = faculty.get(employee.id)
            key, name = groups[employee.id]
            calendar = employee.resource_calendar_id
            local_now = pytz.UTC.localize(now).astimezone(zone)
            workdays = defaultdict(list)
            for slot in calendar.attendance_ids:
                if slot.day_period != "lunch" and (not slot.resource_id or slot.resource_id == employee.resource_id):
                    workdays[int(slot.dayofweek)].append(slot)
            for offset in range((end - start).days + 1):
                day = start + timedelta(days=offset)
                records = punches[employee.id, day]
                week = self.env["resource.calendar.attendance"].get_week_type(day)
                schedule = [slot for slot in workdays[day.weekday()]
                            if (not calendar.two_weeks_calendar or int(slot.week_type or 0) == week)
                            and (not slot.date_from or slot.date_from <= day)
                            and (not slot.date_to or slot.date_to >= day)]
                cutoff = zone.localize(datetime.combine(day, LATE_CUTOFF)).astimezone(pytz.UTC).replace(tzinfo=None)
                holiday = any(left <= cutoff < right for left, right in
                              holiday_windows[False] + holiday_windows.get(calendar.id, []))
                if not records and not (schedule and not holiday) and day not in leave_days[employee.id]:
                    continue
                punch = pytz.UTC.localize(records[0].check_in).astimezone(zone) if records else None
                departure = records[-1].check_out if records else None
                elapsed = day < local_now.date() or day == local_now.date() and bool(
                    schedule and local_now.hour + local_now.minute / 60 >= max(line.hour_to for line in schedule))
                on_leave = day in leave_days[employee.id]
                scheduled_days += int(bool(schedule and not holiday and (elapsed or punch or on_leave)))
                delay = max(0, punch.hour * 60 + punch.minute - LATE_CUTOFF.hour * 60) if punch and schedule and not holiday and not on_leave else 0
                status = ("Late" if delay else "Present") if punch else "Leave" if on_leave else "Absent" if elapsed else ""
                if not status or day > today:
                    continue
                result.append({
                    "key": f"{employee.id}:{day}", "person_id": employee.id, "date": str(day),
                    "name": employee.name, "number": (teacher.campus_staff_code if teacher else "") or employee.barcode or "",
                    "department_key": key, "department": name, "category": "Teaching" if teacher else "Non-teaching",
                    "designation": (teacher.campus_designation if teacher else "") or employee.job_id.name or employee.job_title or "",
                    "check_in": punch.strftime("%H:%M") if punch else "",
                    "check_out": pytz.UTC.localize(departure).astimezone(zone).strftime("%H:%M") if departure else "",
                    "hours": round(sum(row.worked_hours for row in records), 2) if records else None,
                    "status": status, "delay": delay, "missing": bool(punch and not departure and elapsed),
                    "source": _("Staff check-in") if punch else _("Approved leave") if on_leave else _("Scheduled working day"),
                })
        return result, {
            "pending": len(leaves - approved), "approved": len(approved),
            "utilization": rate(sum(row["status"] == "Leave" for row in result), scheduled_days),
        }

    def _student_rows(self, start, end, year, department):
        scope = [("company_id", "=", self.env.company.id)]
        batch_scope = list(scope)
        if year:
            batch_scope.append(("campus_year_id", "=", year.id))
        if department == "unassigned":
            batch_scope.append(("course_id.department_id", "=", False))
        elif department.startswith("a:") and department[2:].isdigit():
            batch_scope.append(("course_id.department_id", "=", int(department[2:])))
        elif department:
            return [], 0
        batches = self.env["op.batch"].search(batch_scope)
        source = scope + [("attendance_date", ">=", start), ("attendance_date", "<=", end),
                          ("batch_id", "in", batches.ids)]
        # Limit the source, not the resulting rates: return an actionable error instead
        # of silently calculating totals or shortages from a partial register.
        line_model = self.env["op.attendance.line"]
        lines = line_model.search(source + [("attendance_id.state", "=", "done"),
            "|", ("attendance_id.session_id", "=", False), ("attendance_id.session_id.state", "!=", "cancel")],
            limit=200001)
        if len(lines) > 200000:
            raise ValidationError(_("Choose a shorter date range or a department to load attendance."))
        day_marks = defaultdict(set)
        overall = defaultdict(Counter)
        policy = self.env.company.campus_excused_policy
        for line in lines:
            if line.student_id.company_id != self.env.company:
                continue
            status = line.campus_status
            day_marks[line.student_id.id, line.batch_id.id, line.attendance_date].add(status)
            if status != "excused" or policy != "exclude":
                stats = overall[line.student_id.id, line.batch_id.id]
                stats["held"] += 1
                stats["present"] += int(status in ("present", "late") or (status == "excused" and policy == "present"))
        registers = self.env["campus.faculty.daily.register"].search(scope + [
            ("batch_id", "in", batches.ids), ("date", ">=", start), ("date", "<=", end), ("submitted_on", "!=", False),
        ])
        daily = defaultdict(set)
        for register in registers:
            for student_key, entry in (register.entries or {}).items():
                daily[int(student_key), register.batch_id.id, register.date].add(entry["status"])
        # Use the submitted mentorship register for daily status when it exists.
        # Subject lines remain the source for subject-wise attendance percentages.
        mark_keys = day_marks.keys() | daily.keys()
        students = {student.id: student for student in self.env["op.student"].search(scope + [
            ("id", "in", sorted({student_id for student_id, _batch, _day in mark_keys})),
        ])}
        approved_leaves = self.env["campus.student.leave"].search(scope + [
            ("student_id", "in", list(students)), ("state", "=", "approved"),
            ("date", "<=", end), ("deadline", ">=", start),
        ])
        leave_days = defaultdict(set)
        for leave in approved_leaves:
            first, last = max(start, leave.date), min(end, leave.deadline)
            leave_days[leave.student_id.id].update(first + timedelta(days=i) for i in range((last - first).days + 1))
        batch_map = {batch.id: batch for batch in batches}
        result = []
        for student_id, batch_id, day in sorted(mark_keys):
            student = students.get(student_id)
            if not student:
                continue
            batch = batch_map[batch_id]
            course = batch.course_id
            dept = course.department_id
            marks = daily.get((student_id, batch_id, day)) or day_marks[student_id, batch_id, day]
            status = ("Late" if "late" in marks else "Present" if "present" in marks else
                      ("Leave" if day in leave_days[student_id] else "On Duty") if "excused" in marks else "Absent")
            stats = overall[student_id, batch_id]
            result.append({
                "key": f"{student_id}:{batch_id}:{day}", "person_id": student_id, "date": str(day),
                "name": student.name, "number": student.gr_no or "", "department_key": f"a:{dept.id}" if dept else "unassigned",
                "department": dept.name or _("Unassigned department"), "programme": course.name,
                "year": batch.campus_year_id.name or _("Unassigned academic year"), "section": batch.name,
                "class_key": batch.id, "status": status, "rate": rate(stats["present"], stats["held"]),
                "present": stats["present"], "held": stats["held"],
                "source": _("Mentorship register") if (student_id, batch_id, day) in daily else _("Class register"),
                "check_in": "",
            })
        correction_count = self.env["op.attendance.sheet"].search_count(source + [
            ("state", "in", ["draft", "start"]), ("campus_correction_reason", "!=", False),
        ])
        return result, correction_count

    def _fleet_rows(self, day, year):
        domain = [("company_id", "=", self.env.company.id), ("kind", "=", "arrival"), ("date", "=", day)]
        if year:
            domain.append(("route_id.year_id", "=", year.id))
        events = self.env["campus.fleet.event"].search(domain)
        allocations = self.env["campus.transport.allocation"].search([
            ("company_id", "=", self.env.company.id), ("state", "=", "approved"), ("route_id", "in", events.route_id.ids),
        ])
        rider_counts = Counter(row.route_id.id for row in allocations)
        result = []
        for event in events:
            route = event.route_id
            if route.company_id != self.env.company:
                continue
            expected, actual = minute(route.fleet_expected_arrival), minute(event.arrival)
            if expected is None or actual is None or actual <= expected:
                continue
            result.append({
                "id": event.id, "route": route.name, "vehicle": route.vehicle_registration,
                "expected": route.fleet_expected_arrival, "actual": event.arrival, "delay": actual - expected,
                "students": rider_counts[route.id], "staff": route.staff_riders,
            })
        return result
