from odoo import api, fields, models


class FacultyDocument(models.Model):
    _name = "campus.faculty.document"
    _description = "Faculty examination and teaching documents"
    _inherit = "campus.faculty.task"

    kind = fields.Selection([("certificate", "Exam certificate"), ("question", "Question paper"),
                             ("answer", "Answer key")], required=True, default="certificate")
    subject_id = fields.Many2one("op.subject", ondelete="restrict")
    exam_id = fields.Many2one("op.exam", ondelete="restrict")
    document = fields.Binary(attachment=True, required=True)
    filename = fields.Char(required=True)

    @api.constrains("subject_id", "exam_id")
    def _check_reference_access(self):
        for rec in self:
            rec.subject_id.check_access_rule("read")
            rec.exam_id.check_access_rule("read")
