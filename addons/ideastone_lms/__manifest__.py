# Ideastone Campus — LMS integration (OpenOlat embedded in the ERP, user provisioning).
{
    "name": "Ideastone Campus – LMS (OpenOlat)",
    "summary": "OpenOlat learning platform embedded inside Ideastone Campus with automatic user provisioning",
    "description": """
Makes the ERP and the LMS one platform:

* **Learning** app in the top bar opens OpenOlat *inside* the Ideastone Campus UI (same login via SSO).
* **Campus home** launcher with one tile per module (Admissions, Students, Fees, Attendance, Exams, Library, Learning).
* **Provisioning**: students and faculty get OpenOlat accounts automatically (button on the record + nightly cron)
  through OpenOlat's REST API; programmes can be mapped to OpenOlat courses so students are enrolled on sync.
""",
    "version": "17.0.1.0.0",
    "category": "Education",
    "author": "Ideastone Technologies Pvt Ltd",
    "license": "OPL-1",
    "depends": ["ideastone_campus", "openeducat_core"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/config.xml",
        "data/cron.xml",
        "views/actions.xml",
        "views/res_config_settings.xml",
        "views/op_student.xml",
        "views/op_faculty.xml",
        "views/op_course.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_lms/static/src/js/*.js",
            "ideastone_lms/static/src/xml/*.xml",
            "ideastone_lms/static/src/scss/*.scss",
        ],
    },
    "application": True,
    "installable": True,
}
