from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StudentLeaveRouting(models.Model):
    _name = "campus.student.leave.routing"
    _description = "College managed student leave approval routing"
    _inherit = "campus.record"

    student_id = fields.Many2one("op.student", required=True, ondelete="restrict")
    advisor_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    hod_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    principal_id = fields.Many2one("res.users", ondelete="restrict")

    _sql_constraints = [("student_route_unique", "unique(student_id,company_id)", "Configure one leave route per student and college.")]

    @api.constrains("advisor_id", "hod_id", "principal_id", "company_id", "student_id")
    def _check_route(self):
        for rec in self:
            users = rec.advisor_id | rec.hod_id | rec.principal_id
            if not rec.advisor_id.has_group("openeducat_core.group_op_faculty"):
                raise ValidationError(_("The advisor must be a faculty account."))
            if len(users) != (3 if rec.principal_id else 2):
                raise ValidationError(_("Each approval stage must have a different person."))
            if any(not user.active or not user.has_group("base.group_user") or rec.company_id not in user.company_ids for user in users):
                raise ValidationError(_("Approvers must be active internal accounts in this college."))
            if rec.student_id.company_id and rec.student_id.company_id != rec.company_id:
                raise ValidationError(_("The student must belong to this college."))


class StudentLeave(models.Model):
    _name = "campus.student.leave"
    _description = "Student leave with advisor, HOD and optional principal approval"
    _inherit = "campus.faculty.task"

    routing_id = fields.Many2one("campus.student.leave.routing", required=True, ondelete="restrict")
    student_id = fields.Many2one("op.student", required=True, readonly=True, ondelete="restrict")
    advisor_id = fields.Many2one("res.users", readonly=True)
    hod_id = fields.Many2one("res.users", readonly=True)
    principal_id = fields.Many2one("res.users", readonly=True)
    state = fields.Selection([("draft", "Draft"), ("advisor", "Advisor review"), ("hod", "HOD review"),
                              ("principal", "Principal review"), ("approved", "Approved"),
                              ("rejected", "Rejected")], required=True, default="draft", tracking=True)
    reason = fields.Text(required=True)
    decision_reason = fields.Text()
    decision_log = fields.Text(readonly=True, copy=False)
    can_decide = fields.Boolean(compute="_compute_can_decide")

    @api.onchange("routing_id")
    def _onchange_routing_id(self):
        for rec in self:
            rec.student_id = rec.routing_id.student_id
            rec.advisor_id = rec.routing_id.advisor_id
            rec.hod_id = rec.routing_id.hod_id
            rec.principal_id = rec.routing_id.principal_id

    @api.depends("state", "advisor_id", "hod_id", "principal_id")
    @api.depends_context("uid")
    def _compute_can_decide(self):
        for rec in self:
            rec.can_decide = rec.state in {"advisor", "hod", "principal"} and rec[f"{rec.state}_id"] == self.env.user

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            route = self.env["campus.student.leave.routing"].browse(vals.get("routing_id")).exists()
            route.check_access_rights("read")
            route.check_access_rule("read")
            if not route or route.advisor_id != self.env.user or not route.active or route.company_id != self.env.company:
                raise AccessError(_("An active college-managed advisor routing is required."))
            if vals.get("state", "draft") != "draft" or vals.get("decision_log"):
                raise AccessError(_("Leave requests must start as drafts."))
            vals.update(student_id=route.student_id.id, advisor_id=route.advisor_id.id, hod_id=route.hod_id.id,
                        principal_id=route.principal_id.id, company_id=route.company_id.id)
        return super().create(vals_list)

    def write(self, vals):
        if {"student_id", "routing_id", "advisor_id", "hod_id", "principal_id", "decision_log"} & vals.keys():
            raise AccessError(_("Approval routing and decision evidence cannot be changed on a request."))
        if "state" not in vals:
            for rec in self:
                if rec.state == "draft" and rec.user_id != self.env.user:
                    raise AccessError(_("Only the filing advisor can edit a draft leave request."))
                if "decision_reason" in vals and rec.state != "draft" and not rec.can_decide:
                    raise AccessError(_("Only the current reviewer can enter a decision reason."))
        if "state" in vals:
            if set(vals) != {"state"}:
                raise ValidationError(_("Save the reason before changing approval status."))
            self._lock()
            for rec in self:
                target = vals["state"]
                expected = {"draft": "advisor", "advisor": "hod", "hod": "principal" if rec.principal_id else "approved",
                            "principal": "approved"}.get(rec.state)
                actor = rec.user_id if rec.state == "draft" else rec[f"{rec.state}_id"] if rec.state in {"advisor", "hod", "principal"} else self.env["res.users"]
                if actor != self.env.user or target not in {expected, "rejected"} or not expected:
                    raise AccessError(_("Only the assigned reviewer can perform the next approval step."))
                if target == "rejected" and not rec.decision_reason:
                    raise ValidationError(_("Record a rejection reason first."))
                entry = f"{fields.Datetime.now()} | {self.env.user.name} | {rec.state} -> {target} | {rec.decision_reason or ''}"
                super(StudentLeave, rec).write({"decision_log": (rec.decision_log or "") + entry + "\n", "decision_reason": False})
        elif any(rec.state != "draft" for rec in self) and set(vals) - {"decision_reason", "message_ids", "message_follower_ids", "activity_ids"}:
            raise ValidationError(_("Submitted leave details are locked; file a revised request if needed."))
        return super().write(vals)

    def action_submit(self):
        return self.write({"state": "advisor"})

    def action_approve(self):
        for rec in self:
            target = {"advisor": "hod", "hod": "principal" if rec.principal_id else "approved", "principal": "approved"}.get(rec.state)
            rec.write({"state": target})

    def action_reject(self):
        return self.write({"state": "rejected"})

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise ValidationError(_("Submitted leave requests retain their decision history."))
        return super().unlink()
