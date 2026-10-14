from odoo import fields, models


class Asset(models.Model):
    _name = "campus.asset"
    _description = "Fixed asset custody register"
    _inherit = "campus.record"

    asset_code = fields.Char(required=True, copy=False, index=True)
    serial_number = fields.Char()
    department_id = fields.Many2one("op.department", ondelete="restrict")
    custodian_id = fields.Many2one("hr.employee", ondelete="restrict", check_company=True)
    acquisition_date = fields.Date(required=True, default=fields.Date.today)
    acquisition_value = fields.Monetary()
    location = fields.Char(required=True)
    equipment_id = fields.Many2one("maintenance.equipment", check_company=True)
    condition = fields.Selection([("good", "Good"), ("repair", "Requires repair"), ("disposed", "Disposed")], default="good", required=True)
    verified_on = fields.Date()
    notes = fields.Text()

    _sql_constraints = [
        ("asset_unique", "unique(company_id, asset_code)", "Asset code must be unique."),
        ("asset_value", "check(acquisition_value >= 0)", "Acquisition value cannot be negative."),
    ]
