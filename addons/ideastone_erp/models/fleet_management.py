import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

EXPENSES = dict(fuel="Diesel / fuel", maintenance="Servicing & repairs", insurance="Insurance & permits",
                tyres="Tyres", accident="Accident repairs", other="Other", salary="Driver wages")


class FleetRoute(models.Model):
    _inherit = "campus.transport.route"

    fleet_insured_until = fields.Date(groups="ideastone_erp.group_fleet_manager")
    fleet_expected_arrival = fields.Char(groups="ideastone_erp.group_fleet_manager")
    fleet_dispatch_revision = fields.Integer(copy=False, groups="base.group_no_one")


class FleetEvent(models.Model):
    _name = "campus.fleet.event"
    _description = "Fleet operations register"
    _order = "date desc, id desc"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True,
                                  default=lambda self: self.env.ref("base.INR"))
    route_id = fields.Many2one("campus.transport.route", required=True, check_company=True, ondelete="restrict", index=True)
    replacement_id = fields.Many2one("campus.transport.route", check_company=True, ondelete="restrict", index=True)
    kind = fields.Selection([(key, key.title()) for key in ("arrival", "expense", "incident", "replacement")], required=True)
    date = fields.Date(required=True, index=True, default=fields.Date.context_today)
    note = fields.Text()
    category = fields.Selection(list(EXPENSES.items()))
    amount = fields.Monetary()
    arrival = fields.Char()
    closed_at = fields.Datetime()
    closed_by = fields.Many2one("res.users")
    close_note = fields.Text()

    def init(self):
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS campus_fleet_arrival_per_day
            ON campus_fleet_event (route_id, date) WHERE kind = 'arrival'""")


class FleetWorkspace(models.AbstractModel):
    _name = "campus.fleet.ui"
    _description = "Company-scoped fleet management workspace"

    def _role(self):
        user = self.env.user
        if user.has_group("ideastone_erp.group_mvp_owner") or user.has_group("base.group_system"):
            return "owner"
        if user.has_group("ideastone_erp.group_fleet_manager"):
            return "manager"
        raise AccessError(_("Fleet workspace access is required."))

    def _routes(self):
        today = self._today()
        return self.env["campus.transport.route"].sudo().search([
            ("company_id", "=", self.env.company.id), ("year_id.start_date", "<=", today),
            ("year_id.end_date", ">=", today),
        ], order="name, id")

    def _events(self):
        return self.env["campus.fleet.event"].sudo().with_company(self.env.company)

    def _today(self):
        return fields.Date.context_today(self.with_context(tz=self.env.company.partner_id.tz or "Asia/Kolkata"))

    def _scope(self):
        return [("company_id", "=", self.env.company.id)]

    def _dispatch(self):
        events = self._events().search(self._scope() + [
            ("kind", "in", ["incident", "replacement"]), ("closed_at", "=", False)])
        return events.filtered(lambda event: event.kind == "replacement"), events.filtered(lambda event: event.kind == "incident")

    def _eligible(self, route, today):
        return bool(route.active and route.driver and route.fleet_insured_until and route.fleet_insured_until >= today
                    and (not route.service_due or route.service_due > today))

    def _registration(self, registration):
        return re.sub(r"[^A-Z0-9]", "", (registration or "").upper())

    def _snapshot(self, detail=False, period="month"):
        today = self._today()
        routes = self._routes()
        events = self._events()
        coverage, incidents = self._dispatch()
        originals = {event.route_id.id: event for event in coverage}
        replacements = {event.replacement_id.id: event for event in coverage}
        blocked = set(incidents.route_id.ids)
        arrivals = {event.route_id.id: event.arrival for event in events.search(
            self._scope() + [("kind", "=", "arrival"), ("date", "=", today)])}
        if period == "previous":
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        elif period == "year":
            start, end = min(routes.year_id.mapped("start_date"), default=today.replace(month=1, day=1)), today
        else:
            start, end = today.replace(day=1), today
        expense_records = events.search(self._scope() + [("kind", "=", "expense"), ("date", ">=", start), ("date", "<=", end)]) if detail else events.browse()
        expenses = Counter()
        spend = Counter()
        for item in expense_records:
            expenses[item.category] += item.amount
            spend[item.route_id.id] += item.amount
        rows = []
        for route in routes:
            if not route.vehicle_registration:
                continue
            current = originals.get(route.id)
            incoming = replacements.get(route.id)
            actual = arrivals.get(route.id, "")
            expected = (incoming.route_id if incoming else route).fleet_expected_arrival or ""
            insured = bool(route.fleet_insured_until and route.fleet_insured_until >= today)
            service = bool(route.service_due and route.service_due <= today)
            running = insured and route.id not in blocked and not current and (
                route.fleet_status == "operational" or bool(incoming))
            rows.append({"id": route.id, "bus": route.vehicle_registration,
                "route": (incoming.route_id if incoming else route).name, "assigned_route": route.name,
                "driver": route.driver or "", "expected": expected, "actual": actual,
                "insured": insured, "insurance_until": str(route.fleet_insured_until or ""),
                "service": service, "service_due": str(route.service_due or ""), "running": running,
                "on_time": bool(running and actual and expected and actual <= expected),
                "late": bool(running and actual and expected and actual > expected),
                "replacement": current.replacement_id.vehicle_registration if current else "",
                "standby": bool(route.fleet_status == "reserve" and not current and not incoming and route.id not in blocked
                                and self._eligible(route, today)),
                "status": route.fleet_status, "spend": spend[route.id],
                "stops": (incoming.route_id if incoming else route).stop_ids.sorted("sequence").mapped("name") if detail else [],
            })
        # A bus registration may be repeated in overlapping academic-year route records.
        # Keep the operational row for overview counters, and retain every route in the register.
        unique = {}
        for row in sorted(rows, key=lambda row: not row["running"]):
            key = self._registration(row["bus"]) or row["bus"]
            unique.setdefault(key, row)
        fleet = list(unique.values())
        totals = {"total": len(fleet), "active": sum(row["running"] for row in fleet),
                  "insured": sum(row["insured"] for row in fleet), "pending": sum(not row["insured"] for row in fleet),
                  "service": sum(row["service"] for row in fleet), "on_time": sum(row["on_time"] for row in fleet),
                  "late": sum(row["late"] for row in fleet), "incidents": len(incidents)}
        data = {"totals": totals, "today": str(today)}
        if detail:
            data.update(rows=rows, company=self.env.company.name,
                currency=self.env.ref("base.INR").name, period_from=str(start), period_to=str(end),
                expense_total=sum(expenses.values()), categories=[{"key": key, "name": label, "amount": expenses[key]} for key, label in EXPENSES.items()],
                expenses=[self._event_row(event) for event in expense_records[:50]],
                incidents=[self._event_row(event) for event in events.search(self._scope() + [("kind", "=", "incident")], limit=50)],
                coverage=[self._event_row(event) for event in coverage],
                previous=[self._event_row(event) for event in events.search(self._scope() + [
                    ("kind", "=", "replacement"), ("closed_at", "!=", False)], limit=30)])
        return data

    def _event_row(self, event):
        return {"id": event.id, "bus": event.route_id.vehicle_registration, "route": event.route_id.name,
                "replacement": event.replacement_id.vehicle_registration or "", "date": str(event.date),
                "note": event.note or "", "amount": event.amount, "category": EXPENSES.get(event.category, ""),
                "closed": bool(event.closed_at), "close_note": event.close_note or ""}

    @api.model
    def get_workspace(self, period="month"):
        role = self._role()
        return dict(self._snapshot(detail=True, period=period), readonly=role == "owner")

    def _bus(self, value):
        if type(value) is not int:
            raise ValidationError(_("Choose a bus from this college."))
        route = self._routes().filtered(lambda item: item.id == value)
        if not route:
            raise AccessError(_("This bus is outside the current college fleet."))
        return route

    def _lock_buses(self, buses):
        # All dispatch writes serialize on the same bus rows. The revision makes
        # concurrent PostgreSQL repeatable-read transactions retry on a fresh snapshot.
        buses._lock()
        self.env.cr.execute("UPDATE campus_transport_route SET fleet_dispatch_revision = COALESCE(fleet_dispatch_revision, 0) + 1 WHERE id IN %s",
                            [tuple(buses.ids)])

    def _time(self, value):
        if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValidationError(_("Enter a valid time in HH:MM format."))
        return value

    def _date(self, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValidationError(_("Enter a valid date."))
        try:
            return fields.Date.to_date(value)
        except ValueError as exc:
            raise ValidationError(_("Enter a valid date.")) from exc

    @api.model
    def save(self, operation, payload):
        if self._role() != "manager":
            raise AccessError(_("Only Fleet Managers can update fleet operations."))
        if not isinstance(payload, dict) or operation not in ("update", "arrival", "expense", "incident", "replacement", "close"):
            raise ValidationError(_("Choose a valid fleet operation."))
        today = self._today()
        note = payload.get("note") or ""
        if not isinstance(note, str) or len(note) > 500:
            raise ValidationError(_("Enter a note of at most 500 characters."))
        events = self._events()
        if operation == "close":
            event_id = payload.get("event_id")
            if type(event_id) is not int:
                raise ValidationError(_("Choose an open fleet entry."))
            event = events.search(self._scope() + [("id", "=", event_id), ("kind", "in", ["incident", "replacement"])])
            if not event:
                raise AccessError(_("This fleet entry is outside your college."))
            self._lock_buses(event.route_id | event.replacement_id)
            if event.closed_at:
                raise ValidationError(_("This fleet entry is already closed."))
            if event.kind == "replacement":
                _coverage, incidents = self._dispatch()
                if payload.get("verified") is not True or not self._eligible(event.route_id, today) or event.route_id in incidents.route_id:
                    raise ValidationError(_("Confirm roadworthiness, insurance and servicing, and resolve open incidents before restoring the regular bus."))
                event.route_id.fleet_status = "operational"
            event.write({"closed_at": fields.Datetime.now(), "closed_by": self.env.uid, "close_note": note.strip()})
            return True
        bus = self._bus(payload.get("route_id"))
        replacement = self._bus(payload.get("replacement_id")) if operation == "replacement" else bus.browse()
        if replacement:
            plates = {self._registration(bus.vehicle_registration), self._registration(replacement.vehicle_registration)}
            self._lock_buses(self._routes().filtered(lambda route: self._registration(route.vehicle_registration) in plates))
        else:
            self._lock_buses(bus)
        coverage, incidents = self._dispatch()
        values = {"kind": operation, "route_id": bus.id, "note": note.strip(), "date": today}
        if operation == "update":
            status = payload.get("status")
            driver = payload.get("driver") or ""
            if status not in ("operational", "maintenance", "reserve") or not isinstance(driver, str) or len(driver) > 100:
                raise ValidationError(_("Enter valid bus operating details."))
            if bus in coverage.replacement_id and (status != "reserve" or not driver.strip() or
                not payload.get("insurance_until") or self._date(payload["insurance_until"]) < today or
                payload.get("service_due") and self._date(payload["service_due"]) <= today):
                raise ValidationError(_("Restore or end this bus's active temporary assignment before making it unavailable."))
            bus.write({"fleet_status": status, "driver": driver.strip(),
                "fleet_insured_until": self._date(payload["insurance_until"]) if payload.get("insurance_until") else False,
                "service_due": self._date(payload["service_due"]) if payload.get("service_due") else False,
                "fleet_expected_arrival": self._time(payload["expected"]) if payload.get("expected") else False})
            return True
        if operation == "arrival":
            values["arrival"] = self._time(payload.get("arrival"))
            previous = events.search(self._scope() + [("route_id", "=", bus.id), ("kind", "=", "arrival"), ("date", "=", today)])
            if previous:
                previous.write({"arrival": values["arrival"]})
                return True
        elif operation == "expense":
            category = payload.get("category")
            if not isinstance(category, str) or category not in EXPENSES or not note.strip():
                raise ValidationError(_("Choose an expense category and enter its purpose."))
            try:
                amount = Decimal(str(payload.get("amount")))
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError(_("Enter a positive expense amount.")) from exc
            if not amount.is_finite() or not Decimal("0.01") <= amount <= 10000000:
                raise ValidationError(_("Enter a positive expense amount up to 10,000,000."))
            date = self._date(payload.get("date"))
            if date > today:
                raise ValidationError(_("An expense cannot be dated in the future."))
            values.update(amount=float(amount), date=date, category=category)
        elif operation == "incident":
            if not note.strip():
                raise ValidationError(_("Describe the incident."))
        else:
            occupied = {self._registration(route.vehicle_registration) for route in coverage.route_id | coverage.replacement_id}
            riders = self.env["campus.transport.allocation"].sudo().search_count([("route_id", "=", bus.id), ("state", "=", "approved")])
            if (not bus.active or bus.fleet_status == "reserve" or len(plates) != 2 or bus.year_id != replacement.year_id or plates & occupied
                or replacement.fleet_status != "reserve" or replacement in incidents.route_id or not self._eligible(replacement, today)
                or replacement.capacity < riders + bus.staff_riders or payload.get("verified") is not True or not note.strip()):
                raise ValidationError(_("Choose an available, insured standby bus with a driver and enough seats. Confirm roadworthiness and enter a reason."))
            values["replacement_id"] = replacement.id
        events.create(values)
        return True
