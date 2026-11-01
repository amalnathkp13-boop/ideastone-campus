from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import _, api, fields, models


class PrincipalRequest(models.Model):
    _name = "ideastone.principal.request"
    _description = "Principal Review Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Subject", required=True, tracking=True)
    request_type = fields.Selection([
        ("admission", "Admission"), ("leave", "Staff Leave"),
        ("academic", "Academic"), ("finance", "Finance"),
        ("discipline", "Discipline"), ("facility", "Campus Facility"),
        ("other", "Other"),
    ], required=True, default="other", tracking=True)
    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    student_id = fields.Many2one("op.student", string="Student")
    faculty_id = fields.Many2one("op.faculty", string="Faculty")
    admission_id = fields.Many2one("op.admission", string="Admission application")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    due_date = fields.Date()
    description = fields.Text(required=True)
    decision_note = fields.Text(tracking=True)
    decided_by_id = fields.Many2one("res.users", readonly=True)
    decided_on = fields.Datetime(readonly=True)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("approved", "Approved"), ("rejected", "Rejected"),
    ], default="draft", required=True, tracking=True)

    @api.constrains("request_type", "date_from", "date_to")
    def _check_dates(self):
        for request in self:
            if request.request_type == "leave" and not (request.date_from and request.date_to):
                raise ValidationError(_("Staff leave needs a start and end date."))
            if request.date_from and request.date_to and request.date_to < request.date_from:
                raise ValidationError(_("The end date must be on or after the start date."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("ideastone_principal.group_principal"):
            for vals in vals_list:
                if (vals.get("state", "draft") != "draft"
                        or vals.get("requester_id", self.env.uid) != self.env.uid
                        or vals.get("company_id", self.env.company.id) not in self.env.companies.ids):
                    raise AccessError(_("You can only create your own draft requests."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            if any(record.requester_id != self.env.user or record.state != "draft" for record in self):
                raise AccessError(_("Only a principal can change submitted requests."))
            if set(vals) & {"state", "requester_id", "company_id", "decision_note", "decided_by_id", "decided_on"}:
                raise AccessError(_("Use Submit to send a request for review."))
        return super().write(vals)

    def unlink(self):
        if any(record.state != "draft" for record in self):
            raise UserError(_("Only draft requests can be deleted."))
        return super().unlink()

    def action_submit(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Only draft requests can be submitted."))
            if request.requester_id != self.env.user and not self.env.user.has_group("ideastone_principal.group_principal"):
                raise AccessError(_("You can only submit your own request."))
            super(PrincipalRequest, request).write({"state": "submitted"})

    def _decide(self, state):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            raise AccessError(_("Only a principal can decide requests."))
        for request in self:
            if request.state != "submitted":
                raise UserError(_("Only submitted requests can be decided."))
            if state == "rejected" and not request.decision_note:
                raise UserError(_("Add a decision note before rejecting."))
            request.write({"state": state, "decided_by_id": self.env.uid, "decided_on": fields.Datetime.now()})

    def action_approve(self):
        self._decide("approved")

    def action_reject(self):
        self._decide("rejected")
