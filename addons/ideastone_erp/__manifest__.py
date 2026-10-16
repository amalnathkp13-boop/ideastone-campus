{
    "name": "Ideastone Campus Operations",
    "summary": "Teaching, campus services, staff administration and institutional engagement",
    "version": "17.0.1.0.1",
    "category": "Education",
    "author": "Ideastone Technologies Pvt Ltd",
    "license": "OPL-1",
    "depends": [
        "ideastone_lms", "hr_attendance", "hr_holidays", "purchase_stock",
        "maintenance", "crm", "survey", "website_event", "website_forum",
        "payment", "portal", "website",
    ],
    "data": [
        "security/groups.xml", "security/directory.xml", "security/ir.model.access.csv", "security/rules.xml",
        "views/operations.xml", "views/faculty.xml", "views/menus.xml", "views/portal.xml", "views/reports.xml",
        "security/workspace.xml", "views/workspace.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_erp/static/src/js/dashboard.js",
            "ideastone_erp/static/src/xml/dashboard.xml",
            "ideastone_erp/static/src/scss/dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
