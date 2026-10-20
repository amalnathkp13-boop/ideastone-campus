"""Read-only staff attendance dashboard backed by HR attendance and leave records."""

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FacultyAttendanceUI(models.AbstractModel):
    _name = "campus.faculty.attendance.ui"
    _description = "Staff attendance dashboard"

    def _manager(self):
        return self.env.user.has_group("ideastone_erp.group_people") or self.env.user.has_group("base.group_system")

    def _employees(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("An internal staff account is required."))
        domain = [("company_id", "in", [False, self.env.company.id])]
        if not self._manager():
            domain.append(("user_id", "=", self.env.uid))
        return self.env["hr.employee"].sudo().search(domain, order="name, id")

    @api.model
    def get_dashboard(self, employee_id=None, year=None, month=None):
        employees = self._employees()
        today = fields.Date.context_today(self)
        year = int(year or today.year)
        month = int(month or today.month)
        if year < 2000 or year > 2100 or month < 1 or month > 12:
            raise UserError(_("Choose a valid month and year."))
        selected = employees.filtered(lambda record: record.id == int(employee_id or 0))[:1]
        if employee_id and not selected:
            raise AccessError(_("This staff member is outside your permitted scope."))
        if not selected:
            selected = employees.filtered(lambda record: record.user_id.id == self.env.uid)[:1] or employees[:1]
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        departments = sorted({item.department_id.id: {"id": item.department_id.id, "name": item.department_id.name}
                              for item in employees if item.department_id}.values(), key=lambda item: item["name"])
        result = {
            "company": self.env.company.name,
            "staff": [{"id": item.id, "name": item.name, "department_id": item.department_id.id or False}
                      for item in employees],
            "departments": departments,
            "employee_id": selected.id or False,
            "year": year,
            "month": month,
            "month_name": start.strftime("%B"),
            "last_login": "",
            "metrics": {"rate": None, "average_check_in": None, "late_marks": None, "leave_utilization": None},
            "leave_balances": [], "attendance": [], "summary": [], "holidays": [],
            "trend": [], "insights": [],
        }
        if self.env.user.login_date:
            login = fields.Datetime.context_timestamp(self, self.env.user.login_date)
            result["last_login"] = login.strftime("%d %b %Y %I:%M %p")
        if not selected:
            return result

        calendar = selected.resource_calendar_id
        campus_tz = pytz.timezone(calendar.tz or self.env.user.tz or "UTC")

        def local_time(value):
            return pytz.UTC.localize(fields.Datetime.to_datetime(value)).astimezone(campus_tz)

        # Expand the UTC query by a day, then classify entries in the staff work calendar's time zone.
        utc_start = datetime.combine(start - timedelta(days=1), time.min)
        utc_end = datetime.combine(end + timedelta(days=2), time.min)
        entries = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", selected.id),
            ("check_in", ">=", fields.Datetime.to_string(utc_start)),
            ("check_in", "<", fields.Datetime.to_string(utc_end)),
        ], order="check_in asc")
        by_day = defaultdict(list)
        for entry in entries:
            local_in = local_time(entry.check_in)
            if start <= local_in.date() <= end:
                by_day[local_in.date()].append((local_in, local_time(entry.check_out)
                                                 if entry.check_out else None))

        leave_types = self.env["hr.leave.type"].sudo().search([("active", "=", True)], order="sequence, name")
        leave_types = leave_types.filtered(lambda item: not item.company_id or item.company_id == self.env.company)
        allocations = self.env["hr.leave.allocation"].sudo().search([
            ("employee_id", "=", selected.id), ("state", "=", "validate"),
        ])
        approved_leaves = self.env["hr.leave"].sudo().search([
            ("employee_id", "=", selected.id), ("state", "=", "validate"),
            ("request_date_from", "<=", fields.Date.to_string(end)),
            ("request_date_to", ">=", fields.Date.to_string(start)),
        ])
        all_used = self.env["hr.leave"].sudo().search([
            ("employee_id", "=", selected.id), ("state", "=", "validate"),
        ])
        for leave_type in leave_types:
            allocated = sum(allocations.filtered(lambda a: a.holiday_status_id == leave_type).mapped("number_of_days"))
            used = sum(all_used.filtered(lambda l: l.holiday_status_id == leave_type).mapped("number_of_days"))
            balance = round(allocated - used, 2)
            result["leave_balances"].append({"name": leave_type.name, "balance": balance,
                                              "eligible": balance > 0 or leave_type.requires_allocation == "no"})

        calendar_days = {int(item.dayofweek) for item in calendar.attendance_ids} if calendar else set(range(5))
        calendar_leave_model = self.env["resource.calendar.leaves"].sudo()
        holiday_domain = [
            ("date_from", "<", fields.Datetime.to_string(utc_end)),
            ("date_to", ">=", fields.Datetime.to_string(utc_start)),
            ("resource_id", "in", [False, selected.resource_id.id]),
            ("calendar_id", "in", [False, calendar.id]),
        ]
        if "company_id" in calendar_leave_model._fields:
            holiday_domain.append(("company_id", "in", [False, self.env.company.id]))
        calendar_leaves = calendar_leave_model.search(holiday_domain)
        holidays = {}
        for holiday in calendar_leaves:
            if holiday.resource_id:
                continue
            holiday_start = local_time(holiday.date_from).date()
            holiday_end = local_time(holiday.date_to).date()
            day = max(holiday_start, start)
            while day <= min(holiday_end, end):
                holidays[day] = holiday.name
                day += timedelta(days=1)
        result["holidays"] = [{"date": day.strftime("%d/%m/%Y"), "day": day.strftime("%a"),
                               "name": name} for day, name in sorted(holidays.items())]

        leave_by_day = {}
        for leave in approved_leaves:
            day = max(fields.Date.to_date(leave.request_date_from), start)
            last = min(fields.Date.to_date(leave.request_date_to), end)
            while day <= last:
                leave_by_day[day] = leave.holiday_status_id.name
                day += timedelta(days=1)
        totals = defaultdict(int)
        check_minutes = []
        late_marks = 0
        working_elapsed = 0
        weekly = defaultdict(lambda: {"present": 0, "scheduled": 0})
        day = start
        while day <= end:
            if day > today:
                break
            week = (day.day - 1) // 7 + 1
            working = day.weekday() in calendar_days and day not in holidays
            if working:
                working_elapsed += 1
                weekly[week]["scheduled"] += 1
            day_entries = by_day.get(day, [])
            if day_entries:
                status = "Present"
                weekly[week]["present"] += 1
                earliest = min(row[0] for row in day_entries)
                latest = max((row[1] for row in day_entries if row[1]), default=None)
                check_minutes.append(earliest.hour * 60 + earliest.minute)
                schedule_hours = [item.hour_from for item in calendar.attendance_ids
                                  if item.dayofweek == str(day.weekday())] if calendar else []
                scheduled_start = min(schedule_hours) if schedule_hours else None
                late = int(scheduled_start is not None and
                           earliest.hour * 60 + earliest.minute > round(scheduled_start * 60) + 5)
                late_marks += late
                check_in = earliest.strftime("%H:%M")
                check_out = latest.strftime("%H:%M") if latest else "—"
            elif day in leave_by_day:
                status, late, check_in, check_out = "Leave", 0, "—", "—"
            elif day in holidays:
                status, late, check_in, check_out = "Holiday", 0, "—", "—"
            elif not working:
                status, late, check_in, check_out = "Weekly Off", 0, "—", "—"
            else:
                status, late, check_in, check_out = "Absent", 0, "—", "—"
            totals[status] += 1
            result["attendance"].append({"date": day.strftime("%d/%m/%Y"), "day": day.strftime("%a"),
                                          "status": status, "check_in": check_in, "check_out": check_out,
                                          "late": late})
            day += timedelta(days=1)
        result["attendance"].reverse()
        result["summary"] = [{"label": label, "total": totals[label]} for label in
                             ("Present", "Absent", "Late", "On Duty", "Leave", "Weekly Off", "Holiday")]
        result["summary"][2]["total"] = late_marks
        result["summary"].append({"label": "Total", "total": sum(totals.values())})
        allocated_total = sum(allocations.mapped("number_of_days"))
        used_total = sum(all_used.mapped("number_of_days"))
        result["metrics"] = {
            "rate": round(100 * totals["Present"] / working_elapsed) if working_elapsed else None,
            "average_check_in": f"{sum(check_minutes) // len(check_minutes) // 60:02d}:{sum(check_minutes) // len(check_minutes) % 60:02d}" if check_minutes else None,
            "late_marks": late_marks,
            "leave_utilization": round(100 * used_total / allocated_total) if allocated_total else None,
        }
        result["trend"] = [{"label": f"Week {week}", "rate": round(100 * data["present"] / data["scheduled"])
                            if data["scheduled"] else 0} for week, data in sorted(weekly.items())]
        result["insights"] = [
            {"title": "Attendance Trend", "text": f"{result['metrics']['rate']}% attendance across {working_elapsed} scheduled days." if working_elapsed else "No scheduled days in this range yet."},
            {"title": "Check-in Pattern", "text": f"{late_marks} late marks this month." if check_minutes else "No check-ins recorded for this month."},
            {"title": "Upcoming Leave", "text": f"{round(allocated_total - used_total, 2)} allocated leave days remain." if allocated_total else "No leave allocation recorded."},
        ]
        return result
