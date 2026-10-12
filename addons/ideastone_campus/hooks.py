"""Install-time hook: Indian localisation defaults for the main company."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
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
