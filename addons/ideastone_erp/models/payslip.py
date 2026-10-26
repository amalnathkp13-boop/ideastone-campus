from datetime import timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

from .late_punch import MONTHLY_GRACE_DAYS, late_punch_dates, local_bounds


class Payslip(models.Model):
    _name = "campus.payslip"
    _description = "Attendance-based campus payroll"
    _inherit = "campus.approval"
    _order = "date_from desc"

    agreement_id = fields.Many2one("campus.salary.agreement", required=True, ondelete="restrict", check_company=True)
    employee_id = fields.Many2one(related="agreement_id.employee_id", store=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    working_days = fields.Float(required=True)
    paid_leave_days = fields.Float("Approved paid leave days", help="College payroll operator classifies approved leave under its configured pay policy.")
    advance_deduction = fields.Monetary()
    worked_days = fields.Float(readonly=True)
    gross = fields.Monetary(readonly=True)
    pf = fields.Monetary(readonly=True)
    esi = fields.Monetary(readonly=True)
    deductions = fields.Monetary(readonly=True)
    late_days = fields.Integer("Late punch days", readonly=True)
    late_grace_days = fields.Integer("Paid late permission days", readonly=True)
    late_deducted_days = fields.Integer("Late days deducted", readonly=True)
    late_deduction = fields.Monetary("Late punch deduction", readonly=True)
    late_punch_dates = fields.Char("Late punch dates", readonly=True)
    late_deduction_dates = fields.Char("Deducted late dates", readonly=True)
    tds = fields.Monetary(readonly=True)
    net = fields.Monetary(readonly=True)
    computed_on = fields.Datetime(readonly=True)
    payment_reference = fields.Char()

    _sql_constraints = [("payslip_unique", "unique(employee_id, date_from, date_to)", "Payroll already exists for this employee and period.")]

    _calculated_fields = {"worked_days", "gross", "pf", "esi", "tds", "deductions", "net", "computed_on",
                          "late_days", "late_grace_days", "late_deducted_days", "late_deduction",
                          "late_punch_dates", "late_deduction_dates"}

    def _history_employees(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Sign in with a staff account to view payroll history."))
        domain = [("company_id", "in", [False, self.env.company.id])]
        if not self.env.user.has_group("ideastone_erp.group_manager"):
            domain.append(("user_id", "=", self.env.uid))
        return self.env["hr.employee"].sudo().search(domain, order="name, id")

    def _history_employee_id(self, value):
        if value is None or value is False or value == "":
            return 0
        if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit() or int(value) <= 0:
            raise ValidationError(_("Choose a valid staff member."))
        return int(value)

    @api.model
    def get_history_data(self, employee_id=None):
        """Use the same approved records for admin review and staff self-service."""
        employees = self._history_employees()
        selected_id = self._history_employee_id(employee_id)
        selected = employees.filtered(lambda employee: employee.id == selected_id)[:1]
        if employee_id and not selected:
            raise AccessError(_("This staff member is outside your permitted payroll scope."))
        if not selected:
            latest = self.search([("employee_id", "in", employees.ids), ("company_id", "=", self.env.company.id),
                                  ("state", "in", ["approved", "done"])], order="date_from desc, id desc", limit=1)
            selected = latest.employee_id or employees[:1]
        slips = self.search([("employee_id", "=", selected.id), ("company_id", "=", self.env.company.id),
                             ("state", "in", ["approved", "done"])],
                            order="date_from desc, id desc") if selected else self.browse()
        columns = ["name", "date_from", "date_to", "net", "pf", "tds", "state", "late_days",
                   "late_grace_days", "late_deducted_days", "late_deduction", "late_punch_dates",
                   "late_deduction_dates"]
        currency = self.env.company.currency_id
        return {"employee_id": selected.id or False,
                "employee_name": selected.name or "", "staff": [
                    {"id": employee.id, "name": employee.name} for employee in employees
                    if self.env.user.has_group("ideastone_erp.group_manager")
                ], "records": slips.read(columns),
                "currency_symbol": currency.symbol, "currency_code": currency.name,
                "currency_position": currency.position}

    @api.model
    def get_punch_entries(self, employee_id, date_from, date_to):
        """Show own punches, or an admin's selected staff member, for approved payroll."""
        employees = self._history_employees()
        selected_id = self._history_employee_id(employee_id)
        employee = employees.filtered(lambda record: record.id == selected_id)[:1]
        if not employee:
            raise AccessError(_("This staff member is outside your permitted payroll scope."))
        try:
            start_day = fields.Date.to_date(date_from)
            end_day = fields.Date.to_date(date_to)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid payroll month.")) from exc
        if not start_day or not end_day or end_day < start_day or start_day.year != end_day.year or start_day.month != end_day.month:
            raise ValidationError(_("Choose a valid payroll month."))
        slip = self.search([("employee_id", "=", employee.id), ("company_id", "=", self.env.company.id), ("date_from", "=", start_day),
                            ("date_to", "=", end_day), ("state", "in", ["approved", "done"])], limit=1)
        if not slip:
            raise AccessError(_("Punch history is available for approved payroll periods only."))
        timezone = pytz.timezone(employee.resource_calendar_id.tz or "UTC")
        start = local_bounds(start_day, timezone)[0]
        end = local_bounds(end_day + timedelta(days=1), timezone)[0]
        attendance = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id), ("check_in", ">=", start), ("check_in", "<", end),
        ], order="check_in asc")
        late_days = set((slip.late_punch_dates or "").split(", "))
        deducted = set((slip.late_deduction_dates or "").split(", "))
        result = []
        for entry in attendance:
            check_in = pytz.UTC.localize(fields.Datetime.to_datetime(entry.check_in)).astimezone(timezone)
            check_out = (pytz.UTC.localize(fields.Datetime.to_datetime(entry.check_out)).astimezone(timezone)
                         if entry.check_out else None)
            day = check_in.date().isoformat()
            result.append({"id": entry.id, "date": day, "check_in": check_in.strftime("%H:%M"),
                           "check_out": check_out.strftime("%H:%M") if check_out else "Open",
                           "treatment": "1 day deducted" if day in deducted else
                           "Paid permission" if day in late_days else "No late deduction"})
        return result

    @api.constrains("date_from", "date_to", "working_days", "paid_leave_days", "advance_deduction")
    def _check_period(self):
        for rec in self:
            if rec.date_to < rec.date_from or rec.date_to.month != rec.date_from.month or rec.date_to.year != rec.date_from.year:
                raise ValidationError(_("Payroll period must fall within a single month."))
            if rec.working_days <= 0 or rec.working_days > (rec.date_to - rec.date_from).days + 1 or min(rec.paid_leave_days, rec.advance_deduction) < 0 or rec.paid_leave_days > rec.working_days:
                raise ValidationError(_("Check working days, paid leave days and advance deduction."))

    def write(self, vals):
        if set(vals) == {"payment_reference"} and all(r.state == "approved" for r in self):
            if not self.env.user.has_group("ideastone_erp.group_people"):
                raise AccessError(_("HR payroll permission is required to record payment evidence."))
            self._lock()
            return self._set_system_values(vals)
        if set(vals) & self._calculated_fields:
            raise AccessError(_("Payroll totals are calculated by Compute payroll."))
        result = super().write(vals)
        if set(vals) - {"state", "message_follower_ids", "activity_ids", "message_ids"}:
            self._set_system_values({"computed_on": False})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v) & self._calculated_fields for v in vals_list):
            raise AccessError(_("Payroll totals cannot be supplied when creating a payslip."))
        return super().create(vals_list)

    def action_compute(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_people"):
            raise AccessError(_("HR payroll permission is required."))
        for rec in self:
            agreement = rec.agreement_id
            if rec.state != "draft" or agreement.state != "approved":
                raise ValidationError(_("Compute only draft payroll against approved salary terms."))
            if rec.date_from < agreement.date_from or agreement.date_to and rec.date_to > agreement.date_to:
                raise ValidationError(_("Payroll dates must lie within the salary agreement."))
            timezone = pytz.timezone(rec.employee_id.resource_calendar_id.tz or "UTC")
            start = local_bounds(rec.date_from, timezone)[0]
            end = local_bounds(rec.date_to + timedelta(days=1), timezone)[0]
            attendance = self.env["hr.attendance"].search([
                ("employee_id", "=", rec.employee_id.id), ("check_in", "<", end),
                "|", ("check_out", "=", False), ("check_out", ">", start),
            ])
            if any(not att.check_out for att in attendance):
                raise ValidationError(_("Close all staff punches in the payroll period before computing salary."))
            month_start = rec.date_from.replace(day=1)
            monthly_late = late_punch_dates(self.env, rec.employee_id, month_start)
            period_late = [day for day in monthly_late if rec.date_from <= day <= rec.date_to]
            grace = set(monthly_late[:MONTHLY_GRACE_DAYS])
            deducted_dates = [day for day in period_late if day not in grace]
            worked = 0.0
            day = rec.date_from
            while day <= rec.date_to:
                day_start, day_end = local_bounds(day, timezone)
                hours = sum(att._get_worked_hours_in_range(max(att.check_in, day_start), min(att.check_out, day_end))
                            for att in attendance if att.check_in < day_end and att.check_out > day_start)
                if day in period_late:
                    first = min(att.check_in for att in attendance if day_start <= att.check_in < day_end)
                    local_first = pytz.UTC.localize(fields.Datetime.to_datetime(first)).astimezone(timezone)
                    starts = [line.hour_from for line in rec.employee_id.resource_calendar_id.attendance_ids
                              if line.dayofweek == str(day.weekday())]
                    scheduled_start = min(starts) if starts else 9.0
                    arrival_hour = local_first.hour + local_first.minute / 60 + local_first.second / 3600
                    # Excuse the missed arrival time, never an unrelated early departure.
                    hours += min(max(arrival_hour - scheduled_start, 0), agreement.daily_hours)
                worked += min(hours / agreement.daily_hours, 1.0)
                day += timedelta(days=1)
            worked = min(worked, rec.working_days)
            leave = self.env["hr.leave"].search([
                ("employee_id", "=", rec.employee_id.id), ("state", "=", "validate"),
                ("date_from", ">=", start), ("date_to", "<", end),
            ])
            if rec.paid_leave_days > sum(leave.mapped("number_of_days")):
                raise ValidationError(_("Paid leave days cannot exceed approved leave within this payroll period."))
            ratio = min(worked + rec.paid_leave_days, rec.working_days) / rec.working_days
            currency = rec.currency_id
            gross = currency.round((agreement.basic + agreement.allowance) * ratio)
            pf = currency.round(agreement.pf_base * agreement.pf_rate / 100 * ratio)
            esi = currency.round(agreement.esi_base * agreement.esi_rate / 100 * ratio)
            late_deduction = currency.round((agreement.basic + agreement.allowance) / rec.working_days * len(deducted_dates))
            deduction = currency.round(agreement.fixed_deduction + rec.advance_deduction + pf + esi + agreement.tds + late_deduction)
            if deduction > gross:
                raise ValidationError(_("Deductions exceed earned salary. Review the agreement and advances."))
            rec._set_system_values({"worked_days": worked, "gross": gross, "pf": pf, "esi": esi, "tds": agreement.tds,
                                    "late_days": len(period_late), "late_grace_days": len(period_late) - len(deducted_dates),
                                    "late_deducted_days": len(deducted_dates), "late_deduction": late_deduction,
                                    "late_punch_dates": ", ".join(day.isoformat() for day in period_late),
                                    "late_deduction_dates": ", ".join(day.isoformat() for day in deducted_dates),
                                    "deductions": deduction, "net": currency.round(gross - deduction), "computed_on": fields.Datetime.now()})

    def _validate_transition(self, target):
        if target in {"submitted", "approved", "done"} and not self.computed_on:
            raise ValidationError(_("Compute and review payroll before submitting it."))
        if target == "done" and not self.payment_reference:
            raise ValidationError(_("Record a payment reference before completing payroll."))
