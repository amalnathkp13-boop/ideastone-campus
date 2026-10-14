from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class TeachingPlan(models.Model):
    _name = "campus.teaching.plan"
    _description = "Lesson plan and execution"
    _inherit = "campus.record"
    _order = "planned_date desc, id desc"

    faculty_id = fields.Many2one("op.faculty", required=True, ondelete="restrict", tracking=True)
    subject_id = fields.Many2one("op.subject", required=True, ondelete="restrict")
    batch_id = fields.Many2one("op.batch", required=True, ondelete="restrict")
    term_id = fields.Many2one("op.academic.term", required=True, ondelete="restrict", check_company=True)
    planned_date = fields.Date(required=True)
    unit = fields.Char(required=True)
    topic = fields.Text(required=True)
    planned_hours = fields.Float(required=True, default=1)
    teaching_aid = fields.Char()
    learning_aid = fields.Char()
    co_level = fields.Char("Course outcome / knowledge level")
    reference = fields.Text("Textbook, pages and reference URL")
    execution_date = fields.Date()
    actual_hours = fields.Float()
    notes = fields.Text("Notes of lesson")
    attachment_ids = fields.Many2many("ir.attachment", string="Teaching materials")
    variance = fields.Float(compute="_compute_variance", store=True)

    @api.depends("planned_hours", "actual_hours")
    def _compute_variance(self):
        for rec in self:
            rec.variance = rec.actual_hours - rec.planned_hours

    @api.constrains("planned_hours", "actual_hours", "execution_date", "notes")
    def _check_hours(self):
        for rec in self:
            if rec.planned_hours <= 0 or rec.actual_hours < 0:
                raise ValidationError(_("Planned hours must be positive and actual hours cannot be negative."))
            if rec.actual_hours and (not rec.execution_date or not rec.notes):
                raise ValidationError(_("Record the delivery date and lesson notes when recording actual hours."))
