from odoo import fields, models


class OpStudent(models.Model):
    """Indian-college fields on the OpenEduCat student record."""

    _inherit = "op.student"

    register_no = fields.Char(
        "University register no", index=True, copy=False,
        help="Register number allotted by the affiliating university",
    )
    admission_quota = fields.Selection(
        [("govt", "Government"), ("mgmt", "Management"), ("nri", "NRI")],
        string="Admission quota", default="govt",
    )
    community = fields.Selection(
        [("oc", "OC"), ("bc", "BC"), ("mbc", "MBC"), ("sc", "SC"), ("st", "ST"), ("other", "Other")],
        string="Community (for scholarship)",
    )
    is_hosteller = fields.Boolean("Hosteller")
    uses_transport = fields.Boolean("Uses college bus")
    aadhaar_last4 = fields.Char("Aadhaar (last 4)", size=4)

    _sql_constraints = [
        ("ideastone_register_no_unique", "unique(register_no)", "This university register number is already used."),
    ]
