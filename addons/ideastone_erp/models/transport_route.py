from odoo import fields, models


class TransportRoute(models.Model):
    _name = "campus.transport.route"
    _description = "Academic year bus route"
    _inherit = "campus.record"

    year_id = fields.Many2one("op.academic.year", required=True, ondelete="restrict", check_company=True)
    vehicle_registration = fields.Char(required=True)
    capacity = fields.Integer(required=True, default=40)
    driver = fields.Char()
    driver_phone = fields.Char()
    stop_ids = fields.One2many("campus.transport.stop", "route_id")

    _sql_constraints = [
        ("route_unique", "unique(company_id, year_id, name)", "Route name must be unique for the academic year."),
        ("route_capacity", "check(capacity > 0)", "Vehicle capacity must be positive."),
    ]
