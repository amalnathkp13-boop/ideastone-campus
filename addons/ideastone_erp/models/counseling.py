from odoo import fields, models


class Counseling(models.Model):
    _name = "campus.counseling"
    _description = "Mentor counseling and parent meetings"
    _inherit = "campus.record"
    _order = "date desc"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict", index=True)
    mentor_id = fields.Many2one("op.faculty", required=True, ondelete="restrict")
    date = fields.Date(required=True, default=fields.Date.today)
    kind = fields.Selection([("student", "Student counseling"), ("parent", "Parent meeting")], default="student", required=True)
    discussion = fields.Text(required=True)
    outcome = fields.Text()
    shared_remarks = fields.Text("Remarks visible to student and parent")
    follow_up_date = fields.Date()
    future_plan = fields.Selection([
        ("job", "Employment"), ("studies", "Higher studies"), ("business", "Entrepreneurship"),
        ("government", "Government examinations"), ("other", "Other"),
    ])
