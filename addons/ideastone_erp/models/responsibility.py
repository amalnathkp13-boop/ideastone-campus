from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class Responsibility(models.Model):
    _name = "campus.responsibility"
    _description = "Approved faculty responsibility"
    _inherit = "campus.record"
    _order = "id desc"

    name = fields.Char(default="Library In-charge", readonly=True)
    faculty_id = fields.Many2one("op.faculty", required=True, ondelete="restrict")
    account_id = fields.Many2one("res.users", required=True, readonly=True, copy=False, ondelete="restrict")
    role = fields.Selection([("library", "Library In-charge")], required=True, default="library")
    media_type_ids = fields.Many2many("op.media.type", string="Permitted collections", required=True)
    date_from = fields.Date(required=True, default=lambda self: self._college_today())
    date_to = fields.Date(required=True)
    justification = fields.Text(required=True)
    state = fields.Selection([
        ("draft", "Draft"), ("requested", "Pending approval"), ("approved", "Approved"),
        ("revoked", "Revoked"), ("rejected", "Rejected"),
    ], required=True, default="draft", readonly=True, tracking=True, copy=False)
    requested_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_on = fields.Datetime(readonly=True, copy=False)
    decision_reason = fields.Text(readonly=True, copy=False)
    effective = fields.Boolean(compute="_compute_effective")

    def _college_today(self):
        # Appointment validity is institution-wide: use the college's timezone, not each user's.
        tz = self.env.company.partner_id.tz or "Asia/Kolkata"
        return fields.Date.context_today(self.with_context(tz=tz))

    def _compute_effective(self):
        today = self._college_today()
        for rec in self:
            rec.effective = bool(rec.state == "approved" and rec.active and rec.faculty_id.active
                                 and rec.account_id.active and rec.account_id == rec.faculty_id.user_id
                                 and rec.date_from <= today <= rec.date_to)

    @api.constrains("faculty_id", "company_id", "date_from", "date_to", "media_type_ids", "justification")
    def _check_scope(self):
        for rec in self:
            account = rec.faculty_id.user_id
            if not account or account != rec.account_id or account.share or rec.company_id not in account.company_ids:
                raise ValidationError(_("Select an internal faculty account belonging to this college."))
            if not rec.date_from or not rec.date_to or rec.date_to < rec.date_from or not rec.media_type_ids or not (rec.justification or "").strip():
                raise ValidationError(_("Provide collections, a reason and a valid appointment period."))

    def _check_admin(self):
        if not (self.env.user.has_group("ideastone_erp.group_college_admin") or
                self.env.user.has_group("ideastone_erp.group_manager")):
            raise AccessError(_("College administrator access is required."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_admin()
        protected = {"state", "account_id", "requested_by", "approved_by", "approved_on", "decision_reason"}
        if any(protected.intersection(vals) for vals in vals_list):
            raise AccessError(_("Use the responsibility approval workflow."))
        return super().create([dict(vals, account_id=self.env["op.faculty"].browse(vals.get("faculty_id")).user_id.id) for vals in vals_list])

    def write(self, vals):
        self._check_admin()
        if {"state", "account_id", "requested_by", "approved_by", "approved_on", "decision_reason"}.intersection(vals):
            raise AccessError(_("Use the responsibility approval workflow."))
        if any(rec.state != "draft" for rec in self):
            raise ValidationError(_("Submitted appointments are immutable. Revoke and create a new appointment."))
        if "faculty_id" in vals:
            vals = dict(vals, account_id=self.env["op.faculty"].browse(vals["faculty_id"]).user_id.id)
        return super().write(vals)

    def action_request(self):
        self._check_admin()
        self._lock()
        if any(rec.state != "draft" for rec in self):
            raise ValidationError(_("Only drafts can be submitted."))
        return super().write({"state": "requested", "requested_by": self.env.uid})

    def action_approve(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_role_approver"):
            raise AccessError(_("Responsibility approver access is required."))
        for rec in self:
            if rec.state != "requested" or rec.requested_by == self.env.user or rec.faculty_id.user_id == self.env.user:
                raise AccessError(_("A separate authorized person must approve this request."))
            rec._check_scope()
        return super().write({"state": "approved", "approved_by": self.env.uid, "approved_on": fields.Datetime.now()})

    def action_revoke(self):
        self._check_admin()
        self._lock()
        if any(rec.state != "approved" for rec in self):
            raise ValidationError(_("Only approved appointments can be revoked."))
        return super().write({"state": "revoked", "decision_reason": _("Revoked by college administrator")})

    def action_reject(self):
        self._lock()
        if not self.env.user.has_group("ideastone_erp.group_role_approver") or any(rec.state != "requested" for rec in self):
            raise AccessError(_("Only an approver can reject a pending request."))
        return super().write({"state": "rejected", "decision_reason": _("Rejected by responsibility approver")})

    def unlink(self):
        self._check_admin()
        if any(rec.state != "draft" for rec in self):
            raise ValidationError(_("Retain submitted appointments for audit."))
        return super().unlink()

    @api.model
    def _library_scope(self):
        if not self.env.user.active or not self.env.user.has_group("base.group_user"):
            raise AccessError(_("An active internal account is required."))
        today = self._college_today()
        # Evaluate on every call: expiry and revocation do not wait for a cron or a new login.
        grants = self.sudo().search([
            ("account_id", "=", self.env.uid), ("faculty_id.user_id", "=", self.env.uid),
            ("faculty_id.active", "=", True), ("active", "=", True),
            ("company_id", "=", self.env.company.id), ("state", "=", "approved"),
            ("date_from", "<=", today), ("date_to", ">=", today),
        ])
        if not grants:
            raise AccessError(_("An active approved Library In-charge appointment is required."))
        return grants.media_type_ids.ids
