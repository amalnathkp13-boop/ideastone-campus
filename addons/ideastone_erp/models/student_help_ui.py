from odoo import api, fields, models


class StudentFeedbackCategory(models.Model):
    _inherit = "campus.feedback"

    student_category = fields.Selection([
        ("teaching", "Teaching & academics"), ("facilities", "Campus facilities"),
        ("services", "Student services"), ("technical", "ERP / technical issue"),
        ("events", "Events & activities"), ("other", "Other"),
    ], default="other", required=True, string="Student feedback category")


class StudentHelpUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student = self._identity()
        period = data["placement"]["year"]
        if period == "Not assigned":
            period = str(fields.Date.context_today(self).year)
        categories = dict(self.env["campus.feedback"]._fields["student_category"].selection)
        feedback = self.with_context(active_test=False)._records("campus.feedback", [("company_id", "=", student.company_id.id),
            ("student_id", "=", student.id), ("respondent_id", "=", self.env.uid), ("kind", "=", "student"),
            ("period", "=", period), ("faculty_id", "=", False)], limit=10, order="id desc")[:1]
        data["help_ui"] = {"period": period, "categories": list(categories.items()),
            "feedback": {"category": categories.get(feedback.student_category, "Other"), "score": feedback.score,
                         "comments": feedback.comments or "", "date": self._dates(feedback.create_date)} if feedback else None}
        return data
