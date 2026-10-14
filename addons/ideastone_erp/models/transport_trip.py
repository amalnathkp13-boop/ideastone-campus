from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class TransportTrip(models.Model):
    _name = "campus.transport.trip"
    _description = "Trip, fuel and transport expense register"
    _inherit = "campus.record"
    _order = "date desc"

    route_id = fields.Many2one("campus.transport.route", required=True, ondelete="restrict", check_company=True)
    date = fields.Date(required=True, default=fields.Date.today)
    odometer_start = fields.Float(required=True)
    odometer_end = fields.Float(required=True)
    fuel_litres = fields.Float()
    fuel_cost = fields.Monetary()
    other_expense = fields.Monetary()
    distance = fields.Float(compute="_compute_usage", store=True)
    mileage = fields.Float(compute="_compute_usage", store=True)
    notes = fields.Text()

    @api.depends("odometer_start", "odometer_end", "fuel_litres")
    def _compute_usage(self):
        for rec in self:
            rec.distance = rec.odometer_end - rec.odometer_start
            rec.mileage = rec.distance / rec.fuel_litres if rec.fuel_litres else 0

    @api.constrains("odometer_start", "odometer_end", "fuel_litres", "fuel_cost", "other_expense")
    def _check_usage(self):
        for rec in self:
            if rec.odometer_start < 0 or rec.odometer_end < rec.odometer_start or min(rec.fuel_litres, rec.fuel_cost, rec.other_expense) < 0:
                raise ValidationError(_("Check odometer readings, fuel and expense amounts."))
