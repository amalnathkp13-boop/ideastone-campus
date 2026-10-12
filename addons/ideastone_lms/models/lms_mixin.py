import logging
import os

from odoo import _, fields, models

from .lms_client import LmsClient

_logger = logging.getLogger(__name__)


class LmsAccountMixin(models.AbstractModel):
    """Shared LMS-account behaviour for students and faculty."""

    _name = "ideastone.lms.account.mixin"
    _description = "LMS account link"

    lms_login = fields.Char("LMS login", copy=False, readonly=True)
    lms_identity_key = fields.Char("LMS identity key", copy=False, readonly=True)
    lms_synced_on = fields.Datetime("LMS synced on", copy=False, readonly=True)
    lms_sync_error = fields.Char("LMS sync error", copy=False, readonly=True)

    # -- to be provided by the concrete model --------------------------
    def _lms_login(self):
        raise NotImplementedError

    def _lms_names(self):
        """return (first_name, last_name, email)"""
        raise NotImplementedError

    def _lms_course_keys(self):
        return []

    # -- client --------------------------------------------------------
    def _lms_client(self):
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param("ideastone.lms_internal_url") or os.environ.get("LMS_INTERNAL_URL", "http://openolat:8088/lms")
        return LmsClient(base, icp.get_param("ideastone.lms_api_user"), icp.get_param("ideastone.lms_api_password"))

    def action_provision_lms(self):
        client = self._lms_client()
        password = self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_default_password") or None
        for rec in self:
            try:
                first, last, email = rec._lms_names()
                user, created = client.ensure_user(rec._lms_login(), first, last, email, password, external_id=f"{rec._name}:{rec.id}")
                key = user.get("key")
                enrolled = 0
                for ck in rec._lms_course_keys():
                    try:
                        client.add_participant(ck, key)
                        enrolled += 1
                    except Exception as e:  # noqa: BLE001 — keep going, report on record
                        _logger.warning("LMS enrolment failed for %s in course %s: %s", rec.display_name, ck, e)
                rec.write({"lms_login": user.get("login"), "lms_identity_key": str(key), "lms_synced_on": fields.Datetime.now(), "lms_sync_error": False})
                if hasattr(rec, "message_post"):
                    rec.message_post(body=_("LMS account %s (%s). Enrolled in %s course(s).",
                                            user.get("login"), _("created") if created else _("already existed"), enrolled))
            except Exception as e:  # noqa: BLE001
                _logger.exception("LMS provisioning failed for %s", rec.display_name)
                rec.write({"lms_sync_error": str(e)[:250]})
        return True

    def action_open_lms(self):
        url = self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_url", "/lms/")
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
