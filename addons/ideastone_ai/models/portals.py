from odoo import api, models


class StudentPortalSuccess(models.AbstractModel):
    """Adds the Student Success guidance to the student portal.

    campus.parent.portal is built on campus.student.portal, so the parent portal
    receives the same guidance for the selected child through this one override.
    """
    _inherit = "campus.student.portal"

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        # Only the signed-in student's (or parent's child's) own guidance; scoring runs under the workflow.
        data["success"] = self.env["campus.success.radar"].sudo().student_nudge(self._identity())
        return data
