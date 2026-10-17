from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyActivity(models.Model):
    _name = "campus.faculty.activity"
    _description = "Faculty club, skill development and placement training"
    _inherit = "campus.faculty.task"

    kind = fields.Selection([("club", "Club function"), ("sdp", "Skill development programme"),
                             ("vac", "Value added / placement training")], required=True, default="club")
    batch_id = fields.Many2one("op.batch", required=True, ondelete="restrict")
    level = fields.Char()
    venue = fields.Char()
    attendance_ids = fields.One2many("campus.faculty.activity.attendance", "activity_id", string="Participants")

    @api.constrains("batch_id", "user_id", "company_id")
    def _check_batch(self):
        for activity in self:
            if not self.env["op.session"].search_count([
                ("faculty_id.user_id", "=", activity.user_id.id), ("batch_id", "=", activity.batch_id.id),
                ("company_id", "=", activity.company_id.id), ("state", "!=", "cancel"),
            ]):
                raise AccessError(_("Choose a batch allocated to you in the timetable."))


class FacultyActivityAttendance(models.Model):
    _name = "campus.faculty.activity.attendance"
    _description = "Faculty activity participant attendance"

    activity_id = fields.Many2one("campus.faculty.activity", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one("op.student", required=True, ondelete="restrict")
    forenoon = fields.Boolean("FN present")
    afternoon = fields.Boolean("AN present")
    remarks = fields.Char()

    _sql_constraints = [("participant_unique", "unique(activity_id,student_id)", "A participant can appear only once.")]

    @api.constrains("activity_id", "student_id")
    def _check_participant(self):
        for line in self:
            line.activity_id.check_access_rule("write")
            if line.activity_id.batch_id not in line.student_id.course_detail_ids.batch_id:
                raise ValidationError(_("Participants must be enrolled in the activity batch."))
