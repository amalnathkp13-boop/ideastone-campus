from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class PlacementDrive(models.Model):
    _name = "campus.placement.drive"
    _description = "Recruiter opportunity and interview drive"
    _inherit = "campus.approval"

    recruiter_id = fields.Many2one("res.partner", required=True, ondelete="restrict", check_company=True)
    representative_id = fields.Many2one("res.partner", ondelete="restrict", check_company=True)
    spoc_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    kind = fields.Selection([("placement", "Placement"), ("internship", "Internship"), ("training", "Training")], required=True, default="placement")
    interview_on = fields.Datetime(required=True)
    location = fields.Char(required=True)
    min_percentage = fields.Float()
    max_standing_arrears = fields.Integer()
    course_ids = fields.Many2many("op.course", string="Eligible programmes")
    job_description = fields.Text(required=True)
    candidate_ids = fields.One2many("campus.placement.candidate", "drive_id")

    @api.constrains("min_percentage", "max_standing_arrears", "representative_id", "recruiter_id")
    def _check_requirements(self):
        for rec in self:
            if not 0 <= rec.min_percentage <= 100 or rec.max_standing_arrears < 0:
                raise ValidationError(_("Check percentage and arrear eligibility limits."))
            if rec.representative_id and rec.representative_id.commercial_partner_id != rec.recruiter_id.commercial_partner_id:
                raise ValidationError(_("The representative must belong to the recruiting company."))
