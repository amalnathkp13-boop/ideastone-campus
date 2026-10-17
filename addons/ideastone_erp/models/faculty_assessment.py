from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class FacultyAssessment(models.Model):
    _name = "campus.faculty.assessment"
    _description = "Draft faculty internal mark calculation"
    _inherit = "campus.faculty.task"

    kind = fields.Selection([("internal", "Internal marks"), ("additional", "Additional internal marks"),
                             ("practical", "Practical external marks")], required=True, default="internal")
    academic_year = fields.Char(required=True)
    semester = fields.Char(required=True)

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict")
    subject_id = fields.Many2one("op.subject", required=True, ondelete="restrict")
    output_maximum = fields.Float(required=True, string="Internal mark maximum")
    component_ids = fields.One2many("campus.faculty.assessment.component", "assessment_id", string="Assessment components")
    total = fields.Float(compute="_compute_total", store=True, digits=(12, 2))
    weight_total = fields.Float(compute="_compute_total", store=True)

    @api.constrains("student_id", "subject_id", "user_id")
    def _check_teaching_scope(self):
        for rec in self:
            if not self.env["op.session"].search_count([
                ("faculty_id.user_id", "=", rec.user_id.id), ("subject_id", "=", rec.subject_id.id),
                ("batch_id", "in", rec.student_id.course_detail_ids.batch_id.ids),
            ]):
                raise ValidationError(_("Internal assessments require a student and subject from your allocated classes."))

    @api.depends("component_ids.score", "component_ids.maximum", "component_ids.weight", "output_maximum")
    def _compute_total(self):
        for rec in self:
            rec.weight_total = sum(rec.component_ids.mapped("weight"))
            rec.total = sum(line.score / line.maximum * line.weight / 100 * rec.output_maximum
                            for line in rec.component_ids if line.maximum > 0)

    @api.constrains("output_maximum", "state", "component_ids")
    def _check_calculation(self):
        for rec in self:
            if rec.output_maximum <= 0:
                raise ValidationError(_("Set a positive internal mark maximum."))
            if rec.state == "done" and (not rec.component_ids or abs(rec.weight_total - 100) > 0.0001):
                raise ValidationError(_("To complete a calculation, component weights must total 100%."))


class FacultyAssessmentComponent(models.Model):
    _name = "campus.faculty.assessment.component"
    _description = "Internal assessment weighted component"

    assessment_id = fields.Many2one("campus.faculty.assessment", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    maximum = fields.Float(required=True)
    score = fields.Float(required=True)
    weight = fields.Float(required=True, string="Weight (%)")

    @api.constrains("maximum", "score", "weight", "assessment_id")
    def _check_score(self):
        for line in self:
            if line.maximum <= 0 or not 0 <= line.score <= line.maximum or not 0 <= line.weight <= 100:
                raise ValidationError(_("Check maximum, score and weight (0–100%)."))
            line.assessment_id._check_calculation()
