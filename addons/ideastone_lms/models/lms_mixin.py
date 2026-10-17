import json
import logging
import os

from odoo.exceptions import AccessError

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
    lms_enrolled_keys = fields.Char("Successfully synchronized course keys", copy=False, readonly=True)

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
        self.check_access_rights("write")
        self.check_access_rule("write")
        registrar = self.env.ref("ideastone_erp.group_mvp_registrar", raise_if_not_found=False)
        if not self.env.su and not (self.env.user.has_group("base.group_system") or self.env.user.has_group("openeducat_core.group_op_back_office_admin") or registrar and registrar in self.env.user.groups_id):
            raise AccessError(_("College administrator permission is required to synchronize LMS accounts."))
        if "company_id" in self._fields and self.filtered(lambda r: r.company_id and r.company_id not in self.env.companies):
            raise AccessError(_("Synchronize accounts only for your permitted colleges."))
        client = self._lms_client()
        password = self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_default_password") or None
        for rec in self:
            try:
                first, last, email = rec._lms_names()
                user, created = client.ensure_user(rec._lms_login(), first, last, email, password, external_id=f"{rec._name}:{rec.id}")
                key = user.get("key")
                if not key:
                    raise ValueError("The LMS did not return an account identity key.")
                enrolled = 0
                try:
                    enrolled_keys = list(json.loads(rec.lms_enrolled_keys or "[]"))
                except (ValueError, TypeError):
                    enrolled_keys = []
                failures = []
                for ck in rec._lms_course_keys():
                    try:
                        client.add_participant(ck, key)
                        enrolled += 1
                        enrolled_keys.append(str(ck))
                    except Exception as e:  # noqa: BLE001 — keep going, report on record
                        _logger.warning("LMS enrolment failed for %s in course %s: %s", rec.display_name, ck, e)
                        failures.append(str(ck))
                rec.write({"lms_login": user.get("login"), "lms_identity_key": str(key), "lms_synced_on": False if failures else fields.Datetime.now(),
                           "lms_enrolled_keys": json.dumps(sorted(set(enrolled_keys))),
                           "lms_sync_error": (_("Course enrolment failed for: %s. Retry synchronization.", ", ".join(failures)))[:250] if failures else False})
                if hasattr(rec, "message_post"):
                    rec.message_post(body=_("LMS account %s (%s). Enrolled in %s course(s).",
                                            user.get("login"), _("created") if created else _("already existed"), enrolled))
            except Exception as e:  # noqa: BLE001
                _logger.exception("LMS provisioning failed for %s", rec.display_name)
                rec.write({"lms_synced_on": False, "lms_sync_error": str(e)[:250]})
        return True

    def action_open_lms(self):
        url = self.env["ir.config_parameter"].sudo().get_param("ideastone.lms_url", "/lms/")
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
