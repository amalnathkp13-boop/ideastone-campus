from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class FacultyAchievement(models.Model):
    _name = "campus.faculty.achievement"
    _description = "Faculty development and appraisal"
    _inherit = "campus.approval"

    faculty_id = fields.Many2one("op.faculty", required=True, ondelete="restrict")
    kind = fields.Selection([
        ("fdp", "FDP / workshop"), ("paper", "Paper / publication"), ("training", "Industrial training"),
        ("guest", "Guest lecture"), ("mou", "MOU / institutional activity"), ("appraisal", "Self appraisal"),
        ("patent", "Patent / research"), ("award", "Award"),
        ("mphil", "M.Phil supervision"), ("review", "Review / editorial / consultancy"),
        ("vacation", "Vacation course"), ("mooc", "MOOC"),
        ("qualified", "Qualified course"), ("resource", "Resource personnel"),
    ], required=True, default="fdp")
    date_from = fields.Date(required=True)
    date_to = fields.Date()
    organizer = fields.Char()
    venue = fields.Char()
    level = fields.Selection([("institution", "Institution"), ("national", "National"), ("international", "International")])
    reference = fields.Char("Publication / DOI / application reference")
    description = fields.Text()
    evidence = fields.Binary(attachment=True)
    filename = fields.Char()
    score = fields.Float("Appraisal score (0–100)")
    reviewer_notes = fields.Text(groups="ideastone_erp.group_manager")

    @api.constrains("date_from", "date_to", "score")
    def _check_values(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from or not 0 <= rec.score <= 100:
                raise ValidationError(_("Check the date range and score (0–100)."))
