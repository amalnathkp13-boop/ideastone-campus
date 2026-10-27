{
    "name": "Ideastone Campus AI Pack",
    "summary": "Student Success Radar (early-warning scores) and the Campus Assistant (generative AI for owners)",
    "description": """
Ideastone Campus AI Pack
========================
* **Student Success Radar** - an explainable early-warning score for every student,
  built from the college's own attendance, results, fee and leave records. Works with
  no external service. Owner, HOD and mentor views; nudges in the student and parent portals.
* **Campus Assistant** - plain-English questions over live college numbers, notice drafting
  and feedback summaries. Uses any OpenAI-compatible provider (OpenAI, Groq, a self-hosted
  Ollama server...). Off until the college configures it; every call is logged.
""",
    "version": "17.0.1.0.1",
    "category": "Education",
    "author": "Ideastone Technologies Pvt Ltd",
    "license": "OPL-1",
    "depends": ["ideastone_erp"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/actions.xml",
        "views/company.xml",
        "views/ai_log.xml",
        "views/student_portal.xml",
        "views/parent_portal.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ideastone_ai/static/src/js/success_radar.js",
            "ideastone_ai/static/src/xml/success_radar.xml",
            "ideastone_ai/static/src/js/assistant.js",
            "ideastone_ai/static/src/xml/assistant.xml",
            "ideastone_ai/static/src/scss/ai_pack.scss",
        ],
        "web.assets_frontend": [
            "ideastone_ai/static/src/scss/portal_nudge.scss",
        ],
    },
    "application": False,
    "installable": True,
}
