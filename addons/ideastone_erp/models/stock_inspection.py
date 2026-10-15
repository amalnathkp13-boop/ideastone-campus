from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class StockInspection(models.Model):
    _name = "campus.stock.inspection"
    _description = "Goods receipt quality and quantity inspection"
    _inherit = "campus.approval"

    picking_id = fields.Many2one("stock.picking", required=True, ondelete="restrict", check_company=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", check_company=True)
    received_quantity = fields.Float(required=True)
    accepted_quantity = fields.Float(required=True)
    rejected_quantity = fields.Float(compute="_compute_rejected", store=True)
    quality_notes = fields.Text(required=True)
    inspected_on = fields.Date(required=True, default=fields.Date.today)

    @api.depends("received_quantity", "accepted_quantity")
    def _compute_rejected(self):
        for rec in self:
            rec.rejected_quantity = rec.received_quantity - rec.accepted_quantity

    @api.constrains("received_quantity", "accepted_quantity", "picking_id", "product_id")
    def _check_inspection(self):
        for rec in self:
            if rec.received_quantity <= 0 or not 0 <= rec.accepted_quantity <= rec.received_quantity:
                raise ValidationError(_("Accepted quantity must be between zero and received quantity."))
            if rec.picking_id.picking_type_id.code != "incoming" or rec.product_id not in rec.picking_id.move_ids.product_id:
                raise ValidationError(_("Select a product on the incoming goods receipt."))


class StockPicking(models.Model):
    _inherit = "stock.picking"

    campus_inspection_required = fields.Boolean("Campus inspection required")
    campus_inspection_ids = fields.One2many("campus.stock.inspection", "picking_id")

    def button_validate(self):
        for picking in self.filtered("campus_inspection_required"):
            approved = picking.campus_inspection_ids.filtered(lambda r: r.state == "approved")
            for move in picking.move_ids.filtered(lambda m: m.state != "cancel"):
                inspections = approved.filtered(lambda r, move=move: r.product_id == move.product_id)
                if not inspections or sum(inspections.mapped("accepted_quantity")) < move.quantity:
                    raise ValidationError(_("Approved quality and quantity inspection is required for the received goods."))
        return super().button_validate()
