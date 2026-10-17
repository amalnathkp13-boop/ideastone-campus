from odoo.exceptions import AccessError

from odoo import _, api, fields, models


class MVPAudit(models.Model):
    _name = "campus.mvp.audit"
    _description = "College workflow audit history"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    actor_id = fields.Many2one("res.users", required=True)
    model_name = fields.Char(required=True, index=True)
    record_id = fields.Integer(required=True, index=True)
    reason = fields.Text()
    details = fields.Json()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Audit entries are recorded by verified workflow actions."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Audit history cannot be changed."))

    def unlink(self):
        raise AccessError(_("Audit history must be retained."))

    @api.model
    def _log(self, record, action, reason=None, details=None):
        record.ensure_one()
        company = record if record._name == "res.company" else record.company_id if "company_id" in record._fields else self.env.company
        return self.sudo().create({
            "name": action, "company_id": (company or self.env.company).id,
            "actor_id": self.env.uid, "model_name": record._name, "record_id": record.id,
            "reason": reason, "details": details or {},
        })


class MVPMixin(models.AbstractModel):
    _name = "campus.mvp.mixin"
    _description = "College workflow guard helpers"

    def _mvp_lock(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self:
            self.env.cr.execute(f'SELECT id FROM "{self._table}" WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset()

    def _mvp_require(self, *groups):
        if not self.env.su and not any(self.env.user.has_group(group) for group in groups):
            raise AccessError(_("Your account is not authorized for this college action."))

    def _mvp_log(self, action, reason=None, details=None):
        for rec in self:
            self.env["campus.mvp.audit"]._log(rec, action, reason, details)

    def _mvp_company(self, *related):
        for rec in self:
            if rec.company_id and rec.company_id not in self.env.companies:
                raise AccessError(_("This record belongs to another college."))
            for name in related:
                targets = rec[name]
                if "company_id" in targets._fields and targets.filtered(lambda r, company=rec.company_id: r.company_id and r.company_id != company):
                    raise AccessError(_("Related records must belong to the same college."))
