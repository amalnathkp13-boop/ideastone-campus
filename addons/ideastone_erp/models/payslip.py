from datetime import datetime, time, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


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
    tds = fields.Monetary(readonly=True)
    net = fields.Monetary(readonly=True)
    computed_on = fields.Datetime(readonly=True)
    payment_reference = fields.Char()

    _sql_constraints = [("payslip_unique", "unique(employee_id, date_from, date_to)", "Payroll already exists for this employee and period.")]

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
        if set(vals) & {"worked_days", "gross", "pf", "esi", "tds", "deductions", "net", "computed_on"}:
            raise AccessError(_("Payroll totals are calculated by Compute payroll."))
        result = super().write(vals)
        if set(vals) - {"state", "message_follower_ids", "activity_ids", "message_ids"}:
            self._set_system_values({"computed_on": False})
        return result

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v) & {"worked_days", "gross", "pf", "esi", "tds", "deductions", "net", "computed_on"} for v in vals_list):
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
            start = timezone.localize(datetime.combine(rec.date_from, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            end = timezone.localize(datetime.combine(rec.date_to + timedelta(days=1), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
            attendance = self.env["hr.attendance"].search([
                ("employee_id", "=", rec.employee_id.id), ("check_in", "<", end), ("check_out", ">", start),
            ])
            hours = sum(att._get_worked_hours_in_range(max(att.check_in, start), min(att.check_out, end)) for att in attendance)
            worked = min(hours / agreement.daily_hours, rec.working_days)
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
            deduction = currency.round(agreement.fixed_deduction + rec.advance_deduction + pf + esi + agreement.tds)
            if deduction > gross:
                raise ValidationError(_("Deductions exceed earned salary. Review the agreement and advances."))
            rec._set_system_values({"worked_days": worked, "gross": gross, "pf": pf, "esi": esi, "tds": agreement.tds,
                                    "deductions": deduction, "net": currency.round(gross - deduction), "computed_on": fields.Datetime.now()})

    def _validate_transition(self, target):
        if target in {"submitted", "approved", "done"} and not self.computed_on:
            raise ValidationError(_("Compute and review payroll before submitting it."))
        if target == "done" and not self.payment_reference:
            raise ValidationError(_("Record a payment reference before completing payroll."))
