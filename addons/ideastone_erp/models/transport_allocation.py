from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class TransportAllocation(models.Model):
    _name = "campus.transport.allocation"
    _description = "Student transport allocation"
    _inherit = "campus.approval"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict", index=True)
    stop_id = fields.Many2one("campus.transport.stop", required=True, ondelete="restrict", check_company=True)
    route_id = fields.Many2one(related="stop_id.route_id", store=True)
    year_id = fields.Many2one(related="route_id.year_id", store=True)
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False, check_company=True)

    @api.constrains("state", "stop_id", "student_id")
    def _check_capacity(self):
        for rec in self.filtered(lambda a: a.state == "approved"):
            rec.route_id._lock()
            self.env.cr.execute("SELECT id FROM op_student WHERE id = %s FOR UPDATE", [rec.student_id.id])
            allocations = self.sudo().search([("state", "=", "approved"), ("year_id", "=", rec.year_id.id)])
            if len(allocations.filtered(lambda a, rec=rec: a.student_id == rec.student_id)) > 1:
                raise ValidationError(_("A student may have only one active transport allocation per year."))
            if len(allocations.filtered(lambda a, rec=rec: a.route_id == rec.route_id)) > rec.route_id.capacity:
                raise ValidationError(_("Vehicle seating capacity is exceeded."))

    def action_invoice(self):
        self.ensure_one()
        self._lock()
        if self.state != "approved":
            raise ValidationError(_("Approve the transport allocation before raising demand."))
        if not self.invoice_id:
            if self.stop_id.fee <= 0:
                raise ValidationError(_("Configure a positive fee on the boarding point."))
            invoice = self.env["account.move"].create({
                "move_type": "out_invoice", "partner_id": self.student_id.partner_id.id,
                "company_id": self.company_id.id, "invoice_date": fields.Date.today(),
                "invoice_line_ids": [(0, 0, {"name": f"Transport: {self.route_id.name} / {self.stop_id.name}", "quantity": 1, "price_unit": self.stop_id.fee})],
            })
            # Bypass only business-data lock after the permission-checked invoice creation.
            self._set_system_values({"invoice_id": invoice.id})
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.invoice_id.id, "view_mode": "form"}
