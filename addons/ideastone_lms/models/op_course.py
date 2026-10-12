from odoo import fields, models


class OpCourse(models.Model):
    _inherit = "op.course"

    lms_course_key = fields.Char(
        "OpenOlat course key",
        help="Repository entry key of the matching OpenOlat course. Students of this programme are enrolled in it when their LMS account is provisioned.",
    )
