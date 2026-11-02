{
    "name": "Ideastone Campus - Principal",
    "summary": "Principal oversight, approvals, notices and campus records",
    "version": "17.0.1.1.1",
    "category": "Education",
    "author": "Ideastone Technologies Pvt Ltd",
    "license": "OPL-1",
    "depends": ["ideastone_erp", "mail"],
    "data": [
        "security/principal_security.xml",
        "security/ir.model.access.csv",
        "views/principal_request_views.xml",
        "views/principal_notice_views.xml",
        "views/principal_workspace.xml",
        "views/staff_workspace.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_principal/static/src/js/workspace.js",
            "ideastone_principal/static/src/xml/workspace.xml",
            "ideastone_principal/static/src/scss/workspace.scss",
            "ideastone_principal/static/src/js/staff_workspace.js",
            "ideastone_principal/static/src/xml/staff_workspace.xml",
            "ideastone_principal/static/src/scss/staff_workspace.scss",
        ],
    },
    "application": False,
    "installable": True,
}
