from odoo.exceptions import AccessError, ValidationError

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
    review_state = fields.Selection([("draft", "Draft"), ("submitted", "Awaiting review"),
                                     ("approved", "Approved"), ("rejected", "Returned for revision")],
                                    default="draft", required=True, tracking=True, copy=False)
    review_reason = fields.Text()
    reviewed_by = fields.Many2one("res.users", readonly=True, copy=False)
    reviewed_on = fields.Datetime(readonly=True, copy=False)
    can_review = fields.Boolean(compute="_compute_can_review")

    @api.depends("review_state", "faculty_id")
    @api.depends_context("uid")
    def _compute_can_review(self):
        reviewer = self.env.user.has_group("ideastone_erp.group_academic") or self.env.user.has_group("ideastone_erp.group_manager")
        for rec in self:
            rec.can_review = reviewer and rec.review_state == "submitted" and rec.faculty_id.user_id != self.env.user

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("review_state", "draft") != "draft" or v.get("reviewed_by") or v.get("reviewed_on") for v in vals_list):
            raise AccessError(_("Lesson plans must start as drafts; review evidence is maintained by the workflow."))
        return super().create(vals_list)

    def write(self, vals):
        if {"reviewed_by", "reviewed_on"} & vals.keys():
            raise AccessError(_("Lesson review evidence is maintained by the workflow."))
        self._lock()
        if "review_reason" in vals and any(not rec.can_review for rec in self):
            raise AccessError(_("Only an independent reviewer can enter a reason while the plan awaits review."))
        if "review_state" in vals:
            if set(vals) != {"review_state"}:
                raise ValidationError(_("Save the lesson details before changing review status."))
            for rec in self:
                target = vals["review_state"]
                if target == "submitted" and rec.review_state in {"draft", "rejected"}:
                    if rec.faculty_id.user_id != self.env.user:
                        raise AccessError(_("The assigned faculty member submits the lesson plan."))
                elif target in {"approved", "rejected"} and rec.review_state == "submitted":
                    if rec.faculty_id.user_id == self.env.user or not (
                        self.env.user.has_group("ideastone_erp.group_academic") or self.env.user.has_group("ideastone_erp.group_manager")
                    ):
                        raise AccessError(_("An independent academic reviewer must decide the lesson plan."))
                    if target == "rejected" and not (rec.review_reason or "").strip():
                        raise ValidationError(_("Record the reason for returning this plan."))
                    super(TeachingPlan, rec).write({"reviewed_by": self.env.uid, "reviewed_on": fields.Datetime.now()})
                else:
                    raise ValidationError(_("This lesson review transition is not allowed."))
        elif any(rec.review_state in {"submitted", "approved"} for rec in self):
            allowed = {"execution_date", "actual_hours", "notes", "message_ids", "message_follower_ids", "activity_ids"}
            if set(vals) - allowed:
                if set(vals) != {"review_reason"} or not (
                    self.env.user.has_group("ideastone_erp.group_academic") or self.env.user.has_group("ideastone_erp.group_manager")
                ):
                    raise ValidationError(_("Submitted plan details are locked. Record delivery separately or return it for revision."))
        return super().write(vals)

    def action_submit_review(self):
        return self.write({"review_state": "submitted"})

    def action_approve_review(self):
        return self.write({"review_state": "approved"})

    def action_return_review(self):
        return self.write({"review_state": "rejected"})

    def unlink(self):
        if any(rec.review_state != "draft" for rec in self):
            raise ValidationError(_("Keep submitted lesson plans for their review history."))
        return super().unlink()

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
