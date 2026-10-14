from odoo import fields, models


class AlumniChapter(models.Model):
    _name = "campus.alumni.chapter"
    _description = "Alumni chapter"
    _inherit = "campus.record"

    location = fields.Char(required=True)
    coordinator_id = fields.Many2one("res.partner", check_company=True)
    description = fields.Text()


class Alumni(models.Model):
    _name = "campus.alumni"
    _description = "Alumni education, career and community profile"
    _inherit = "campus.record"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict", index=True)
    graduation_year = fields.Integer(required=True)
    chapter_id = fields.Many2one("campus.alumni.chapter", ondelete="restrict", check_company=True)
    employer = fields.Char()
    designation = fields.Char()
    location = fields.Char()
    higher_studies = fields.Text()
    family_information = fields.Text()
    contact_email = fields.Char()
    contact_phone = fields.Char()
    photo = fields.Image()
    job_opportunities = fields.Text()

    _sql_constraints = [
        ("alumni_unique", "unique(student_id)", "This student already has an alumni profile."),
        ("alumni_year", "check(graduation_year BETWEEN 1900 AND 2200)", "Enter a valid graduation year."),
    ]
