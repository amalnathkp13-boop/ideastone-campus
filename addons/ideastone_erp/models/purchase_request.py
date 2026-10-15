from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class PurchaseRequest(models.Model):
    _name = "campus.purchase.request"
    _description = "Purchase indent, review and supplier quotation"
    _inherit = "campus.approval"

    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    department_id = fields.Many2one("op.department", required=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", check_company=True)
    quantity = fields.Float(required=True, default=1)
    vendor_id = fields.Many2one("res.partner", required=True, ondelete="restrict", check_company=True)
    unit_price = fields.Monetary(required=True)
    total = fields.Monetary(compute="_compute_total", store=True)
    required_on = fields.Date(required=True)
    justification = fields.Text(required=True)
    comparative_quote = fields.Text("Alternative supplier quotes and recommendation", required=True)
    department_reviewer_id = fields.Many2one("res.users", readonly=True, copy=False)
    finance_reviewer_id = fields.Many2one("res.users", readonly=True, copy=False)
    purchase_id = fields.Many2one("purchase.order", readonly=True, copy=False, check_company=True)

    @api.depends("quantity", "unit_price")
    def _compute_total(self):
        for rec in self:
            rec.total = rec.quantity * rec.unit_price

    @api.constrains("quantity", "unit_price")
    def _check_values(self):
        for rec in self:
            if rec.quantity <= 0 or rec.unit_price < 0:
                raise ValidationError(_("Quantity must be positive and price cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v) & {"department_reviewer_id", "finance_reviewer_id", "purchase_id"} for v in vals_list):
            raise AccessError(_("Purchase approval evidence is set by the workflow."))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) & {"department_reviewer_id", "finance_reviewer_id", "purchase_id"}:
            raise AccessError(_("Use purchase review actions to update approval evidence."))
        if "state" not in vals and any(r.department_reviewer_id or r.finance_reviewer_id for r in self):
            raise ValidationError(_("Cancel and revise the indent to change reviewed purchase details."))
        result = super().write(vals)
        if vals.get("state") == "draft":
            self._set_system_values({"department_reviewer_id": False, "finance_reviewer_id": False})
        return result

    def action_department_review(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_purchasing") or any(r.state != "submitted" for r in self):
            raise AccessError(_("A purchasing reviewer may review only submitted indents."))
        return self._set_system_values({"department_reviewer_id": self.env.uid})

    def action_finance_review(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_finance"):
            raise AccessError(_("Finance permission is required."))
        if any(r.state != "submitted" or not r.department_reviewer_id for r in self):
            raise ValidationError(_("Department review must precede finance review."))
        return self._set_system_values({"finance_reviewer_id": self.env.uid})

    def _validate_transition(self, target):
        if target == "approved" and (not self.department_reviewer_id or not self.finance_reviewer_id):
            raise ValidationError(_("Department and finance review must precede final approval."))
        if target == "cancelled" and self.purchase_id and self.purchase_id.state not in {"draft", "cancel"}:
            raise ValidationError(_("Cancel the purchase order before cancelling its indent."))

    def action_purchase(self):
        self.ensure_one()
        self._lock()
        if self.state != "approved":
            raise ValidationError(_("Final approval is required before preparing a purchase order."))
        if not self.purchase_id:
            order = self.env["purchase.order"].create({
                "partner_id": self.vendor_id.id, "company_id": self.company_id.id,
                "origin": self.name, "order_line": [(0, 0, {
                    "product_id": self.product_id.id, "name": self.product_id.display_name,
                    "product_qty": self.quantity, "product_uom": self.product_id.uom_po_id.id,
                    "price_unit": self.unit_price, "date_planned": self.required_on,
                })],
            })
            self._set_system_values({"purchase_id": order.id})
        return {"type": "ir.actions.act_window", "res_model": "purchase.order", "res_id": self.purchase_id.id, "view_mode": "form"}
