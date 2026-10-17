{
    "name": "Ideastone Campus Operations",
    "summary": "Teaching, campus services, staff administration and institutional engagement",
    "version": "17.0.1.0.3",
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
        "security/workspace.xml", "views/workspace.xml", "views/faculty_workspace.xml",
        "security/faculty_tools.xml", "views/faculty_tools.xml", "views/student_leave.xml", "views/faculty_reports.xml",
        "security/mvp.xml", "data/mvp.xml", "views/mvp.xml", "views/mvp_search.xml", "views/mvp_reports.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_erp/static/src/js/dashboard.js",
            "ideastone_erp/static/src/xml/dashboard.xml",
            "ideastone_erp/static/src/xml/owner.xml",
            "ideastone_erp/static/src/scss/dashboard.scss",
            "ideastone_erp/static/src/scss/faculty_workspace.scss",
            "ideastone_erp/static/src/scss/owner.scss",
        ],
    },
    "application": True,
    "installable": True,
}
