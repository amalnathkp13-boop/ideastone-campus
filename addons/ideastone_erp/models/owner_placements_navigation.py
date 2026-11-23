from odoo import models

PLACEMENT_SCREENS = (
    ("overview", "Overview"), ("departments", "Departments"), ("students", "Students"),
    ("drives", "Placement drives"), ("offers", "Offers & outcomes"),
    ("history", "Past records"), ("insights", "AI insights"),
)


class OwnerPlacementsNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _owner_modules(self):
        modules = super()._owner_modules()
        if self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            entries = [(label, "action_owner_placements_" + screen) for screen, label in PLACEMENT_SCREENS]
            index = next((i + 1 for i, item in enumerate(modules) if item[0] == "exams"), len(modules))
            modules.insert(index, ("placements", "Campus Placements", "briefcase", entries))
        return modules

    def _client_action_models(self):
        return dict(super()._client_action_models(), **{
            "action_owner_placements_" + screen: "campus.placement.profile" for screen, _label in PLACEMENT_SCREENS
        })
