from odoo.exceptions import AccessError

from odoo import models

RADAR_ACTION = "ideastone_ai.action_success_radar"
ASSISTANT_ACTION = "ideastone_ai.action_assistant"


class CampusDashboardAI(models.AbstractModel):
    _inherit = "campus.dashboard"

    # Owner workspace: one "AI" module with both screens.
    def _owner_modules(self):
        modules = super()._owner_modules()
        modules.insert(1, ("ai", "AI insights", "magic", [("Student Success Radar", RADAR_ACTION), ("Campus Assistant", ASSISTANT_ACTION)]))
        return modules

    def _client_action_models(self):
        models_map = super()._client_action_models()
        models_map[RADAR_ACTION] = "op.student"
        models_map[ASSISTANT_ACTION] = "campus.ai.log"
        return models_map

    # Staff workspace (HODs and mentors): the radar appears as its own module.
    def _navigation_extensions(self):
        extensions = super()._navigation_extensions()
        try:
            self.env["campus.success.radar"]._scope()
        except AccessError:
            return extensions
        return extensions + [
            {"label": "Student Success Radar", "model": "op.student", "action": RADAR_ACTION, "group": "Student success"},
        ]

    def _faculty_module_definitions(self):
        definitions = super()._faculty_module_definitions()
        index = next((i for i, item in enumerate(definitions) if item[0] == "od"), len(definitions))
        definitions.insert(index, ("success", "Student success", "heartbeat", ["Student success"]))
        return definitions
