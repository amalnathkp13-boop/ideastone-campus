from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class HostelRoom(models.Model):
    _name = "campus.hostel.room"
    _description = "Hostel rooms and vacancies"
    _inherit = "campus.record"

    building = fields.Char(required=True, index=True)
    capacity = fields.Integer(required=True, default=2)
    air_conditioned = fields.Boolean()
    attached_bathroom = fields.Boolean()
    facilities = fields.Text()
    warden_id = fields.Many2one("res.users")
    allocation_ids = fields.One2many("campus.hostel.allocation", "room_id")
    occupied = fields.Integer(compute="_compute_occupancy")
    vacancy = fields.Integer(compute="_compute_occupancy")

    _sql_constraints = [
        ("room_unique", "unique(company_id, building, name)", "Room number must be unique within a building."),
        ("room_capacity", "check(capacity > 0)", "Room capacity must be positive."),
    ]

    @api.depends("allocation_ids.state", "allocation_ids.date_from", "allocation_ids.date_to", "capacity")
    def _compute_occupancy(self):
        today = fields.Date.today()
        for rec in self:
            rec.occupied = len(rec.allocation_ids.filtered(
                lambda a: a.state == "approved" and a.date_from <= today and (not a.date_to or a.date_to >= today)
            ))
            rec.vacancy = rec.capacity - rec.occupied

    def write(self, vals):
        if "capacity" in vals:
            self._lock()
        result = super().write(vals)
        if "capacity" in vals:
            for allocation in self.allocation_ids.filtered(lambda a: a.state == "approved"):
                allocation._check_allocation()
        return result

    @api.constrains("active")
    def _check_active(self):
        for rec in self:
            if not rec.active and rec.allocation_ids.filtered(lambda a: a.state == "approved"):
                raise ValidationError(_("Close all resident allocations before archiving a room."))
