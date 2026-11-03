from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

from .staff_workspace import principal_access


class StaffApplication(models.Model):
    _name = "ideastone.principal.staff.application"
    _description = "Staff recruitment review"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True
    _order = "create_date desc, id desc"

    name = fields.Char("Applicant", required=True, tracking=True)
    reference = fields.Char(default=lambda self: _("New"), readonly=True, copy=False)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    staff_type = fields.Selection([("teaching", "Teaching"), ("non_teaching", "Non-teaching")], required=True, default="teaching")
    role = fields.Char(required=True, tracking=True)
    department_id = fields.Many2one("op.department", required=True, check_company=True, ondelete="restrict")
    qualification = fields.Char(required=True)
    experience = fields.Char(required=True)
    documents = fields.Selection([("incomplete", "Incomplete"), ("verified", "Verified")], required=True, default="incomplete", tracking=True)
    interview_date = fields.Datetime(tracking=True)
    review = fields.Text("Recruitment panel review", tracking=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Supporting documents")
    state = fields.Selection([("pending", "Pending"), ("interview", "Interview"),
        ("approved", "Approved"), ("rejected", "Rejected")], default="pending", required=True, tracking=True, copy=False)
    decision_note = fields.Text(tracking=True, copy=False)
    decided_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    decided_on = fields.Datetime(readonly=True, copy=False)

    def _check_scope(self):
        if any(r.company_id != self.env.company for r in self):
            raise AccessError(_("Choose an application in the active college."))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if not self.env.su and (vals.get("state", "pending") != "pending" or
                                   any(vals.get(k) for k in ("decided_by_id", "decided_on")) or
                                   vals.get("reference") not in (None, False, "", "New", _("New"))):
                raise ValidationError(_("New applications must start pending review."))
            if vals.get("company_id", self.env.company.id) != self.env.company.id:
                raise AccessError(_("Create applications in the active college."))
            vals["reference"] = self.env["ir.sequence"].next_by_code("principal.staff.application")
            if not vals["reference"]:
                raise ValidationError(_("Configure the staff application sequence for this college."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_scope()
        if not self.env.su and (set(vals) & {"state", "decided_by_id", "decided_on", "reference", "company_id"} or
                               any(r.state in ("approved", "rejected") for r in self)):
            raise ValidationError(_("Decided applications are locked. Use the review actions to record a decision."))
        return super().write(vals)

    def unlink(self):
        if any(r.state in ("approved", "rejected") for r in self):
            raise ValidationError(_("Keep decided applications for the recruitment audit trail."))
        return super().unlink()

    def action_schedule_interview(self):
        self._check_scope()
        if any(r.state != "pending" or not r.interview_date for r in self):
            raise ValidationError(_("Set an interview date on a pending application first."))
        return super().write({"state": "interview"})

    def _decide(self, decision, note=""):
        principal_access(self.env)
        self._check_scope()
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.env.cr.execute("SELECT id FROM ideastone_principal_staff_application WHERE id IN %s FOR UPDATE", [tuple(self.ids)])
        self.invalidate_recordset(["state", "documents"])
        if any(r.state not in ("pending", "interview") for r in self):
            raise ValidationError(_("This application has already been decided."))
        if decision == "approved" and any(r.documents != "verified" for r in self):
            raise ValidationError(_("Verify the supporting documents before approval."))
        if decision == "rejected" and not note.strip():
            raise ValidationError(_("Record a reason for rejection."))
        return super().write({"state": decision, "decision_note": note.strip(),
                              "decided_by_id": self.env.uid, "decided_on": fields.Datetime.now()})

    def action_approve(self):
        for record in self:
            record._decide("approved", record.decision_note or "")
        return True

    def action_reject(self):
        for record in self:
            record._decide("rejected", record.decision_note or "")
        return True
