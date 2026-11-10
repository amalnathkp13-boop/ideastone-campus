import base64
from datetime import timedelta
from io import BytesIO

from odoo.exceptions import AccessError, ValidationError
from PyPDF2 import PdfFileReader

from odoo import _, api, fields, models


def check_pdf(raw):
    if not raw or len(raw) > 5 * 1024 * 1024 or not raw.startswith(b"%PDF-"):
        raise ValidationError(_("Choose a PDF up to 5 MB."))
    try:
        pdf = PdfFileReader(BytesIO(raw), strict=False)
        if pdf.isEncrypted or not pdf.getNumPages():
            raise ValueError("Empty or encrypted PDF")
    except Exception as exc:
        raise ValidationError(_("Choose a readable, unencrypted PDF.")) from exc


class PlacementDrive(models.Model):
    _inherit = "campus.placement.drive"

    portal_published = fields.Boolean(string="List in student placements", copy=False)
    application_deadline = fields.Date(copy=False)
    sector = fields.Char()
    expected_ctc_lpa = fields.Float(string="Expected CTC (INR LPA)", digits=(10, 2))
    batch_ids = fields.Many2many("op.batch", string="Eligible sections", check_company=True)
    recruitment_process = fields.Text()

    @api.constrains("portal_published", "application_deadline", "interview_on", "expected_ctc_lpa")
    def _check_portal_details(self):
        for drive in self:
            if drive.expected_ctc_lpa < 0:
                raise ValidationError(_("Expected CTC cannot be negative."))
            if drive.portal_published and (not drive.application_deadline or
                    drive.application_deadline > drive.interview_on.date()):
                raise ValidationError(_("Set an application deadline on or before the drive date."))

    def _portal_matches(self, enrolment, academic):
        self.ensure_one()
        return bool(enrolment and academic and
                    (not self.course_ids or enrolment.course_id in self.course_ids) and
                    (not self.batch_ids or enrolment.batch_id in self.batch_ids) and
                    academic["percentage"] >= self.min_percentage and academic["arrears"] <= self.max_standing_arrears)


class PlacementProfile(models.Model):
    _name = "campus.placement.profile"
    _description = "Student placement profile"
    _rec_name = "student_id"
    _check_company_auto = True

    student_id = fields.Many2one("op.student", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="student_id.company_id", store=True, index=True)
    skills = fields.Char()
    preferred_roles = fields.Char()
    preferred_locations = fields.Char()
    experience = fields.Text(string="Projects or experience")
    consent = fields.Selection([("undecided", "Not recorded"), ("willing", "Willing to participate"),
                                ("declined", "Not participating")], default="undecided", required=True)
    resume = fields.Binary(attachment=True)
    resume_filename = fields.Char()
    resume_uploaded = fields.Date(readonly=True)
    resume_verified = fields.Boolean(copy=False)
    readiness_recorded = fields.Boolean(string="Practice scores recorded")
    quantitative = fields.Integer(string="Quantitative aptitude (%)")
    reasoning = fields.Integer(string="Logical reasoning (%)")
    verbal = fields.Integer(string="Verbal ability (%)")

    _sql_constraints = [("profile_student_unique", "unique(student_id)", "Each student has one placement profile.")]

    @api.constrains("quantitative", "reasoning", "verbal", "resume_verified", "resume")
    def _check_profile(self):
        for profile in self:
            if not all(0 <= score <= 100 for score in (profile.quantitative, profile.reasoning, profile.verbal)):
                raise ValidationError(_("Practice scores must be between 0 and 100."))
            if profile.resume_verified and not profile.resume:
                raise ValidationError(_("Upload a resume before verifying it."))


class PlacementResource(models.Model):
    _name = "campus.placement.resource"
    _description = "Placement preparation resource"
    _order = "sequence, id"

    name = fields.Char(required=True)
    description = fields.Char(required=True)
    icon = fields.Selection([("∑", "Aptitude"), ("⌘", "Technical"), ("◉", "Interview"), ("▤", "Document")],
                            default="▤", required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    published = fields.Boolean()
    document = fields.Binary(required=True, attachment=True)
    filename = fields.Char(required=True)

    @api.constrains("document", "filename")
    def _check_document(self):
        for resource in self:
            if not (resource.filename or "").lower().endswith(".pdf"):
                raise ValidationError(_("Upload a PDF preparation resource."))
            check_pdf(base64.b64decode(resource.with_context(bin_size=False).document or b""))


class PlacementMilestone(models.Model):
    _name = "campus.placement.milestone"
    _description = "Student-visible placement milestone"
    _order = "event_at, id"

    name = fields.Char(required=True)
    candidate_id = fields.Many2one("campus.placement.candidate", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="candidate_id.company_id", store=True, index=True)
    event_at = fields.Datetime()
    detail = fields.Text(string="Student-visible update")
    status = fields.Selection([("done", "Completed"), ("pending", "Scheduled"), ("waiting", "Pending")],
                              required=True, default="waiting")


class PlacementCandidate(models.Model):
    _inherit = "campus.placement.candidate"

    portal_enrolment_id = fields.Many2one("op.student.course", copy=False, ondelete="restrict")
    portal_applied_on = fields.Date(copy=False)
    profile_id = fields.Many2one("campus.placement.profile", copy=False, check_company=True)
    milestone_ids = fields.One2many("campus.placement.milestone", "candidate_id", string="Student-visible interview journey")

    @api.depends("portal_enrolment_id", "drive_id.batch_ids")
    def _compute_results(self):
        portal = self.filtered("portal_enrolment_id")
        super(PlacementCandidate, self - portal)._compute_results()
        for rec in portal:
            academic = self.env["campus.student.portal"]._placement_academic(rec.student_id, rec.portal_enrolment_id)
            rec.percentage = academic.get("percentage", 0)
            rec.standing_arrears = academic.get("arrears", 0)
            rec.ever_had_arrears = academic.get("ever_had_arrears", False)
            rec.eligible = rec.drive_id._portal_matches(rec.portal_enrolment_id, academic)

    @api.constrains("student_id", "drive_id", "company_id", "portal_enrolment_id", "profile_id")
    def _check_portal_identity(self):
        for rec in self:
            if rec.company_id != rec.drive_id.company_id or (rec.student_id.company_id and rec.student_id.company_id != rec.company_id):
                raise ValidationError(_("The student and drive must belong to the same college."))
            if (rec.portal_enrolment_id and rec.portal_enrolment_id.student_id != rec.student_id
                    or rec.profile_id and rec.profile_id.student_id != rec.student_id):
                raise ValidationError(_("The profile and enrolment must belong to this student."))


class StudentPlacements(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _placement_academic(self, student, enrolment):
        if not enrolment or not enrolment.batch_id or enrolment.student_id != student or enrolment.company_id != student.company_id:
            return {}
        results = self._records("op.result.line", [
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id),
            ("exam_id.batch_id", "=", enrolment.batch_id.id), ("exam_id.total_marks", ">", 0),
            "|", "&", ("exam_id.campus_managed", "=", True), "&", ("exam_id.campus_state", "=", "published"),
            ("campus_entered", "=", True),
            "&", ("exam_id.campus_managed", "=", False), ("exam_id.state", "in", ["result_updated", "done"]),
        ], order="id desc")
        latest = {}
        for row in results:
            latest.setdefault(row.exam_id.subject_id.id, row)
        if not latest:
            return {}
        return {"percentage": round(sum(row.marks * 100 / row.exam_id.total_marks for row in latest.values()) / len(latest), 2),
                "arrears": sum(row.status == "fail" for row in latest.values()),
                "ever_had_arrears": any(row.status == "fail" for row in results)}

    def _placement_profile(self, student):
        return self.env["campus.placement.profile"].sudo().search([("student_id", "=", student.id)], limit=1)

    def _placement_open(self, student, enrolment, today):
        source = self.env["campus.placement.drive"].sudo()
        if not enrolment or enrolment.state != "running" or (enrolment.campus_date_from and enrolment.campus_date_from > today
                or enrolment.campus_date_to and enrolment.campus_date_to < today):
            return source.browse()
        return source.search([
            ("company_id", "=", student.company_id.id), ("active", "=", True), ("portal_published", "=", True),
            ("state", "=", "approved"), ("application_deadline", ">=", today), ("interview_on", ">=", fields.Datetime.now()),
            "|", ("course_ids", "=", False), ("course_ids", "in", enrolment.course_id.ids),
            "|", ("batch_ids", "=", False), ("batch_ids", "in", enrolment.batch_id.ids),
        ], order="interview_on, id")

    def _placement_application_row(self, application, now):
        drive = application.drive_id
        milestones = application.milestone_ids
        completed = application.state in ("selected", "rejected") or drive.state in ("done", "cancelled")
        next_step = milestones.filtered(lambda step: step.status == "pending" and step.event_at and step.event_at >= now)[:1]
        latest = next_step or milestones.filtered(lambda step: step.status != "waiting" and (not step.event_at or step.event_at <= now))[-1:]
        labels = dict(application._fields["state"].selection)
        status = _("Interview scheduled") if next_step and not completed else labels[application.state]
        if application.state == "applied" and latest and not next_step and not completed:
            status = _("Under review")
        if drive.state == "cancelled" and application.state not in ("selected", "rejected"):
            status = _("Drive cancelled")
        elif drive.state == "done" and application.state not in ("selected", "rejected"):
            status = _("Drive closed")
        submitted = self._dates(application.portal_applied_on or application.create_date.date())
        timeline = [{"title": _("Application submitted"), "text": submitted, "tone": "done"}]
        timeline.extend({"title": step.name, "text": " · ".join(filter(None, (self._dates(step.event_at), step.detail))),
                         "tone": step.status if step.status != "pending" or not completed else "waiting"} for step in milestones)
        return {"id": application.id, "company": drive.recruiter_id.name, "role": drive.name, "applied": submitted,
                "stage": latest.name or labels[application.state], "next": self._dates(next_step.event_at) if not completed and next_step else (_("Completed") if completed else _("Awaiting update")),
                "status": status, "state": "closed" if completed else "active", "next_at": next_step.event_at if not completed else False,
                "tone": "offer" if application.state == "selected" else "rejected" if completed else "selected" if next_step else "applied",
                "offer": application.offer_reference if application.state == "selected" else "",
                "timeline": timeline}

    def _placement_overview(self, enrolment_id=None):
        student, enrolment, _enrolments, _date_from, _date_to = self._portal_context(enrolment_id)
        today, now = fields.Date.context_today(self), fields.Datetime.now()
        profile = self._placement_profile(student).with_context(bin_size=True)
        academic = self._placement_academic(student, enrolment)
        candidates = self._records("campus.placement.candidate", [
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id),
            ("drive_id.company_id", "=", student.company_id.id),
        ], order="create_date desc, id desc")
        applied = set(candidates.drive_id.ids)
        rows = []
        for drive in self._placement_open(student, enrolment, today):
            if not drive._portal_matches(enrolment, academic):
                continue
            departments = drive.course_ids.department_id | drive.batch_ids.course_id.department_id
            rows.append({"id": drive.id, "company": drive.recruiter_id.name, "role": drive.name, "sector": drive.sector,
                         "date": self._dates(fields.Datetime.context_timestamp(self, drive.interview_on).date()),
                         "deadline": self._dates(drive.application_deadline), "venue": drive.location,
                         "ctc": f"{drive.expected_ctc_lpa:.2f}".removesuffix("0") if drive.expected_ctc_lpa else "",
                         "closing": drive.application_deadline <= today + timedelta(days=5),
                         "departments": " · ".join(department.code or department.name for department in departments),
                         "description": drive.job_description, "process": drive.recruitment_process,
                         "applied": drive.id in applied})
        candidates = candidates.sorted(lambda row: (row.portal_applied_on or row.create_date.date(), row.id), reverse=True)
        applications = [self._placement_application_row(row, now) for row in candidates]
        interviews = sorted((row for row in applications if row["next_at"]), key=lambda row: row["next_at"])
        active = [row for row in applications if row["state"] == "active"]
        complete = sum(bool(value) for value in (student.email and (student.phone or student.mobile), academic,
            profile.resume, profile.skills, profile.preferred_roles, profile.experience))
        scores = [(_("Quantitative aptitude"), profile.quantitative), (_("Logical reasoning"), profile.reasoning),
                  (_("Verbal ability"), profile.verbal)] if profile.readiness_recorded else []
        resources = self._records("campus.placement.resource", [("company_id", "=", student.company_id.id),
            ("published", "=", True)], order="sequence, id")
        return {"drives": rows, "applications": applications, "active": len(active),
                "companies": len({row["company"] for row in active}), "interviews": len(interviews),
                "offers": sum(row.state == "selected" and bool(row.offer_reference or row.offered_salary) for row in candidates),
                "journey": (interviews or active or applications or [None])[0],
                "next": self._dates(interviews[0]["next_at"]) if interviews else "",
                "profile": {"id": profile.id, "skills": profile.skills, "roles": profile.preferred_roles,
                    "locations": profile.preferred_locations, "experience": profile.experience,
                    "resume": profile.resume_filename if profile.resume else "", "uploaded": self._dates(profile.resume_uploaded),
                    "verified": profile.resume_verified, "consent": profile.consent or "undecided",
                    "complete": round(complete * 100 / 6)},
                "academic": academic, "scores": scores, "weakest": min(scores, key=lambda row: row[1]) if scores else None,
                "resources": [{"id": item.id, "name": item.name, "description": item.description, "icon": item.icon} for item in resources]}

    def _save_placement(self, operation, payload, enrolment_id):
        student, enrolment, _enrolments, _date_from, _date_to = self._portal_context(enrolment_id)
        # Serialize saves and applications for this student, including creation of the first profile.
        self.env.cr.execute("SELECT id FROM op_student WHERE id = %s FOR UPDATE", [student.id])
        profile = self._placement_profile(student)
        profile.invalidate_recordset()
        if operation == "placement_apply":
            try:
                drive_id = int(payload.get("drive_id", ""))
            except (TypeError, ValueError) as exc:
                raise ValidationError(_("Choose a valid placement drive.")) from exc
            today = fields.Date.context_today(self)
            drive = self._placement_open(student, enrolment, today).filtered(lambda row: row.id == drive_id)
            if not drive:
                raise AccessError(_("This drive is unavailable for your enrolment."))
            drive._lock()
            if drive not in self._placement_open(student, enrolment, today) or not drive._portal_matches(enrolment, self._placement_academic(student, enrolment)):
                raise AccessError(_("You do not meet the current eligibility criteria for this drive."))
            if not profile.resume or not profile.skills or profile.consent != "willing":
                raise ValidationError(_("Add your skills and resume, then confirm participation before applying."))
            candidates = self.env["campus.placement.candidate"].sudo().with_context(active_test=False)
            if candidates.search_count([("drive_id", "=", drive.id), ("student_id", "=", student.id)]):
                raise ValidationError(_("You have already applied for this drive."))
            return candidates.create({"name": drive.name, "drive_id": drive.id, "student_id": student.id,
                "company_id": student.company_id.id, "portal_enrolment_id": enrolment.id, "profile_id": profile.id,
                "portal_applied_on": today}).id
        if operation == "placement_consent":
            consent = payload.get("consent")
            if consent not in ("willing", "declined"):
                raise ValidationError(_("Choose your participation preference."))
            values = {"consent": consent}
        else:
            values = {}
            for field, maximum in (("skills", 500), ("preferred_roles", 250), ("preferred_locations", 250), ("experience", 2000)):
                value = payload.get(field, "")
                if not isinstance(value, str) or len(value) > maximum:
                    raise ValidationError(_("Keep each profile field within its displayed length."))
                values[field] = value.strip()
            if payload.get("file"):
                name = payload.get("filename") or ""
                if len(name) > 150 or not name.lower().endswith(".pdf") or any(char in name for char in "/\\\r\n"):
                    raise ValidationError(_("Choose a PDF with a valid filename."))
                check_pdf(base64.b64decode(payload["file"], validate=True))
                values.update(resume=payload["file"], resume_filename=name,
                              resume_verified=False, resume_uploaded=fields.Date.context_today(self))
        if profile:
            return profile.write(values)
        return profile.create(dict(values, student_id=student.id)).id

    def _download(self, kind, record_id):
        if kind not in ("placement-resource", "placement-resume"):
            return super()._download(kind, record_id)
        student = self._identity()
        if kind == "placement-resource":
            resource = self.env["campus.placement.resource"].sudo().search([
                ("id", "=", record_id), ("company_id", "=", student.company_id.id), ("published", "=", True)], limit=1)
            data, name = resource.document, resource.filename
        else:
            profile = self._placement_profile(student)
            data, name = (profile.resume, profile.resume_filename) if profile.id == record_id else (False, False)
        if not data:
            raise AccessError(_("This document is not available."))
        return base64.b64decode(data), name, "application/pdf"
