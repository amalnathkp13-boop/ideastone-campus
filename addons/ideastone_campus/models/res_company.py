from odoo import fields, models


class ResCompany(models.Model):
    """Extra identity fields a college prints on receipts and reports."""

    _inherit = "res.company"

    campus_affiliation = fields.Char(
        "Affiliated to", help="e.g. Anna University, Chennai — printed on fee receipts and marksheets"
    )
    campus_approval = fields.Char("Approved by", help="e.g. AICTE, New Delhi")
    campus_naac_grade = fields.Char("NAAC grade")
    campus_code = fields.Char("College code", help="Counselling / university college code")
