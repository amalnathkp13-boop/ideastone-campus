from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class CollegeNotice(models.Model):
    _inherit = "campus.circular"

    campus_managed = fields.Boolean(default=False)
    campus_category = fields.Char(string="Category")
    campus_course_id = fields.Many2one("op.course", string="Target programme")
    campus_batch_id = fields.Many2one("op.batch", string="Target section")
    campus_group_id = fields.Many2one("res.groups", string="Target staff group")
    campus_status = fields.Selection([("draft", "Draft"), ("scheduled", "Scheduled"), ("published", "Published"), ("archived", "Archived")], default="draft", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("campus_status", "draft") != "draft" for v in vals_list):
            raise AccessError(_("Create notices as drafts."))
        return super().create(vals_list)

    def write(self, vals):
        if "campus_status" in vals:
            raise AccessError(_("Use notice publication and archive actions."))
        return super().write(vals)

    def action_campus_publish(self):
        if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            raise AccessError(_("College administrator permission is required to publish notices."))
        self._lock()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.campus_status != "draft" or rec.date_to and rec.date_to < today:
                raise ValidationError(_("Publish an unexpired draft notice."))
            if rec.campus_batch_id and rec.campus_batch_id.course_id != rec.campus_course_id:
                raise ValidationError(_("Target section must belong to the selected programme."))
            future = rec.date_from > today
            rec._set_system_values({"campus_status": "scheduled" if future else "published", "state": "submitted" if future else "approved",
                                    "approved_by": self.env.uid, "approved_on": fields.Datetime.now()})
            self.env["campus.mvp.audit"]._log(rec, "Notice scheduled" if future else "Notice published")
        return True

    def action_campus_archive(self):
        if not self.env.su and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            raise AccessError(_("College administrator permission is required."))
        self._lock()
        self._set_system_values({"campus_status": "archived", "state": "done"})
        for rec in self:
            self.env["campus.mvp.audit"]._log(rec, "Notice archived")
        return True

    @api.model
    def _cron_publish_notices(self):
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        for rec in self.search([("campus_managed", "=", True), ("campus_status", "=", "scheduled"), ("date_from", "<=", today)]):
            if rec.communication_publish_at and rec.communication_publish_at > now:
                continue
            expired = rec.date_to and rec.date_to < today
            rec._set_system_values({"campus_status": "archived" if expired else "published", "state": "done" if expired else "approved"})
        expired = self.search([("campus_managed", "=", True), ("campus_status", "=", "published"), ("date_to", "<", today)])
        expired._set_system_values({"campus_status": "archived", "state": "done"})

    @api.model
    def _mvp_notices(self):
        if not self.check_access_rights("read", raise_exception=False):
            return []
        today = fields.Date.context_today(self)
        notices = self.search([("company_id", "=", self.env.company.id), ("campus_status", "=", "published"),
                               ("date_from", "<=", today), "|", ("date_to", "=", False), ("date_to", ">=", today)], limit=20)
        return [{"id": n.id, "name": n.name, "date": str(n.date_from), "audience": n.audience} for n in notices]


class CollegeReadonlyGuard(models.AbstractModel):
    _inherit = "base"

    def _mvp_readonly_guard(self):
        if self.env.su or not (self._name.startswith("op.") or self._name.startswith("campus.")):
            return
        if self._name in {"campus.mvp.report"}:
            return
        user = self.env.user
        readonly = user.has_group("ideastone_erp.group_mvp_readonly") or user.has_group("ideastone_erp.group_mvp_hod")
        operator = any(user.has_group("ideastone_erp.group_mvp_" + role) for role in ["registrar", "accountant", "exams", "admissions"])
        if readonly and not operator:
            raise AccessError(_("This account has read-only college reporting access."))

    @api.model_create_multi
    def create(self, vals_list):
        self._mvp_readonly_guard()
        return super().create(vals_list)

    def write(self, vals):
        self._mvp_readonly_guard()
        result = super().write(vals)
        academic = {"op.academic.year", "op.academic.term", "op.department", "op.course", "op.batch", "op.subject", "op.fees.terms", "op.fees.terms.line"}
        sensitive = set(vals).intersection({"groups_id", "company_ids", "active"}) if self._name == "res.users" else set(vals).intersection({"campus_attendance_threshold", "campus_excused_policy", "currency_id"}) if self._name == "res.company" else set(vals) if self._name in academic else set()
        if sensitive and self.env.registry.ready and "campus.mvp.audit" in self.env:
            for rec in self:
                self.env["campus.mvp.audit"]._log(rec, "College configuration updated", details={key: str(vals[key])[:500] for key in sorted(sensitive)})
        return result

    def unlink(self):
        self._mvp_readonly_guard()
        return super().unlink()
