from urllib.parse import urlsplit

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, models


class LearningWorkspace(models.AbstractModel):
    _name = "ideastone.lms.workspace"
    _description = "Public learning URL for authorized staff"

    @api.model
    def configuration(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Use an authorized staff account to open the learning workspace."))
        url = self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_url", "/lms/") or "/lms/"
        parts = urlsplit(url)
        if not (url.startswith("/") and not url.startswith("//") or parts.scheme in {"http", "https"} and parts.netloc and not parts.username and not parts.password):
            raise ValidationError(_("Configure a same-site learning path or an HTTP(S) LMS address in college settings."))
        return {"url": url}
