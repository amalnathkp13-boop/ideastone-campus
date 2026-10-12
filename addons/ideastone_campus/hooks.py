"""Install-time hook: Indian localisation defaults + environment-specific SSO URLs."""

import logging
import os

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _localise(env)
    _configure_sso(env)


def _localise(env):
    company = env.ref("base.main_company", raise_if_not_found=False)
    if not company:
        return
    inr = env.ref("base.INR", raise_if_not_found=False)
    india = env.ref("base.in", raise_if_not_found=False)
    vals = {}
    if inr and company.currency_id != inr:
        # Only safe on a fresh database; skip if accounting entries exist.
        if not env["account.move"].search_count([("company_id", "=", company.id)]):
            inr.active = True
            vals["currency_id"] = inr.id
    if india:
        vals["country_id"] = india.id
    if vals:
        company.write(vals)
    env["res.users"].search([("tz", "=", False)]).write({"tz": "Asia/Kolkata"})
    _logger.info("Ideastone Campus: localisation defaults applied (%s)", list(vals))


def _configure_sso(env):
    """Point the Keycloak provider at this deployment's public URL (browser side)
    and the internal Keycloak URL (server-side token validation)."""
    public = os.environ.get("CAMPUS_PUBLIC_URL", "http://localhost").rstrip("/")
    internal = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/sso").rstrip("/")
    provider = env.ref("ideastone_campus.provider_keycloak", raise_if_not_found=False)
    if provider:
        provider.write({
            "auth_endpoint": f"{public}/sso/realms/campus/protocol/openid-connect/auth",
            "validation_endpoint": f"{internal}/realms/campus/protocol/openid-connect/userinfo",
        })
    # SSO users not yet in Odoo get an account on first login (auth_signup "free" mode)
    env["ir.config_parameter"].sudo().set_param("auth_signup.invitation_scope", "b2c")
    env["ir.config_parameter"].sudo().set_param("web.base.url", public)
    env["ir.config_parameter"].sudo().set_param("web.base.url.freeze", "True")
    _logger.info("Ideastone Campus: SSO provider configured for %s (validation via %s)", public, internal)
