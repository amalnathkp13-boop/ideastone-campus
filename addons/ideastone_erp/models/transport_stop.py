from odoo import fields, models


class TransportStop(models.Model):
    _name = "campus.transport.stop"
    _description = "Transport stage and boarding point"
    _inherit = "campus.record"
    _order = "route_id, sequence, id"

    route_id = fields.Many2one("campus.transport.route", required=True, ondelete="restrict", check_company=True)
    sequence = fields.Integer(default=10)
    pickup_time = fields.Float("Pickup time (24-hour)")
    fee = fields.Monetary()

    _sql_constraints = [
        ("stop_unique", "unique(route_id, name)", "Boarding point already exists on this route."),
        ("stop_fee", "check(fee >= 0)", "Transport fee cannot be negative."),
        ("stop_time", "check(pickup_time >= 0 AND pickup_time < 24)", "Pickup time must be between 0 and 24."),
    ]
