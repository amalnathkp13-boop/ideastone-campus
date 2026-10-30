from collections import defaultdict
from datetime import datetime, timedelta
from textwrap import shorten

import pytz
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext

from odoo import _, api, fields, models

from .late_punch import late_punch_dates, local_bounds


class AdminOverviewUI(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _admin_events_allowed(self):
        return all(self.env[model].check_access_rights("read", raise_exception=False)
                   for model in ("event.event", "event.stage", "event.type", "res.partner"))

    def _admin_staff_punches(self):
        source = self.env["hr.attendance"]
        allowed = self.env["campus.faculty.attendance.ui"]._manager() and all(
            self.env[model].check_access_rights("read", raise_exception=False)
            for model in ("hr.attendance", "hr.employee", "hr.leave", "resource.calendar.leaves"))
        if not allowed:
            return source.browse(), source.browse(), False
        today = fields.Date.context_today(self)
        employees = self._mvp_records("hr.employee", [("company_id", "=", self.env.company.id), ("active", "=", True)])
        punches = self._mvp_records("hr.attendance", [("employee_id", "in", employees.ids),
            ("check_in", ">=", today - timedelta(days=1)), ("check_in", "<", today + timedelta(days=2))])
        present, delayed = source.browse(), source.browse()
        for employee in employees:
            zone = pytz.timezone(employee.resource_calendar_id.tz or "UTC")
            start, end = local_bounds(today, zone)
            entries = punches.filtered(lambda row, employee=employee, start=start, end=end:
                row.employee_id == employee and start <= row.check_in < end)
            present |= entries
            # Reuse the payroll policy, including first punch, holidays and approved leave.
            if entries and today in late_punch_dates(self.env, employee, today.replace(day=1)):
                delayed |= entries
        return present, delayed, True

    def _admin_source(self, kind, filters):
        company = [("company_id", "=", self.env.company.id)]
        today, now = fields.Date.context_today(self), fields.Datetime.now()
        if kind in {"staff_present", "staff_delayed"}:
            present, delayed, allowed = self._admin_staff_punches()
            if not allowed:
                raise AccessError(_("Staff attendance reporting access is required."))
            return "hr.attendance", [("employee_id.company_id", "=", self.env.company.id),
                ("id", "in", (present if kind == "staff_present" else delayed).ids)]
        if kind == "fleet":
            return "campus.transport.route", company + ([("year_id", "=", filters["year_id"])] if filters["year_id"] else
                [("year_id.start_date", "<=", today), ("year_id.end_date", ">=", today)])
        if kind == "decisions":
            return "campus.service.request", company + [("state", "=", "submitted"), ("amount", ">", 0)]
        if kind in {"services", "overdue_services"}:
            domain = company + [("state", "not in", ["done", "cancelled", "rejected"])]
            if kind == "overdue_services":
                domain += [("date_to", "<", today)]
            return "campus.service.request", domain
        if kind == "events":
            if not self._admin_events_allowed():
                return "event.event", company + [("id", "=", False)]
            return "event.event", company + [("active", "=", True), ("stage_id.pipe_end", "=", False),
                ("date_end", ">=", now), ("date_begin", "<", now + timedelta(days=90))]
        if kind == "overdue_dues":
            rows = self._mvp_report_rows("dues", filters, self._mvp_records(*self._mvp_source("dues", filters)))
            return "account.move", company + [("id", "in", [row["id"] for row in rows if row["days_overdue"]])]
        if kind == "attendance_pending":
            domain = company + [("state", "!=", "cancel"), ("end_datetime", "<=", now),
                ("start_datetime", ">=", filters["date_from"]), ("start_datetime", "<", filters["date_to"] + timedelta(days=1))]
            if filters["year_id"]:
                domain.append(("batch_id.campus_year_id", "=", filters["year_id"]))
            for key in ("course_id", "batch_id", "faculty_id", "subject_id"):
                if filters[key]:
                    domain.append((key, "=", filters[key]))
            sessions = self._mvp_records("op.session", domain)
            sheets = self._mvp_records("op.attendance.sheet", company + [("session_id", "in", sessions.ids), ("state", "=", "done")])
            # A caller without sheet access cannot infer which registers are missing.
            if not self.env["op.attendance.sheet"].check_access_rights("read", raise_exception=False):
                sessions = sessions.browse()
            return "op.session", company + [("id", "in", (sessions - sheets.session_id).ids)]
        raise ValidationError(_("Unknown overview register."))

    @api.model
    def get_owner_overview_action(self, kind, filters=None, event_id=None):
        f = self._mvp_filters(filters)
        model, domain = self._admin_source("events" if kind == "create_event" else kind, f)
        if model == "event.event" and not self._admin_events_allowed():
            raise AccessError(_("Event calendar access is required."))
        source = self.env[model]
        source.check_access_rights("read")
        context = {"default_company_id": self.env.company.id, "campus_module": "home"}
        names = {"staff_present": _("Present staff"), "staff_delayed": _("Delayed arrivals"), "fleet": _("Fleet (buses)")}
        action = {"type": "ir.actions.act_window", "name": names.get(kind, _("Event Management") if model == "event.event" else _("Overview follow-up")),
                  "res_model": model, "view_mode": "calendar,tree,form" if model == "event.event" else "tree,form",
                  "views": [(False, mode) for mode in (["calendar", "tree", "form"] if model == "event.event" else ["tree", "form"])],
                  "domain": domain, "context": context}
        if kind == "create_event":
            source.check_access_rights("create")
            action.update(view_mode="form", views=[(False, "form")])
        elif event_id is not None:
            if kind not in {"events", "decisions"} or isinstance(event_id, bool) or not isinstance(event_id, int) or not 1 <= event_id <= 2147483647:
                raise ValidationError(_("Choose a valid overview record."))
            event = source.search(domain + [("id", "=", event_id)], limit=1)
            if not event:
                raise AccessError(_("This record is outside the active college or overview scope."))
            action.update(view_mode="form", views=[(False, "form")], res_id=event.id)
        return action

    @api.model
    def get_owner_metrics(self, filters=None):
        data = super().get_owner_metrics(filters)
        f = self._mvp_filters(filters)
        today, now = fields.Date.context_today(self), fields.Datetime.now()
        attendance = self._mvp_records(*self._mvp_source("attendance", f))
        admissions = self._mvp_records(*self._mvp_source("admissions", f))
        monthly = defaultdict(lambda: {"present": 0, "sessions": 0, "applications": 0, "enrolled": 0})
        departments = defaultdict(lambda: {"present": 0, "sessions": 0})
        for line in attendance:
            if line.excused and self.env.company.campus_excused_policy == "exclude":
                continue
            present = int(line.present or line.late or (line.excused and self.env.company.campus_excused_policy == "present"))
            for bucket in (monthly[str(line.attendance_date)[:7]], departments[line.course_id.department_id.name or _("Unassigned department")]):
                bucket["sessions"] += 1
                bucket["present"] += present
        for application in admissions:
            bucket = monthly[str(application.application_date)[:7]]
            bucket["applications"] += 1
            bucket["enrolled"] += application.campus_stage == "enrolled"
        activity = [{"label": month, "attendance": round(v["present"] * 100 / v["sessions"], 1) if v["sessions"] else None,
                     "conversion": round(v["enrolled"] * 100 / v["applications"], 1) if v["applications"] else None}
                    for month, v in sorted(monthly.items())]
        department_rows = [{"label": label, "value": round(v["present"] * 100 / v["sessions"], 1)} for label, v in departments.items()]
        department_rows.sort(key=lambda row: (row["value"], row["label"]))
        threshold = self.env.company.campus_attendance_threshold
        services = self._mvp_records(*self._admin_source("services", f))
        overdue_services = services.filtered(lambda r: r.date_to and r.date_to < today)
        pending = self._mvp_records(*self._admin_source("attendance_pending", f))
        invoices = self._mvp_records(*self._mvp_source("dues", f))
        dues = self._mvp_report_rows("dues", f, invoices)
        # A billed-fee target uses the same invoice cohort as its collected amount.
        # Receipt posting months and outstanding due months must not be added together.
        end_month = f["date_to"].replace(day=1)
        months = [fields.Date.subtract(end_month, months=n) for n in reversed(range(6))]
        fee_months = {month.strftime("%Y-%m"): {"target": 0, "collected": 0} for month in months}
        balances = {row["id"]: row["balance"] for row in dues}
        for invoice in invoices:
            month = (invoice.invoice_date_due or invoice.invoice_date).strftime("%Y-%m")
            if month in fee_months:
                fee_months[month]["target"] += invoice.amount_total
                fee_months[month]["collected"] += max(0, invoice.amount_total - balances.get(invoice.id, 0))
        fee_rows = [{"label": month, **values, "percent": round(values["collected"] * 100 / values["target"], 1) if values["target"] else None}
                    for month, values in fee_months.items()]
        billed = sum(row["target"] for row in fee_rows)
        decisions = self._mvp_records(*self._admin_source("decisions", f)).sorted(lambda rec: (rec.date_to or fields.Date.to_date("9999-12-31"), rec.id))
        decision_rows = []
        for request in decisions[:3]:
            days = (request.date_to - today).days if request.date_to else None
            name = request.name.lower()
            tone, icon = ("cultural", "♫") if "cultur" in name else ("campaign", "⚑") if "campaign" in name else ("sponsor", "♧")
            decision_rows.append({"id": request.id, "name": request.name, "amount": request.amount,
                "deadline": request.date_to.strftime("%d %b %Y") if request.date_to else None, "days": days,
                "impact": request.description, "tone": tone, "icon": icon})
        overdue_dues = [row for row in dues if row["due"] and row["due"] < str(f["date_to"])]
        events = self._mvp_records(*self._admin_source("events", f)).sorted("date_begin")
        event_rows = []
        for event in events[:4]:
            start = fields.Datetime.context_timestamp(self, event.date_begin)
            end = fields.Datetime.context_timestamp(self, event.date_end)
            event_rows.append({"id": event.id, "name": event.name, "day": start.strftime("%d"), "month": start.strftime("%b").upper(),
                "date": start.strftime("%d %b %Y"), "time": start.strftime("%H:%M") + " – " + end.strftime("%d %b %H:%M"),
                "venue": event.address_id.name or _("Venue not assigned"), "organizer": event.organizer_id.name or _("Organizer not assigned"),
                "category": event.event_type_id.name or _("Campus event"),
                "description": shorten(html2plaintext(event.description or ""), width=120, placeholder="…")})
        current_terms = self._mvp_records("op.academic.term", [("company_id", "=", self.env.company.id),
            ("term_start_date", "<=", today), ("term_end_date", ">=", today)] + ([("academic_year_id", "=", f["year_id"])] if f["year_id"] else []))
        term_ranges = {(term.term_start_date, term.term_end_date) for term in current_terms}
        semester = next(iter(term_ranges)) if len(term_ranges) == 1 else None
        stats = {card["kind"]: card for card in data["stats"]}
        present, delayed, staff_allowed = self._admin_staff_punches()
        routes = self._mvp_records(*self._admin_source("fleet", f))
        fleet_allowed = self.env["campus.transport.route"].check_access_rights("read", raise_exception=False)
        registrations = {"".join(char for char in route.vehicle_registration.upper() if char.isalnum()) for route in routes}
        registrations.discard("")
        for kind, value, detail in [("staff_present", len(present.employee_id), _("Today · recorded check-ins")),
                                    ("staff_delayed", len(delayed.employee_id), _("Today · included in present")),
                                    ("fleet", len(registrations), _("Registered college buses"))]:
            allowed = fleet_allowed if kind == "fleet" else staff_allowed
            stats[kind] = {"kind": kind, "value": value if allowed else "—", "allowed": allowed,
                "detail": detail if allowed else _("Reporting access required")}
        specs = [("active_students", "Active students", "users", "blue"), ("admissions", "Admissions pipeline", "envelope-o", "blue"),
                 ("staff_delayed", "Delayed arrivals", "clock-o", "blue"), ("collection", "Fee collection", "inr", "blue"),
                 ("dues", "Outstanding fees", "inr", "amber"), ("staff_present", "Present staff", "users", "green"),
                 ("fleet", "Fleet (buses)", "bus", "blue")]
        kpis = [dict(stats[kind], label=label, icon=icon, tone=tone) for kind, label, icon, tone in specs]
        # The requested overview uses rupee labels; retain the recorded amounts.
        for card in kpis:
            if card["kind"] in {"collection", "dues"} and card["allowed"]:
                amount = card["value"].removeprefix(f"{self.env.company.currency_id.symbol} ")
                card["value"] = f"₹ {amount}"
        service_allowed = self.env["campus.service.request"].check_access_rights("read", raise_exception=False)
        kpis.append({"kind": "services", "label": "Open service requests", "value": len(services) if service_allowed else "—",
            "detail": _("Current college · all academic periods") if service_allowed else _("Reporting access required"), "icon": "flag-o", "tone": "red", "allowed": service_allowed})
        insights = []
        shortage = sum(row["value"] < threshold for row in department_rows)
        if shortage:
            insights.append({"title": _("Attendance needs attention"), "text": _("%(count)s departments are below the %(rate)s%% attendance threshold in this period.", count=shortage, rate=threshold), "tag": _("ACADEMICS"), "icon": "line-chart", "source": "attendance"})
        elif pending:
            insights.append({"title": _("Attendance registers need completion"), "text": _("%(count)s elapsed sessions in this period have no completed attendance register. Ask the responsible faculty to submit attendance.", count=len(pending)), "tag": _("ACADEMICS"), "icon": "calendar-check-o", "source": "attendance_pending"})
        if overdue_dues:
            insights.append({"title": _("Fee follow-up opportunity"), "text": _("%(count)s posted invoices have an outstanding balance past their due date as of %(date)s.", count=len(overdue_dues), date=str(f["date_to"])), "tag": _("FINANCE"), "icon": "inr", "source": "dues"})
        if stats["review"]["allowed"] and stats["review"]["value"]:
            insights.append({"title": _("Applications awaiting review"), "text": _("%(count)s applications in this period are awaiting a decision. Review the admissions register for the next action.", count=stats["review"]["value"]), "tag": _("ADMISSIONS"), "icon": "clock-o", "source": "review"})
        watches = [{"kind": "overdue_services", "label": _("Service requests past requested date"), "count": len(overdue_services), "detail": _("Open requests with a requested end date before today"), "icon": "flag-o", "tone": "red", "allowed": service_allowed},
            {"kind": "overdue_dues", "label": _("Overdue fee invoices"), "count": len(overdue_dues), "detail": _("Outstanding invoices past due in the selected academic scope"), "icon": "inr", "tone": "amber", "allowed": stats["dues"]["allowed"]},
            {"kind": "attendance_pending", "label": _("Attendance not submitted"), "count": len(pending), "detail": _("Elapsed sessions in this period without completed attendance"), "icon": "check", "tone": "blue", "allowed": self.env["op.attendance.sheet"].check_access_rights("read", raise_exception=False)}]
        data["overview_ui"] = {"kpis": kpis, "activity": activity, "departments": department_rows, "threshold": threshold, "currency_symbol": "₹",
            "fee_months": fee_rows, "fee_allowed": self.env["account.move"].check_access_rights("read", raise_exception=False),
            "fee_percent": round(sum(row["collected"] for row in fee_rows) * 100 / billed) if billed else None,
            "decisions": decision_rows, "decision_count": len(decisions), "decision_budget": sum(decisions.mapped("amount")),
            "decision_allowed": self.env["campus.service.request"].check_access_rights("read", raise_exception=False),
            "events": event_rows, "event_count": len(events), "event_allowed": self._admin_events_allowed(),
            "event_create": self._admin_events_allowed() and self.env["event.event"].check_access_rights("create", raise_exception=False),
            "insights": insights, "watchlist": watches, "updated": fields.Datetime.context_timestamp(self, now).strftime("%d %b %Y, %H:%M"),
            "greeting": _("Good morning") if fields.Datetime.context_timestamp(self, now).hour < 12 else _("Good afternoon") if fields.Datetime.context_timestamp(self, now).hour < 17 else _("Good evening"),
            "semester": {"start": str(semester[0]), "end": str(min(semester[1], today))} if semester else None}
        # Use stored decision codes, independent of translated stage labels.
        others = set(dict(self.env["op.admission"]._fields["campus_stage"].selection)) - {"submitted", "documents", "review", "approved"}
        groups = [("Submitted", {"submitted"}, "#1769e8"), ("Under review", {"documents", "review"}, "#36b890"),
                  ("Offer issued", {"approved"}, "#f2bd5d"), ("Enrolled / other", others, "#d9e1eb")]
        data["overview_ui"]["funnel"] = [{"label": label, "value": len(admissions.filtered(lambda rec, codes=codes: rec.campus_stage in codes)), "color": color} for label, codes, color in groups]
        def local_time(value):
            return fields.Datetime.context_timestamp(self, datetime.fromisoformat(value))
        data["overview_ui"]["upcoming"] = [dict(row, when=local_time(row["when"]).strftime("%d %b %Y, %H:%M"),
            day=local_time(row["when"]).strftime("%d"), month=local_time(row["when"]).strftime("%b").upper()) for row in data["upcoming"]]
        data["overview_ui"]["recent"] = [dict(row, when=local_time(row["when"]).strftime("%d %b %Y, %H:%M")) for row in data["recent"]]
        return data
