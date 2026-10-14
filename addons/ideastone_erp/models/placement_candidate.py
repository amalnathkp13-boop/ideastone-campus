from odoo.exceptions import ValidationError

from odoo import _, api, fields, models


class PlacementCandidate(models.Model):
    _name = "campus.placement.candidate"
    _description = "Placement shortlisting and outcomes"
    _inherit = "campus.record"

    drive_id = fields.Many2one("campus.placement.drive", required=True, ondelete="restrict", check_company=True)
    student_id = fields.Many2one("op.student", required=True, ondelete="restrict", index=True)
    percentage = fields.Float(compute="_compute_results")
    standing_arrears = fields.Integer(compute="_compute_results")
    ever_had_arrears = fields.Boolean(compute="_compute_results")
    eligible = fields.Boolean(compute="_compute_results")
    state = fields.Selection([
        ("applied", "Applied"), ("shortlisted", "Shortlisted"), ("interviewed", "Interviewed"),
        ("selected", "Selected"), ("rejected", "Rejected"),
    ], default="applied", required=True, tracking=True)
    interview_notes = fields.Text()
    offer_reference = fields.Char()
    offered_salary = fields.Monetary()

    _sql_constraints = [("candidate_unique", "unique(drive_id, student_id)", "Student already participates in this drive.")]

    @api.depends("student_id", "drive_id.min_percentage", "drive_id.max_standing_arrears", "drive_id.course_ids")
    def _compute_results(self):
        for rec in self:
            results = self.env["op.result.line"].search([("student_id", "=", rec.student_id.id)], order="id desc")
            latest = {}
            for line in results:
                latest.setdefault(line.exam_id.subject_id.id, line)
            lines = list(latest.values())
            rec.percentage = sum(100 * line.marks / line.exam_id.total_marks for line in lines if line.exam_id.total_marks) / len(lines) if lines else 0
            rec.standing_arrears = sum(line.status == "fail" for line in lines)
            rec.ever_had_arrears = any(line.status == "fail" for line in results)
            courses = rec.student_id.course_detail_ids.course_id
            programme_ok = not rec.drive_id.course_ids or bool(courses & rec.drive_id.course_ids)
            rec.eligible = bool(lines) and programme_ok and rec.percentage >= rec.drive_id.min_percentage and rec.standing_arrears <= rec.drive_id.max_standing_arrears

    @api.constrains("state", "student_id", "drive_id", "offered_salary")
    def _check_selection(self):
        for rec in self:
            if rec.offered_salary < 0:
                raise ValidationError(_("Offered salary cannot be negative."))
            if rec.state in {"shortlisted", "interviewed", "selected"} and (rec.drive_id.state != "approved" or not rec.eligible):
                raise ValidationError(_("Approve the drive and verify candidate academic eligibility before shortlisting."))
