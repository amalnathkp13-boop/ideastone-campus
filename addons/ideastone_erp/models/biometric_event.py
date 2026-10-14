from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class BiometricEvent(models.Model):
    _name = "campus.biometric.event"
    _description = "Idempotent imported attendance device event"
    _inherit = "campus.record"

    device = fields.Char(required=True)
    external_reference = fields.Char(required=True, copy=False)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict", check_company=True)
    check_in = fields.Datetime(required=True)
    check_out = fields.Datetime()
    attendance_id = fields.Many2one("hr.attendance", readonly=True, copy=False)

    _sql_constraints = [("device_event_unique", "unique(company_id, device, external_reference)", "This device event has already been imported.")]

    @api.constrains("check_in", "check_out")
    def _check_times(self):
        for rec in self:
            if rec.check_out and rec.check_out <= rec.check_in:
                raise ValidationError(_("Attendance checkout must follow check-in."))

    def action_import(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_people"):
            raise AccessError(_("HR attendance permission is required."))
        for rec in self:
            if not rec.attendance_id:
                att = self.env["hr.attendance"].create({"employee_id": rec.employee_id.id, "check_in": rec.check_in, "check_out": rec.check_out})
                super(BiometricEvent, rec).write({"attendance_id": att.id})
        return True

    def write(self, vals):
        if "attendance_id" in vals or any(r.attendance_id for r in self):
            raise ValidationError(_("Imported attendance events are immutable. Correct the attendance record through HR."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("attendance_id") for v in vals_list):
            raise AccessError(_("Use Import attendance to link a device event."))
        return super().create(vals_list)

    def unlink(self):
        if any(r.attendance_id for r in self):
            raise ValidationError(_("Retain imported attendance events for audit."))
        return super().unlink()
