from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

ADMISSION_ROLES = ("ideastone_erp.group_mvp_admissions", "ideastone_erp.group_mvp_registrar")
STAGES = [
    ("new", "New"), ("contacted", "Contacted"), ("started", "Application started"),
    ("submitted", "Submitted"), ("documents", "Documents pending"), ("review", "Under review"),
    ("approved", "Approved"), ("rejected", "Rejected"), ("waitlisted", "Waitlisted"), ("enrolled", "Enrolled"),
]


class AdmissionRegister(models.Model):
    _inherit = "op.admission.register"

    min_count = fields.Integer(default=1)


class Enquiry(models.Model):
    _inherit = "crm.lead"

    campus_enquiry = fields.Boolean(string="College enquiry")
    campus_course_id = fields.Many2one("op.course", string="Programme")
    campus_year_id = fields.Many2one("op.academic.year", string="Academic year")
    campus_contacted = fields.Boolean(string="Contacted", tracking=True)

    def _check_campus_enquiry_permission(self):
        if not self.env.su and not any(self.env.user.has_group(g) for g in ADMISSION_ROLES):
            raise AccessError(_("Admissions permission is required for college enquiries."))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("default_campus_enquiry") or any(v.get("campus_enquiry") for v in vals_list):
            self._check_campus_enquiry_permission()
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered("campus_enquiry") or vals.get("campus_enquiry"):
            self._check_campus_enquiry_permission()
        return super().write(vals)

    def action_campus_application(self):
        self.ensure_one()
        if not any(self.env.user.has_group(g) for g in ADMISSION_ROLES) and not self.env.su:
            raise AccessError(_("Admissions permission is required."))
        self.check_access_rule("read")
        existing = self.env["op.admission"].search([("campus_lead_id", "=", self.id)], limit=1)
        action = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp.mvp_applications")
        action.update(views=[(self.env.ref("ideastone_erp.mvp_admission_form").id, "form")], res_id=existing.id or False,
                      context={"default_campus_managed": True, "default_campus_lead_id": self.id,
                               "default_first_name": self.contact_name or self.partner_name or self.name,
                               "default_last_name": "", "default_name": self.contact_name or self.name,
                               "default_phone": self.phone, "default_email": self.email_from,
                               "default_course_id": self.campus_course_id.id, "default_company_id": self.company_id.id})
        return action


class DocumentRequirement(models.Model):
    _name = "campus.admission.requirement"
    _description = "Admission document requirement"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    course_id = fields.Many2one("op.course", string="Programme (blank for all)")
    required = fields.Boolean(default=True)
    active = fields.Boolean(default=True)


class AdmissionDocument(models.Model):
    _name = "campus.admission.document"
    _description = "Applicant document verification"
    _inherit = "campus.mvp.mixin"

    admission_id = fields.Many2one("op.admission", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="admission_id.company_id", store=True, index=True)
    student_id = fields.Many2one(related="admission_id.student_id", store=True, index=True)
    requirement_id = fields.Many2one("campus.admission.requirement", required=True, ondelete="restrict")
    name = fields.Char(related="requirement_id.name", store=True)
    file = fields.Binary(attachment=True, required=True)
    filename = fields.Char(required=True)
    note = fields.Text(string="Verification / rejection note")
    state = fields.Selection([("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")], default="pending", readonly=True)
    verified_by = fields.Many2one("res.users", readonly=True)
    verified_on = fields.Datetime(readonly=True)
    _sql_constraints = [("campus_document_requirement", "unique(admission_id, requirement_id)", "Upload one document per checklist requirement.")]

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({"verified_by", "verified_on", "state"}) for v in vals_list):
            raise AccessError(_("Use document verification to record a decision."))
        records = super().create(vals_list)
        records._mvp_company("admission_id", "requirement_id")
        return records

    def write(self, vals):
        if {"verified_by", "verified_on", "state", "admission_id", "requirement_id"}.intersection(vals):
            raise AccessError(_("Verification and document identity are maintained by the workflow."))
        if any(r.admission_id.campus_stage in {"approved", "enrolled"} for r in self):
            raise ValidationError(_("Approved admission evidence must be retained unchanged."))
        if "file" in vals:
            vals = dict(vals, state="pending", verified_by=False, verified_on=False)
        return super().write(vals)

    def action_verify(self):
        self._mvp_require(*ADMISSION_ROLES)
        self._mvp_lock()
        if any(not rec.file for rec in self):
            raise ValidationError(_("Upload a document before verification."))
        super().write({"state": "verified", "verified_by": self.env.uid, "verified_on": fields.Datetime.now()})
        self._mvp_log("Admission document verified")

    def action_reject(self):
        self._mvp_require(*ADMISSION_ROLES)
        self._mvp_lock()
        if any(not (rec.note or "").strip() for rec in self):
            raise ValidationError(_("Explain why this document was rejected."))
        super().write({"state": "rejected", "verified_by": self.env.uid, "verified_on": fields.Datetime.now()})
        self._mvp_log("Admission document rejected")

    def unlink(self):
        if any(rec.state != "pending" or rec.admission_id.campus_stage in {"approved", "enrolled"} for rec in self):
            raise ValidationError(_("Retain reviewed admission evidence."))
        return super().unlink()


class Admission(models.Model):
    _inherit = ["op.admission", "campus.mvp.mixin"]
    _name = "op.admission"

    campus_managed = fields.Boolean(default=False, copy=False)
    campus_stage = fields.Selection(STAGES, default="started", required=True, readonly=True, tracking=True, copy=False)
    campus_lead_id = fields.Many2one("crm.lead", string="Source enquiry", ondelete="restrict")
    campus_source_id = fields.Many2one("utm.source", string="Source")
    campus_officer_id = fields.Many2one("res.users", string="Assigned officer", default=lambda self: self.env.user)
    campus_document_ids = fields.One2many("campus.admission.document", "admission_id", string="Documents")
    campus_reason = fields.Text(string="Decision / exception reason")
    campus_document_exception = fields.Boolean(string="Approve documented checklist exception")
    campus_enrolment_id = fields.Many2one("op.student.course", readonly=True, copy=False, ondelete="restrict")
    campus_year_id = fields.Many2one(related="register_id.academic_years_id", store=True)
    _sql_constraints = [("campus_enquiry_intake", "unique(campus_lead_id, register_id)", "This enquiry already has an application for this intake.")]

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({"campus_stage", "campus_enrolment_id"}) for v in vals_list):
            raise AccessError(_("New applications must start in the application workflow."))
        records = super().create(vals_list)
        records._mvp_company("register_id", "course_id", "batch_id", "student_id", "campus_lead_id")
        return records

    def write(self, vals):
        if {"campus_stage", "campus_enrolment_id"}.intersection(vals):
            raise AccessError(_("Use the admission workflow to change decisions or enrolment."))
        if self.filtered("campus_managed") and {"campus_managed", "state", "partner_id", "nbr", "admission_date"}.intersection(vals):
            raise AccessError(_("Use approved conversion to update student links or admission status."))
        if any(r.campus_managed and r.campus_stage in {"approved", "enrolled"} for r in self) and set(vals) - {"active", "message_follower_ids", "activity_ids"}:
            raise ValidationError(_("Approved applications are locked. Retain their decision history."))
        result = super().write(vals)
        self._mvp_company("register_id", "course_id", "batch_id", "student_id", "campus_lead_id")
        return result

    def action_campus_submit(self):
        return self._campus_decide("submitted")

    def action_campus_review(self):
        return self._campus_decide("review")

    def action_campus_documents(self):
        return self._campus_decide("documents")

    def action_campus_approve(self):
        return self._campus_decide("approved")

    def action_campus_reject(self):
        return self._campus_decide("rejected")

    def action_campus_waitlist(self):
        return self._campus_decide("waitlisted")

    def _campus_decide(self, target):
        self._mvp_require(*ADMISSION_ROLES)
        self._mvp_lock()
        transitions = {"started": {"submitted"}, "submitted": {"review", "documents"}, "documents": {"submitted", "review"},
                       "review": {"approved", "rejected", "waitlisted", "documents"}, "waitlisted": {"review"}}
        for rec in self:
            if target not in transitions.get(rec.campus_stage, set()):
                raise ValidationError(_("This admission decision is not available from the current stage."))
            if target in {"rejected", "waitlisted"} and not (rec.campus_reason or "").strip():
                raise ValidationError(_("Enter a reason for this decision."))
            if target == "approved":
                required = self.env["campus.admission.requirement"].search([
                    ("company_id", "=", rec.company_id.id), ("required", "=", True),
                    "|", ("course_id", "=", False), ("course_id", "=", rec.course_id.id)])
                verified = rec.campus_document_ids.filtered(lambda d: d.state == "verified").requirement_id
                if required - verified and not (rec.campus_document_exception and (rec.campus_reason or "").strip()):
                    raise ValidationError(_("Verify required documents or record an explicit exception and reason."))
                if not rec.batch_id or not rec.campus_year_id or rec.batch_id.course_id != rec.course_id:
                    raise ValidationError(_("Configure the intake academic year and a matching programme section before approval."))
            super(Admission, rec).write({"campus_stage": target, "state": {"submitted": "submit", "approved": "admission", "rejected": "reject"}.get(target, "pending")})
            rec._mvp_log("Admission: %s" % dict(STAGES)[target], rec.campus_reason)
        return True

    def enroll_student(self):
        legacy = self.filtered(lambda r: not r.campus_managed)
        if legacy:
            super(Admission, legacy).enroll_student()
        for rec in self - legacy:
            rec._mvp_require(*ADMISSION_ROLES)
            rec._mvp_lock()
            if rec.campus_enrolment_id:
                continue
            if rec.campus_stage != "approved":
                raise ValidationError(_("Only an approved application can be converted."))
            rec._mvp_company("register_id", "course_id", "batch_id", "student_id")
            rec.register_id.flush_recordset()
            self.env.cr.execute("SELECT id FROM op_admission_register WHERE id=%s FOR UPDATE", [rec.register_id.id])
            if rec.register_id.max_count and self.search_count([("register_id", "=", rec.register_id.id), ("state", "=", "done")]) >= rec.register_id.max_count:
                raise ValidationError(_("This admission intake has reached its configured capacity."))
            student = rec.student_id
            if not student:
                partner = self.env["res.partner"].create({"name": rec.name, "email": rec.email, "phone": rec.phone,
                                                           "mobile": rec.mobile, "company_id": rec.company_id.id})
                student = self.env["op.student"].create({"partner_id": partner.id, "first_name": rec.first_name,
                    "last_name": rec.last_name, "gender": rec.gender, "birth_date": rec.birth_date,
                    "gr_no": self.env["ir.sequence"].with_company(rec.company_id).next_by_code("campus.student"),
                    "campus_admission_date": fields.Date.context_today(rec)})
            existing = self.env["op.student.course"].search([("student_id", "=", student.id), ("course_id", "=", rec.course_id.id), ("batch_id", "=", rec.batch_id.id)], limit=1)
            enrolment = existing or self.env["op.student.course"].create({"student_id": student.id, "course_id": rec.course_id.id,
                "batch_id": rec.batch_id.id, "academic_years_id": rec.campus_year_id.id,
                "academic_term_id": rec.register_id.academic_term_id.id, "subject_ids": [(6, 0, rec.course_id.subject_ids.ids)]})
            super(Admission, rec).write({"student_id": student.id, "partner_id": student.partner_id.id, "is_student": True,
                "campus_enrolment_id": enrolment.id, "campus_stage": "enrolled", "state": "done", "nbr": 1,
                "admission_date": fields.Date.context_today(rec)})
            rec._mvp_log("Applicant converted to student", details={"student_id": student.id, "enrolment_id": enrolment.id})
        return True

    def unlink(self):
        if any(r.campus_stage not in {"new", "started"} or r.student_id for r in self.filtered("campus_managed")):
            raise ValidationError(_("Archive reviewed applications instead of deleting admission history."))
        return super().unlink()


class Student(models.Model):
    _inherit = ["op.student", "campus.mvp.mixin"]
    _name = "op.student"

    campus_status = fields.Selection([(s, s.replace("_", " ").title()) for s in ["applicant", "active", "on_hold", "graduated", "withdrawn"]], default="active", required=True, tracking=True)
    campus_status_reason = fields.Text(string="Status change reason")
    campus_status_date = fields.Date(string="Status effective date", default=fields.Date.context_today)
    campus_admission_date = fields.Date(string="Admission date")
    campus_guardian_ids = fields.Many2many("res.partner", "campus_student_guardian_rel", string="Guardians")
    campus_admission_document_ids = fields.One2many("campus.admission.document", "student_id", string="Admission documents")

    def write(self, vals):
        if {"campus_status", "active"}.intersection(vals):
            self._mvp_require(*ADMISSION_ROLES)
            if not (vals.get("campus_status_reason") or all(r.campus_status_reason for r in self)):
                raise ValidationError(_("Record a reason for changing student status or archiving."))
        result = super().write(vals)
        if {"campus_status", "active"}.intersection(vals):
            self._mvp_log("Student status changed", details={k: str(v) for k, v in vals.items()})
        return result

    def unlink(self):
        for rec in self:
            if rec.course_detail_ids or rec.fees_detail_ids or self.env["op.attendance.line"].sudo().search_count([("student_id", "=", rec.id)]) or self.env["op.result.line"].sudo().search_count([("student_id", "=", rec.id)]):
                raise ValidationError(_("This student has academic or financial history. Withdraw or archive with a reason."))
        return super().unlink()

    def action_campus_records(self, kind):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        targets = {"fees": ("op.student.fees.details", "student_id"), "attendance": ("op.attendance.line", "student_id"),
                   "results": ("op.result.line", "student_id"), "applications": ("op.admission", "student_id")}
        if kind not in targets:
            raise ValidationError(_("Unknown student register."))
        model, field = targets[kind]
        self.env[model].check_access_rights("read")
        return {"type": "ir.actions.act_window", "name": kind.title(), "res_model": model,
                "view_mode": "tree,form", "domain": [(field, "=", self.id)]}

    def action_campus_fees(self):
        return self.action_campus_records("fees")

    def action_campus_attendance(self):
        return self.action_campus_records("attendance")

    def action_campus_results(self):
        return self.action_campus_records("results")

    def action_campus_applications(self):
        return self.action_campus_records("applications")
