from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class Feedback(models.Model):
    _name = "campus.feedback"
    _description = "Student, parent and staff feedback"
    _inherit = "campus.record"
    _order = "create_date desc"

    respondent_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict")
    student_id = fields.Many2one("op.student", ondelete="restrict")
    faculty_id = fields.Many2one("op.faculty", string="Faculty being reviewed", ondelete="restrict")
    kind = fields.Selection([("student", "Student"), ("parent", "Parent"), ("staff", "Staff")], required=True)
    period = fields.Char(required=True)
    target_key = fields.Char(compute="_compute_target", store=True, required=True, precompute=True)
    score = fields.Integer(required=True, default=3)
    comments = fields.Text()

    _sql_constraints = [
        ("feedback_score", "check(score BETWEEN 1 AND 5)", "Feedback score must be from 1 to 5."),
        ("feedback_unique", "unique(company_id, respondent_id, kind, period, target_key)", "Feedback has already been submitted for this period and target."),
    ]

    @api.depends("faculty_id")
    def _compute_target(self):
        for rec in self:
            rec.target_key = str(rec.faculty_id.id or 0)

    @api.constrains("kind", "student_id")
    def _check_student(self):
        for rec in self:
            if rec.kind in {"student", "parent"} and not rec.student_id:
                raise ValidationError(_("Student or parent feedback requires a linked student."))
