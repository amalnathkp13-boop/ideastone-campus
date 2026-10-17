from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class StudentEducation(models.Model):
    _name = "campus.student.education"
    _description = "Assigned student previous academic information"
    _inherit = "campus.faculty.task"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict")
    qualification = fields.Char(required=True)
    institution = fields.Char(required=True)
    board = fields.Char("Board / university")
    completion_year = fields.Integer(required=True)
    score = fields.Float()
    maximum = fields.Float(required=True, default=100)
    percentage = fields.Float(compute="_compute_percentage", store=True)

    @api.depends("score", "maximum")
    def _compute_percentage(self):
        for rec in self:
            rec.percentage = rec.score / rec.maximum * 100 if rec.maximum else 0

    @api.constrains("student_id", "user_id", "company_id", "score", "maximum", "completion_year")
    def _check_education(self):
        for rec in self:
            if not 1900 <= rec.completion_year <= fields.Date.today().year + 1 or not 0 <= rec.score <= rec.maximum or rec.maximum <= 0:
                raise ValidationError(_("Check the completion year, marks and positive maximum."))
            if not self.env["op.session"].search_count([
                ("faculty_id.user_id", "=", rec.user_id.id), ("batch_id", "in", rec.student_id.course_detail_ids.batch_id.ids),
                ("company_id", "=", rec.company_id.id), ("state", "!=", "cancel"),
            ]):
                raise ValidationError(_("Record previous academic information only for your assigned students."))
