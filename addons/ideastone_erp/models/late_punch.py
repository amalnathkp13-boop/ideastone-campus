"""Classify the first punch on each scheduled local working day."""

from datetime import datetime, time, timedelta

import pytz

from odoo import fields

LATE_CUTOFF = time(9, 0)
MONTHLY_GRACE_DAYS = 2


def local_bounds(day, timezone):
    start = timezone.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
    end = timezone.localize(datetime.combine(day + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
    return start, end


def late_punch_dates(env, employee, month_start):
    """Return late dates for the whole month, ordered by the first local punch.

    A day is counted once, even if a staff member has multiple attendance records.
    Non-working days, calendar holidays and approved leave do not use the allowance.
    """
    calendar = employee.resource_calendar_id
    timezone = pytz.timezone(calendar.tz or "UTC")
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    start, _ = local_bounds(month_start, timezone)
    end, _ = local_bounds(next_month, timezone)
    attendance = env["hr.attendance"].search([
        ("employee_id", "=", employee.id), ("check_in", ">=", fields.Datetime.to_string(start)),
        ("check_in", "<", fields.Datetime.to_string(end)),
    ], order="check_in asc")
    first_punch = {}
    for entry in attendance:
        local = pytz.UTC.localize(fields.Datetime.to_datetime(entry.check_in)).astimezone(timezone)
        first_punch.setdefault(local.date(), local)

    scheduled = {int(line.dayofweek) for line in calendar.attendance_ids} if calendar else set(range(5))
    holidays = env["resource.calendar.leaves"].search([
        ("date_from", "<", fields.Datetime.to_string(end)),
        ("date_to", ">", fields.Datetime.to_string(start)),
        ("resource_id", "in", [False, employee.resource_id.id]),
        ("calendar_id", "in", [False, calendar.id]),
    ])
    leave = env["hr.leave"].search([
        ("employee_id", "=", employee.id), ("state", "=", "validate"),
        ("request_date_from", "<", fields.Date.to_string(next_month)),
        ("request_date_to", ">=", fields.Date.to_string(month_start)),
    ])
    dates = []
    for day, punch in sorted(first_punch.items()):
        if day.weekday() not in scheduled or punch.time().replace(tzinfo=None) <= LATE_CUTOFF:
            continue
        cutoff_utc = timezone.localize(datetime.combine(day, LATE_CUTOFF)).astimezone(pytz.UTC).replace(tzinfo=None)
        if any(item.date_from <= cutoff_utc < item.date_to for item in holidays):
            continue
        if any(fields.Date.to_date(item.request_date_from) <= day <= fields.Date.to_date(item.request_date_to)
               for item in leave):
            continue
        dates.append(day)
    return dates
