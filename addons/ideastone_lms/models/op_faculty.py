from odoo import api, models


class OpFaculty(models.Model):
    _name = "op.faculty"
    _inherit = ["op.faculty", "ideastone.lms.account.mixin"]

    def _lms_login(self):
        self.ensure_one()
        return (self.email or f"faculty{self.id}").lower().replace(" ", "")

    def _lms_names(self):
        self.ensure_one()
        return self.first_name, " ".join(p for p in (self.middle_name, self.last_name) if p), self.email

    @api.model
    def _cron_provision_lms(self):
        if self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_auto_provision") != "True":
            return
        self.search([("active", "=", True), ("lms_identity_key", "=", False)], limit=200).action_provision_lms()
