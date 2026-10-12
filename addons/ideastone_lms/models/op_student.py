from odoo import api, models


class OpStudent(models.Model):
    _name = "op.student"
    _inherit = ["op.student", "ideastone.lms.account.mixin"]

    def _lms_login(self):
        self.ensure_one()
        return (self.register_no or self.gr_no or self.email or f"student{self.id}").lower().replace(" ", "")

    def _lms_names(self):
        self.ensure_one()
        return self.first_name, " ".join(p for p in (self.middle_name, self.last_name) if p), self.email

    def _lms_course_keys(self):
        self.ensure_one()
        return [d.course_id.lms_course_key for d in self.course_detail_ids if d.course_id.lms_course_key]

    @api.model
    def _cron_provision_lms(self):
        if self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_auto_provision") != "True":
            return
        self.search([("active", "=", True), ("lms_identity_key", "=", False)], limit=200).action_provision_lms()
