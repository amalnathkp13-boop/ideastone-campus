"""Department hall requests with serialized campus-wide venue availability."""

import re
from uuid import uuid4

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

PROGRAMME_TYPES = ["Seminar", "Workshop", "Guest lecture", "Symposium", "Department meeting", "Other"]
ACTIVE_STATES = ["pending", "approved"]


def hall_department(env):
    return env["campus.hod.dashboard"]._department()


def allocator(env, hall):
    user = env.user
    return env.su or user.has_group("ideastone_erp.group_manager") or (
        user == hall.authority_id and user.has_group("ideastone_erp.group_services"))


def slot_values(value):
    if not isinstance(value, dict):
        raise ValidationError(_("Choose a programme date and time."))
    try:
        day = fields.Date.to_date(value.get("date"))
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("Choose a valid event date.")) from exc
    start, end = value.get("start"), value.get("end")
    if (not day or not isinstance(start, str) or not isinstance(end, str)
            or not all(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", item) for item in (start, end))
            or start >= end):
        raise ValidationError(_("Choose a valid date and an end time later than the start time."))
    return day, start, end


class Hall(models.Model):
    _name = "campus.hall"
    _description = "Campus programme hall"
    _inherit = "campus.record"
    _order = "sequence, name, id"

    sequence = fields.Integer(default=10)
    capacity = fields.Integer(required=True)
    location = fields.Char(required=True)
    features = fields.Char(help="Comma-separated facilities, such as Projector, PA system, AC")
    authority_id = fields.Many2one("res.users", required=True, ondelete="restrict",
        default=lambda self: self.env.ref("base.user_admin"))
    booking_revision = fields.Integer(default=0, copy=False, groups="base.group_no_one")

    _sql_constraints = [
        ("hall_name", "unique(company_id,name)", "Hall names must be unique in the college."),
        ("hall_capacity", "check(capacity > 0)", "Enter a positive seating capacity."),
    ]

    @api.constrains("authority_id", "company_id")
    def _check_authority(self):
        for hall in self:
            user = hall.authority_id
            if (not user.active or hall.company_id not in user.company_ids
                    or not any(user.has_group("ideastone_erp." + role) for role in ("group_services", "group_manager"))):
                raise ValidationError(_("Choose an active allocation authority in this college."))

    @api.constrains("capacity", "active")
    def _check_live_bookings(self):
        for hall in self:
            live = self.env["campus.hall.booking"].sudo().search([
                ("hall_id", "=", hall.id), ("company_id", "=", hall.company_id.id),
                ("state", "in", ACTIVE_STATES), ("event_date", ">=", fields.Date.context_today(self)),
            ])
            if live and (not hall.active or any(row.attendees > hall.capacity for row in live)):
                raise ValidationError(_("Resolve upcoming allocations before reducing capacity or archiving this hall."))

    def _reserve_lock(self):
        # Updating the lock row makes concurrent repeatable-read transactions retry
        # with a fresh snapshot before inspecting overlapping bookings.
        self.ensure_one()
        self.sudo()._lock()
        self.sudo().write({"booking_revision": self.sudo().booking_revision + 1})


class HallBooking(models.Model):
    _name = "campus.hall.booking"
    _description = "Department hall allocation request"
    _inherit = "campus.record"
    _order = "id desc"

    name = fields.Char(default="/", readonly=True)
    hall_id = fields.Many2one("campus.hall", required=True, check_company=True, ondelete="restrict", index=True)
    department_id = fields.Many2one("op.department", required=True, check_company=True, ondelete="restrict", index=True)
    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    event_date = fields.Date(required=True, index=True)
    start_time = fields.Char(required=True)
    end_time = fields.Char(required=True)
    programme = fields.Char(required=True)
    programme_type = fields.Selection([(item, item) for item in PROGRAMME_TYPES], required=True)
    coordinator = fields.Char(required=True)
    attendees = fields.Integer(required=True)
    requirements = fields.Text()
    state = fields.Selection([(key, key.title()) for key in ("pending", "approved", "rejected", "cancelled")],
        default="pending", required=True, tracking=True, readonly=True, index=True)
    reason = fields.Text(readonly=True)
    decision_note = fields.Text(string="Approval / rejection remarks")
    decided_by_id = fields.Many2one("res.users", readonly=True)
    decided_on = fields.Datetime(readonly=True)
    request_token = fields.Char(required=True, default=lambda self: str(uuid4()), readonly=True, copy=False)

    _sql_constraints = [
        ("hall_request_token", "unique(requester_id,request_token)", "This request has already been submitted."),
    ]

    def _overlaps(self):
        self.ensure_one()
        return self.sudo().search([
            ("company_id", "=", self.company_id.id), ("hall_id", "=", self.hall_id.id),
            ("id", "!=", self.id), ("event_date", "=", self.event_date),
            ("state", "in", ACTIVE_STATES), ("start_time", "<", self.end_time), ("end_time", ">", self.start_time),
        ], limit=1)

    @api.constrains("hall_id", "department_id", "company_id", "event_date", "start_time", "end_time",
                    "attendees", "programme", "coordinator", "requirements")
    def _check_details(self):
        for row in self:
            slot_values({"date": row.event_date, "start": row.start_time, "end": row.end_time})
            if row.department_id.company_id != row.company_id or row.hall_id.company_id != row.company_id:
                raise ValidationError(_("Choose a hall and department in the request's college."))
            if (not 1 <= row.attendees <= row.hall_id.capacity or not row.programme.strip() or len(row.programme) > 120
                    or not row.coordinator.strip() or len(row.coordinator) > 80 or len(row.requirements or "") > 500):
                raise ValidationError(_("Enter programme details and an attendee count within the hall capacity."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for incoming in vals_list:
            values = dict(incoming)
            if (values.get("state", "pending") != "pending" or values.get("decided_by_id")
                    or values.get("decided_on") or values.get("reason") or values.get("active") is False):
                raise AccessError(_("New requests must start as pending allocations."))
            if not self.env.su and not self.env.user.has_group("ideastone_erp.group_manager"):
                department = hall_department(self.env)
                allowed = {"hall_id", "department_id", "requester_id", "company_id", "event_date", "start_time", "end_time",
                           "programme", "programme_type", "coordinator", "attendees", "requirements", "request_token"}
                if set(values) - allowed:
                    raise AccessError(_("Submit programme details through the allocation request workflow."))
                if values.get("department_id", department.id) != department.id or values.get("requester_id", self.env.uid) != self.env.uid:
                    raise AccessError(_("Submit requests for your assigned department."))
                values.update(department_id=department.id, requester_id=self.env.uid, company_id=self.env.company.id)
            hall = self.env["campus.hall"].sudo().search([
                ("id", "=", values.get("hall_id")), ("company_id", "=", self.env.company.id), ("active", "=", True),
            ])
            if not hall:
                raise AccessError(_("Choose an active hall in the current college."))
            values["company_id"] = hall.company_id.id
            day, _start, _end = slot_values({"date": values.get("event_date"), "start": values.get("start_time"), "end": values.get("end_time")})
            if day < fields.Date.context_today(self):
                raise ValidationError(_("Choose today or a future date for a new request."))
            values.update(state="pending", active=True, decided_by_id=False, decided_on=False, reason=False,
                          decision_note=False)
            prepared.append(values)
        # Stable hall order also prevents deadlocks when a manager imports several requests.
        for hall in self.env["campus.hall"].sudo().browse(sorted({values["hall_id"] for values in prepared})):
            hall._reserve_lock()
        # HOD reporting access is otherwise read-only. Elevate only after the
        # department, caller, college and initial-state checks above.
        create_context = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        rows = super(HallBooking, self.sudo().with_context(create_context)).create(prepared)
        for row in rows:
            if row._overlaps():
                raise ValidationError(_("The hall is no longer available. Choose another hall or time slot."))
            super(HallBooking, row).write({"name": f"HA-{row.id:04d}"})
            row.message_post(body=_("Allocation request submitted. The slot is held pending approval."))
        return rows.with_env(self.env)

    def write(self, vals):
        if set(vals) - {"message_follower_ids", "message_ids", "activity_ids", "decision_note"}:
            raise AccessError(_("Use the allocation approval or cancellation workflow to change a request."))
        if "decision_note" in vals and any(not allocator(self.env, row.hall_id) for row in self):
            raise AccessError(_("Only the allocation authority can add decision remarks."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Retain allocation requests for their history."))

    def action_decide(self, decision):
        if decision not in ("approved", "rejected"):
            raise ValidationError(_("Choose approve or reject."))
        for row in self:
            row.check_access_rights("read")
            row.check_access_rule("read")
            if row.company_id != self.env.company or not allocator(self.env, row.hall_id):
                raise AccessError(_("Only the allocation authority can decide this request."))
            row.sudo()._lock()
            if row.state != "pending":
                raise ValidationError(_("Only pending requests can be decided."))
            if decision == "rejected" and not (row.decision_note or "").strip():
                raise ValidationError(_("Enter a reason before rejecting the request."))
            row.hall_id._reserve_lock()
            if decision == "approved" and (not row.hall_id.active or row._overlaps()):
                raise ValidationError(_("The hall is no longer available for this booking."))
            super(HallBooking, row.sudo()).write({"state": decision, "reason": row.decision_note,
                "decided_by_id": self.env.uid, "decided_on": fields.Datetime.now()})
            row.message_post(body=_("Allocation request %s.", decision))
        return True

    def action_approve(self):
        return self.action_decide("approved")

    def action_reject(self):
        return self.action_decide("rejected")


class HallAllocationUI(models.AbstractModel):
    _name = "campus.hod.hall.ui"
    _description = "HOD hall allocation workspace"

    def _halls(self):
        hall_department(self.env)
        return self.env["campus.hall"].sudo().search([("company_id", "=", self.env.company.id), ("active", "=", True)])

    def _serialize(self, row):
        return {"id": row.id, "reference": row.name, "hall_id": row.hall_id.id, "hall": row.hall_id.name,
            "date": str(row.event_date), "start": row.start_time, "end": row.end_time, "programme": row.programme,
            "type": row.programme_type, "coordinator": row.coordinator, "attendees": row.attendees,
            "requirements": row.requirements or "", "department": row.department_id.name,
            "status": row.state.title(), "reason": row.reason or ""}

    @api.model
    def get_workspace(self, slot=None):
        department = hall_department(self.env)
        halls = self._halls()
        records = self.env["campus.hall.booking"].sudo()
        scope = [("company_id", "=", self.env.company.id)]
        own = records.search(scope + [("department_id", "=", department.id)])
        bookings = records.browse()
        if slot:
            day, _start, _end = slot_values(slot)
            bookings = records.search(scope + [("hall_id", "in", halls.ids), ("event_date", "=", day),
                ("state", "in", ACTIVE_STATES)], order="start_time, id")
        return {"department": department.name, "demo": self.env.company.campus_demo,
            "today": str(fields.Date.context_today(self)), "types": PROGRAMME_TYPES,
            "halls": [{"id": hall.id, "name": hall.name, "capacity": hall.capacity, "location": hall.location,
                       "features": [part.strip() for part in (hall.features or "").split(",") if part.strip()]} for hall in halls],
            # The availability calendar exposes programme/department/time, while contact
            # details and special requirements stay inside the requesting department.
            "bookings": [{"id": row.id, "hall_id": row.hall_id.id, "date": str(row.event_date),
                          "start": row.start_time, "end": row.end_time, "programme": row.programme,
                          "department": row.department_id.name, "status": row.state.title()} for row in bookings],
            "requests": [self._serialize(row) for row in own]}

    @api.model
    def submit(self, payload):
        department = hall_department(self.env)
        if not isinstance(payload, dict):
            raise ValidationError(_("Enter allocation request details."))
        token = payload.get("token")
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f-]{36}", token):
            raise ValidationError(_("Refresh the form and submit again."))
        self.env.cr.execute("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", [token, self.env.uid])
        previous = self.env["campus.hall.booking"].search([("request_token", "=", token), ("requester_id", "=", self.env.uid)])
        if previous:
            return self._serialize(previous)
        day, start, end = slot_values(payload.get("slot"))
        if type(payload.get("hall_id")) is not int or type(payload.get("attendees")) is not int:
            raise ValidationError(_("Choose a hall and a whole-number attendee count."))
        text_fields = ["programme", "type", "coordinator", "requirements"]
        if any(not isinstance(payload.get(key, ""), str) for key in text_fields):
            raise ValidationError(_("Enter valid programme details."))
        row = self.env["campus.hall.booking"].create({
            "hall_id": payload["hall_id"], "department_id": department.id, "event_date": day,
            "start_time": start, "end_time": end, "attendees": payload["attendees"],
            "programme": payload.get("programme", "").strip(), "programme_type": payload.get("type"),
            "coordinator": payload.get("coordinator", "").strip(), "requirements": payload.get("requirements", "").strip(),
            "request_token": token,
        })
        return self._serialize(row)

    @api.model
    def cancel(self, request_id):
        department = hall_department(self.env)
        if type(request_id) is not int:
            raise ValidationError(_("Choose a valid allocation request."))
        row = self.env["campus.hall.booking"].search([
            ("id", "=", request_id), ("company_id", "=", self.env.company.id), ("department_id", "=", department.id),
        ])
        if not row:
            raise AccessError(_("This request belongs to another department or college."))
        row.sudo()._lock()
        if row.state == "cancelled":
            return True
        if row.state != "pending":
            raise ValidationError(_("Only a pending request can be cancelled."))
        row.hall_id._reserve_lock()
        super(HallBooking, row.sudo()).write({"state": "cancelled"})
        row.sudo().message_post(body=_("The requesting department cancelled the temporary hold."))
        return True


class HallNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        department = self.env["campus.hod.directory"]._department()
        if department:
            action = self.env.ref("ideastone_erp.action_hod_hall_allocation")
            item = {"label": "Request & availability", "action": "ideastone_erp.action_hod_hall_allocation",
                    "action_id": action.id, "allowed": True, "group": "Hall Allocation"}
            modules = data["faculty_modules"]
            index = next((i for i, module in enumerate(modules) if module["key"] == "reports"), len(modules))
            modules.insert(index, {"key": "hall-allocation", "label": "Hall Allocation",
                                   "icon": "building-o", "items": [item]})
            data["navigation"].append(item)
        return data
