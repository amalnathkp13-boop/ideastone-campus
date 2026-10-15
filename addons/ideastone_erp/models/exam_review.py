from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class ExamReview(models.Model):
    _name = "campus.exam.review"
    _description = "Exam mark verification and revaluation"
    _inherit = "campus.approval"

    result_id = fields.Many2one("op.result.line", required=True, ondelete="restrict")
    student_id = fields.Many2one(related="result_id.student_id", store=True)
    kind = fields.Selection([("verify", "Mark verification"), ("retotal", "Re-totaling"), ("revalue", "Revaluation"), ("malpractice", "Malpractice case")], required=True, default="verify")
    original_marks = fields.Integer(readonly=True, copy=False)
    revised_marks = fields.Integer(required=True)
    evaluator_id = fields.Many2one("op.faculty", required=True, ondelete="restrict")
    dummy_number = fields.Char()
    packet_number = fields.Char()
    reason = fields.Text(required=True)
    published = fields.Boolean(readonly=True, copy=False)

    @api.constrains("revised_marks", "result_id")
    def _check_marks(self):
        for rec in self:
            if not 0 <= rec.revised_marks <= rec.result_id.exam_id.total_marks:
                raise ValidationError(_("Revised marks must fall within the examination maximum."))

    def action_publish(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_manager"):
            raise AccessError(_("Campus manager permission is required to publish reviewed marks."))
        for rec in self:
            if rec.state != "approved" or rec.published or rec.kind == "malpractice":
                raise ValidationError(_("Publish an approved, unpublished mark review."))
            self.env.cr.execute("SELECT id FROM op_result_line WHERE id=%s FOR UPDATE", [rec.result_id.id])
            rec.result_id.invalidate_recordset()
            if rec.result_id.marks != rec.original_marks:
                raise ValidationError(_("The original result changed after this review was created. Create a new review."))
            rec.result_id.write({"marks": rec.revised_marks})
            rec._set_system_values({"published": True})

    def write(self, vals):
        if set(vals) & {"published", "original_marks", "result_id"}:
            raise ValidationError(_("Use Publish reviewed marks."))
        if any(r.published for r in self) and "state" in vals:
            raise ValidationError(_("Published reviews are final. Create a new review for a correction."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("published") or "original_marks" in v for v in vals_list):
            raise ValidationError(_("New reviews cannot be published."))
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            result = self.env["op.result.line"].browse(vals.get("result_id"))
            vals["original_marks"] = result.marks
            prepared.append(vals)
        return super().create(prepared)
