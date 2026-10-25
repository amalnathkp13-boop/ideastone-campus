# Ideastone Campus — customisation layer on top of OpenEduCat.
#
# This module is Ideastone Technologies' own code. It only *depends on* and
# *extends* OpenEduCat (LGPL-3) through Odoo's inheritance mechanism; no
# OpenEduCat file is modified. All client-specific changes go here.
{
    "name": "Ideastone Campus",
    "summary": "College ERP for Indian engineering & arts colleges, built on OpenEduCat",
    "description": """
Ideastone Campus bundles the full OpenEduCat suite (admissions, students, fees,
timetable, attendance, exams, library, parents portal) and layers on:

* Ideastone branding (login page, window title, company defaults)
* Indian engineering-college master data (departments, B.E./B.Tech programmes,
  academic year with two semesters) loaded as reference data
* Indian localisation defaults (INR, Asia/Kolkata, en_IN)
* Single sign-on: Keycloak OpenID Connect provider pre-configured ("Log in with Ideastone SSO")
* Menu "Ideastone Campus" that groups the daily-use screens for college office staff
""",
    "version": "17.0.1.0.3",
    "category": "Education",
    "author": "Ideastone Technologies Pvt Ltd",
    "website": "https://github.com/ideastone",
    "license": "OPL-1",
    "depends": [
        "openeducat_erp",
        "openeducat_fees",
        "openeducat_timetable",
        "openeducat_classroom",
        "openeducat_activity",
        "openeducat_facility",
        "web",
        "auth_oauth",
        "auth_signup",
    ],
    "data": [
        "data/branding.xml",
        "data/master_data.xml",
        "data/sso.xml",
        "views/webclient_templates.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_campus/static/src/scss/brand.scss",
        ],
        "web.assets_frontend": [
            "ideastone_campus/static/src/scss/brand.scss",
        ],
    },
    "images": ["static/description/banner.png"],
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
    "auto_install": False,
}
