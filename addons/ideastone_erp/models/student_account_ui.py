from odoo import api, fields, models


class StudentAccountPreferences(models.Model):
    _inherit = "op.student"

    campus_academic_reminders = fields.Boolean(default=True, string="Show academic reminders")
    campus_compact_cards = fields.Boolean(default=False, string="Compact portal information cards")


class StudentAccountUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student = self._identity()
        data["account_ui"] = {
            "last_sign_in": self._dates(self.env.user.sudo().login_date) or "Not recorded",
            "academic_reminders": student.campus_academic_reminders,
            "compact_cards": student.campus_compact_cards,
        }
        return data
