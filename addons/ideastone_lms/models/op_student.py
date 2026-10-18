import json

from odoo import api, fields, models


class OpStudent(models.Model):
    _name = "op.student"
    _inherit = ["op.student", "ideastone.lms.account.mixin"]

    lms_enrolment_pending = fields.Boolean(string="LMS enrolment update pending", compute="_compute_lms_enrolment_pending", store=True)

    @api.depends("lms_identity_key", "lms_enrolled_keys", "course_detail_ids.state", "course_detail_ids.course_id.lms_course_key")
    def _compute_lms_enrolment_pending(self):
        for rec in self:
            try:
                enrolled = set(json.loads(rec.lms_enrolled_keys or "[]"))
            except (ValueError, TypeError):
                enrolled = set()
            rec.lms_enrolment_pending = not rec.lms_identity_key or not set(rec._lms_course_keys()).issubset(enrolled)

    def _lms_login(self):
        self.ensure_one()
        return (self.register_no or self.gr_no or self.email or f"student{self.id}").lower().replace(" ", "")

    def _lms_names(self):
        self.ensure_one()
        return self.first_name, " ".join(p for p in (self.middle_name, self.last_name) if p), self.email

    def _lms_course_keys(self):
        self.ensure_one()
        return sorted({d.course_id.lms_course_key for d in self.course_detail_ids if d.state == "running" and d.course_id.lms_course_key})

    @api.model
    def _cron_provision_lms(self):
        if self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_auto_provision") != "True":
            return
        self.search([("active", "=", True), "|", ("lms_enrolment_pending", "=", True), ("lms_sync_error", "!=", False)], limit=200).action_provision_lms()
