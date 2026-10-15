from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class CampusRecord(models.AbstractModel):
    _name = "campus.record"
    _description = "Company scoped campus record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    active = fields.Boolean(default=True)

    def _lock(self):
        """Serialize decisions such as capacity allocation against concurrent requests."""
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self:
            self.env.cr.execute(f'SELECT id FROM "{self._table}" WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()


class CampusApproval(models.AbstractModel):
    _name = "campus.approval"
    _description = "Audited campus approval"
    _inherit = "campus.record"

    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
        ("done", "Completed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, copy=False, tracking=True)
    approved_by = fields.Many2one("res.users", readonly=True, copy=False)
    approved_on = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("state", "draft") != "draft" or v.get("approved_by") or v.get("approved_on") for v in vals_list):
            raise AccessError(_("New records must start as drafts."))
        return super().create(vals_list)

    def write(self, vals):
        if {"approved_by", "approved_on"} & vals.keys():
            raise AccessError(_("Approval evidence is maintained by the approval workflow."))
        if "state" in vals:
            if set(vals) != {"state"}:
                raise ValidationError(_("Save business changes before changing workflow status."))
            self._lock()
            transitions = {
                "draft": {"submitted", "cancelled"}, "submitted": {"approved", "cancelled"},
                "approved": {"done", "cancelled"}, "done": set(), "cancelled": {"draft"},
            }
            for rec in self:
                target = vals["state"]
                if target == rec.state:
                    continue
                if target not in transitions[rec.state]:
                    raise ValidationError(_("This workflow transition is not allowed."))
                if target in {"approved", "done"} or rec.state in {"approved", "cancelled"}:
                    if not self.env.user.has_group("ideastone_erp.group_manager"):
                        raise AccessError(_("Campus manager approval is required."))
                rec._validate_transition(target)
        elif any(rec.state in {"approved", "done"} for rec in self):
            # Chatter/activity metadata is not business data.
            business = set(vals) - {"message_follower_ids", "message_ids", "activity_ids", "active"}
            if business:
                raise ValidationError(_("Approved records are locked. Cancel and create a revised record."))
        result = super().write(vals)
        if vals.get("state") == "approved":
            super().write({"approved_by": self.env.uid, "approved_on": fields.Datetime.now()})
        return result

    def _validate_transition(self, target):
        return True

    def _set_system_values(self, vals):
        """Internal link updates after a permission-checked business action."""
        return super().write(vals)

    def action_submit(self):
        return self.write({"state": "submitted"})

    def action_approve(self):
        return self.write({"state": "approved"})

    def action_done(self):
        return self.write({"state": "done"})

    def action_cancel(self):
        return self.write({"state": "cancelled"})

    def action_reset(self):
        return self.write({"state": "draft"})

    def unlink(self):
        if any(rec.state not in {"draft", "cancelled"} for rec in self):
            raise ValidationError(_("Archive completed records to retain their audit history."))
        return super().unlink()
