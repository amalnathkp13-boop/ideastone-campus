from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    lms_public_url = fields.Char("LMS URL (browser)", config_parameter="ideastone.lms_url",
                                 help="Where the Learning app opens, relative or absolute. Default /lms/ (same domain).")
    lms_internal_url = fields.Char("LMS URL (server-to-server)", config_parameter="ideastone.lms_internal_url",
                                   help="URL Odoo uses to call OpenOlat's REST API, e.g. http://openolat:8088/lms")
    lms_api_user = fields.Char("LMS API user", config_parameter="ideastone.lms_api_user",
                               help="An OpenOlat user with the User manager role (or an API key login)")
    lms_api_password = fields.Char("LMS API password / key", config_parameter="ideastone.lms_api_password")
    lms_default_password = fields.Char("Initial LMS password for new accounts", config_parameter="ideastone.lms_default_password",
                                       help="Only used when SSO is not active for the LMS. Leave empty to let OpenOlat generate one.")
    lms_auto_provision = fields.Boolean("Create LMS accounts automatically (nightly)", config_parameter="ideastone.lms_auto_provision")
