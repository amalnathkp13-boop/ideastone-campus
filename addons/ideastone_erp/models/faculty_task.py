from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyTask(models.Model):
    _name = "campus.faculty.task"
    _description = "Personal faculty task and e-diary"
    _inherit = "campus.record"
    _order = "deadline, priority desc, id desc"

    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, readonly=True, index=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    deadline = fields.Date(required=True, default=fields.Date.context_today, index=True)
    kind = fields.Selection([
        ("teaching", "Teaching"), ("exam", "Examination"), ("mentoring", "Mentoring"),
        ("club", "Club activity"), ("sdp", "Skill development"), ("other", "Other"),
    ], required=True, default="teaching")
    state = fields.Selection([("planned", "Planned"), ("progress", "In progress"), ("done", "Completed"),
                              ("cancelled", "Cancelled")], required=True, default="planned", tracking=True)
    priority = fields.Selection([("0", "Normal"), ("1", "Important")], default="0")
    notes = fields.Html(sanitize=True)
    document = fields.Binary(attachment=True)
    filename = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("user_id", self.env.uid) != self.env.uid:
                raise AccessError(_("You can create tasks only for your own faculty account."))
        return super().create(vals_list)

    def write(self, vals):
        if {"user_id", "company_id"} & vals.keys():
            raise AccessError(_("A personal task cannot be transferred to another account or college."))
        return super().write(vals)

    @api.constrains("date", "deadline")
    def _check_dates(self):
        for task in self:
            if task.deadline < task.date:
                raise ValidationError(_("The due date cannot be before the task date."))
