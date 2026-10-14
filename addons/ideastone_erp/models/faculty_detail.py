from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyDetail(models.Model):
    _name = "campus.faculty.detail"
    _description = "Faculty education, service, language and document register"
    _inherit = "campus.record"

    faculty_id = fields.Many2one("op.faculty", required=True, ondelete="cascade", index=True)
    kind = fields.Selection([
        ("qualification", "Qualification"), ("experience", "Service history"),
        ("language", "Language"), ("document", "Document"),
    ], required=True, default="qualification")
    specialization = fields.Char()
    institution = fields.Char()
    university = fields.Char()
    year = fields.Integer()
    result = fields.Char()
    designation = fields.Char()
    date_from = fields.Date()
    date_to = fields.Date()
    nature = fields.Char()
    can_read = fields.Boolean()
    can_write = fields.Boolean()
    can_speak = fields.Boolean()
    reference = fields.Char()
    document = fields.Binary(attachment=True)
    filename = fields.Char()
    verification = fields.Selection([
        ("missing", "Missing"), ("pending", "Pending"), ("verified", "Verified"),
    ], default="pending", required=True, tracking=True)
    reviewer_id = fields.Many2one("res.users", readonly=True)
    next_action = fields.Text()

    @api.constrains("date_from", "date_to", "year")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Service end date must follow its start date."))
            if rec.year and not 1900 <= rec.year <= fields.Date.today().year + 10:
                raise ValidationError(_("Enter a valid qualification year."))

    def action_verify(self):
        if not self.env.user.has_group("ideastone_erp.group_people"):
            raise AccessError(_("HR permission is required to verify a document."))
        if any(rec.kind == "document" and not rec.document for rec in self):
            raise ValidationError(_("Upload the document before verification."))
        return super().write({"verification": "verified", "reviewer_id": self.env.uid})

    def write(self, vals):
        if "reviewer_id" in vals or vals.get("verification") == "verified":
            raise ValidationError(_("Use Verify to record document verification."))
        if "document" in vals:
            vals = dict(vals, verification="pending", reviewer_id=False)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if any(v.get("verification") == "verified" or v.get("reviewer_id") for v in vals_list):
            raise ValidationError(_("New documents must be reviewed before verification."))
        return super().create(vals_list)


class OpFaculty(models.Model):
    _inherit = "op.faculty"

    campus_staff_code = fields.Char(index=True)
    campus_designation = fields.Char()
    campus_category = fields.Selection([("teaching", "Teaching"), ("non_teaching", "Non-teaching"), ("admin", "Administration")])
    campus_service_type = fields.Selection([("permanent", "Permanent"), ("contract", "Contract"), ("temporary", "Temporary")])
    campus_joining_date = fields.Date()
    campus_reporting_id = fields.Many2one("op.faculty", string="Reporting to", ondelete="restrict")
    campus_work_location = fields.Char()
    campus_community = fields.Char()
    campus_caste = fields.Char()
    campus_caste_certificate_name = fields.Char()
    campus_religion = fields.Char()
    campus_blood_donor = fields.Boolean()
    campus_anniversary = fields.Date()
    campus_alternate_mobile = fields.Char()
    campus_father_name = fields.Char()
    campus_mother_name = fields.Char()
    campus_spouse_name = fields.Char()
    campus_pan_reference = fields.Char("PAN reference (masked)", groups="ideastone_erp.group_people")
    campus_aadhaar_last4 = fields.Char("Aadhaar last four", size=4, groups="ideastone_erp.group_people")
    campus_passport_reference = fields.Char(groups="ideastone_erp.group_people")
    campus_pf_reference = fields.Char(groups="ideastone_erp.group_people")
    campus_esi_reference = fields.Char(groups="ideastone_erp.group_people")
    campus_registration_reference = fields.Char()
    campus_identification_marks = fields.Text(groups="ideastone_erp.group_people")
    campus_residence_location = fields.Char()
    campus_emergency_phone = fields.Char()
    campus_marital_status = fields.Selection([("single", "Single"), ("married", "Married"), ("other", "Other")])
    campus_alternate_email = fields.Char()
    campus_communication_address = fields.Text()
    campus_travel_mode = fields.Char()
    campus_previous_education = fields.Text()
    campus_notes = fields.Text()
    campus_detail_ids = fields.One2many("campus.faculty.detail", "faculty_id")

    _sql_constraints = [("campus_staff_code_unique", "unique(campus_staff_code)", "Staff code must be unique.")]

    @api.constrains("campus_aadhaar_last4", "campus_joining_date", "campus_reporting_id")
    def _check_campus_profile(self):
        for rec in self:
            if rec.campus_aadhaar_last4 and (len(rec.campus_aadhaar_last4) != 4 or not rec.campus_aadhaar_last4.isdigit()):
                raise ValidationError(_("Store only the last four digits of Aadhaar."))
            if rec.campus_joining_date and rec.campus_joining_date > fields.Date.today():
                raise ValidationError(_("Joining date cannot be in the future."))
            if rec.campus_reporting_id == rec:
                raise ValidationError(_("A staff member cannot report to themselves."))

    def write(self, vals):
        privileged = self.env.su or self.env.user.has_group("ideastone_erp.group_people") or self.env.user.has_group("openeducat_core.group_op_back_office_admin")
        if not privileged:
            editable = {
                "campus_alternate_email", "campus_communication_address", "campus_travel_mode",
                "campus_previous_education", "campus_notes", "campus_caste", "campus_caste_certificate_name",
                "campus_religion", "campus_blood_donor", "campus_anniversary", "campus_alternate_mobile",
                "campus_father_name", "campus_mother_name", "campus_spouse_name", "campus_registration_reference",
                "campus_residence_location", "campus_emergency_phone", "campus_marital_status", "campus_community",
                "email", "phone", "mobile", "street", "street2", "city", "zip", "state_id", "country_id",
                "blood_group", "image_1920", "message_follower_ids", "activity_ids",
            }
            if set(vals) - editable:
                raise AccessError(_("HR must update official employment, identity and account assignments."))
        return super().write(vals)
