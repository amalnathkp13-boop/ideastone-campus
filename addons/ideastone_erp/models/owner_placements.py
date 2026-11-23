"""Owner placement reporting uses the same profiles, drives and offers as students."""

import math
from collections import defaultdict
from datetime import datetime, time
from uuid import UUID

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

BASELINE_CGPA = 6.5
MODES = [("campus", "On campus"), ("virtual", "Virtual"), ("offsite", "Off campus")]


def _text(value, maximum, required=True):
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value or required and not value.strip():
        raise ValidationError(_("Enter valid text within the displayed length."))
    return value.strip()


def _number(value, minimum, maximum):
    if isinstance(value, bool):
        raise ValidationError(_("Enter a valid number."))
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("Enter a valid number.")) from exc
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValidationError(_("Enter a number between %(minimum)s and %(maximum)s.", minimum=minimum, maximum=maximum))
    return number


class PlacementDepartment(models.Model):
    _inherit = "op.department"

    placement_coordinator = fields.Char(string="Placement coordinator")
    placement_sequence = fields.Integer(string="Placement display order", default=10)


class PlacementProfile(models.Model):
    _inherit = "campus.placement.profile"

    graduation_year = fields.Integer(string="Graduating batch")
    placement_enrolment_id = fields.Many2one("op.student.course", string="Placement enrolment", ondelete="restrict")
    cgpa_recorded = fields.Boolean(string="CGPA verified")
    cgpa = fields.Float(string="Verified CGPA", digits=(4, 2))
    non_willing_reason = fields.Char(string="Career plan / non-participation reason")
    technical_recorded = fields.Boolean(string="Technical score recorded")
    technical = fields.Integer(string="Technical readiness (%)")

    @api.constrains("graduation_year", "placement_enrolment_id", "student_id", "cgpa", "technical")
    def _check_owner_placement_profile(self):
        for record in self:
            if record.graduation_year and not 1900 <= record.graduation_year <= 2200:
                raise ValidationError(_("Enter a graduating batch between 1900 and 2200."))
            if not math.isfinite(record.cgpa) or not 0 <= record.cgpa <= 10 or not 0 <= record.technical <= 100:
                raise ValidationError(_("CGPA must be between 0 and 10 and readiness between 0 and 100."))
            enrolment = record.placement_enrolment_id
            if enrolment and (enrolment.student_id != record.student_id or enrolment.company_id != record.company_id):
                raise ValidationError(_("The placement enrolment must belong to the same student and college."))


class PlacementDrive(models.Model):
    _inherit = "campus.placement.drive"

    graduation_year = fields.Integer(string="Graduating batch")
    minimum_cgpa = fields.Float(string="Minimum verified CGPA", digits=(4, 2))
    placement_mode = fields.Selection(MODES, default="campus", required=True)
    coordinator_name = fields.Char(string="Placement coordinator")
    owner_preview_added = fields.Boolean(copy=False, readonly=True)
    owner_request_key = fields.Char(copy=False, readonly=True, size=36, index=True)

    _sql_constraints = [("owner_request_unique", "unique(company_id, owner_request_key)", "This placement drive has already been created.")]

    @api.constrains("graduation_year", "minimum_cgpa", "course_ids", "batch_ids", "company_id")
    def _check_owner_placement_drive(self):
        for record in self:
            if record.graduation_year and not 1900 <= record.graduation_year <= 2200:
                raise ValidationError(_("Enter a graduating batch between 1900 and 2200."))
            if not math.isfinite(record.minimum_cgpa) or not 0 <= record.minimum_cgpa <= 10:
                raise ValidationError(_("Minimum CGPA must be between 0 and 10."))
            if any(course.company_id != record.company_id for course in record.course_ids) or any(batch.company_id != record.company_id for batch in record.batch_ids):
                raise ValidationError(_("Eligible programmes and sections must belong to the drive's college."))

    def _portal_matches(self, enrolment, academic):
        if not super()._portal_matches(enrolment, academic):
            return False
        profile = self.env["campus.placement.profile"].sudo().search([("student_id", "=", enrolment.student_id.id)], limit=1)
        year = profile.graduation_year
        if not year and enrolment.academic_term_id.campus_sequence >= enrolment.course_id.campus_duration - 1:
            year = enrolment.academic_years_id.end_date.year if enrolment.academic_years_id.end_date else 0
        return (not self.graduation_year or year == self.graduation_year) and (
            not self.minimum_cgpa or profile.cgpa_recorded and profile.cgpa >= self.minimum_cgpa)

    def action_approve(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_owner") or self.env.user.has_group("ideastone_erp.group_manager"):
            return super().action_approve()
        # Owners approve this shared placement record without acquiring every Campus Manager permission.
        self._lock()
        if any(record.company_id != self.env.company for record in self):
            raise AccessError(_("Approve placement drives only in the currently selected college."))
        for record in self:
            if record.state != "submitted":
                raise ValidationError(_("Submit the drive before approving it."))
            record._validate_transition("approved")
        return self._set_system_values({"state": "approved", "approved_by": self.env.uid, "approved_on": fields.Datetime.now()})


class PlacementCandidate(models.Model):
    _inherit = "campus.placement.candidate"

    offer_decision = fields.Selection([("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")], default="pending", required=True, tracking=True)
    offer_accepted_on = fields.Date(string="Offer accepted on", tracking=True)
    joined_on = fields.Date(string="Joining confirmed on", tracking=True)

    @api.depends("drive_id.minimum_cgpa", "drive_id.graduation_year", "profile_id.cgpa", "profile_id.cgpa_recorded", "profile_id.graduation_year")
    def _compute_results(self):
        super()._compute_results()
        for record in self.filtered(lambda candidate: not candidate.portal_enrolment_id and (candidate.drive_id.minimum_cgpa or candidate.drive_id.graduation_year)):
            profile = self.env["campus.placement.profile"].sudo().search([("student_id", "=", record.student_id.id)], limit=1)
            enrolment = profile.placement_enrolment_id or record.student_id.course_detail_ids.sorted("id", reverse=True)[:1]
            academic = self.env["campus.student.portal"]._placement_academic(record.student_id, enrolment)
            record.percentage = academic.get("percentage", 0)
            record.standing_arrears = academic.get("arrears", 0)
            record.ever_had_arrears = academic.get("ever_had_arrears", False)
            record.eligible = record.drive_id._portal_matches(enrolment, academic)

    @api.constrains("offer_decision", "offer_accepted_on", "joined_on", "state")
    def _check_offer_outcome(self):
        for record in self:
            if (record.offer_decision != "pending" or record.offer_accepted_on or record.joined_on) and record.state != "selected":
                raise ValidationError(_("Record an offer decision only after the student is selected."))
            if record.offer_accepted_on and record.offer_decision != "accepted":
                raise ValidationError(_("An acceptance date requires an accepted offer."))
            if record.joined_on and (record.offer_decision != "accepted" or not record.offer_accepted_on or record.joined_on < record.offer_accepted_on):
                raise ValidationError(_("Confirm acceptance before joining, with the joining date on or after acceptance."))
            if record.joined_on and record.joined_on > fields.Date.context_today(record):
                raise ValidationError(_("Confirm actual joining only on or after the joining date."))


class PlacementImprovementPlan(models.Model):
    _name = "campus.placement.improvement.plan"
    _description = "Placement improvement follow-up plan"
    _inherit = "campus.record"
    _order = "create_date desc, id desc"

    kind = fields.Selection([("skills", "Readiness"), ("outreach", "Recruiter outreach"), ("resume", "Resume clinic"), ("student", "Student follow-up")], required=True)
    graduation_year = fields.Integer(required=True)
    department_id = fields.Many2one("op.department", check_company=True, ondelete="restrict")
    student_id = fields.Many2one("op.student", ondelete="restrict")
    student_ids = fields.Many2many("op.student", string="Affected students")
    owner_label = fields.Char(required=True)
    note = fields.Text(required=True)
    state = fields.Selection([("planned", "Planned"), ("in_progress", "In progress"), ("done", "Completed"), ("cancelled", "Cancelled")], default="planned", required=True, tracking=True)
    owner_preview_added = fields.Boolean(copy=False, readonly=True)
    plan_key = fields.Char(compute="_compute_plan_key", store=True, index=True)

    _sql_constraints = [("unique_scope", "unique(company_id, plan_key)", "An improvement plan already exists for this cohort and purpose.")]

    @api.depends("kind", "graduation_year", "department_id", "student_id")
    def _compute_plan_key(self):
        for record in self:
            record.plan_key = f"{record.kind}:{record.graduation_year}:{record.department_id.id or 0}:{record.student_id.id or 0}"

    @api.constrains("company_id", "graduation_year", "department_id", "student_id", "student_ids", "kind")
    def _check_plan_scope(self):
        for record in self:
            if not 1900 <= record.graduation_year <= 2200:
                raise ValidationError(_("Choose a valid graduating batch."))
            if any(student.company_id != record.company_id for student in record.student_id | record.student_ids):
                raise ValidationError(_("All plan participants must belong to the same college."))
            if record.kind == "student" and not record.student_id:
                raise ValidationError(_("Choose the student for an individual follow-up plan."))


class OwnerPlacementsUI(models.AbstractModel):
    _name = "campus.owner.placements.ui"
    _description = "Owner placement overview and working plans"

    def _check_owner(self):
        if not self.env.user.has_group("base.group_user") or not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
            raise AccessError(_("The Campus Placements workspace requires an Owner account."))
        if self.env.company not in self.env.user.company_ids:
            raise AccessError(_("Choose an authorised college."))

    def _records(self, model, domain=None, **kwargs):
        source = self.env[model].sudo().with_context(active_test=False)
        records = source.search([("company_id", "=", self.env.company.id)] + (domain or []), limit=20001, **kwargs)
        if len(records) > 20000:
            raise ValidationError(_("This college has too many placement records to load in one workspace."))
        return records

    def _preview_enabled(self):
        return bool(self.env.cr.dbname == "owner_placements_preview" and self.env.company.campus_demo and
                    self.env["ir.config_parameter"].sudo().get_param("owner_placements.preview_company_id") == str(self.env.company.id))

    @api.model
    def get_data(self):
        self._check_owner()
        company = self.env.company
        departments = self._records("op.department", [("active", "=", True)], order="placement_sequence,code,name,id")
        profiles = self._records("campus.placement.profile").with_context(bin_size=True)
        profile_map = {profile.student_id.id: profile for profile in profiles}
        enrolments = self._records("op.student.course", order="id desc")
        by_student = defaultdict(list)
        for enrolment in enrolments:
            if enrolment.student_id.company_id == company and enrolment.course_id.company_id == company:
                by_student[enrolment.student_id.id].append(enrolment)
        student_records = self._records("op.student", order="name,id")
        drives = self._records("campus.placement.drive", [("active", "=", True)], order="interview_on,id")
        candidates = self._records("campus.placement.candidate", [("active", "=", True), ("state", "=", "selected")], order="id desc")
        all_offers = defaultdict(list)
        for candidate in candidates:
            if candidate.student_id.company_id == company and candidate.drive_id.company_id == company and (candidate.offer_reference or candidate.offered_salary):
                all_offers[candidate.student_id.id].append(candidate)
        students, offers, unassigned = [], [], 0
        for student in student_records:
            profile = profile_map.get(student.id, self.env["campus.placement.profile"].sudo())
            options = by_student.get(student.id, [])
            final = next((entry for entry in options if entry.academic_term_id and entry.academic_term_id.campus_sequence >= entry.course_id.campus_duration - 1), None)
            enrolment = profile.placement_enrolment_id or final or (options[0] if options else self.env["op.student.course"].sudo())
            year = profile.graduation_year or (final.academic_years_id.end_date.year if final and final.academic_years_id.end_date else 0)
            department = enrolment.course_id.department_id
            if not year or not department or department.company_id != company:
                unassigned += 1
                continue
            eligible = bool(profile.cgpa_recorded and profile.cgpa >= BASELINE_CGPA)
            current_offers = [offer for offer in all_offers[student.id] if not offer.drive_id.graduation_year or offer.drive_id.graduation_year == year]
            primary = sorted(current_offers, key=lambda row: (bool(row.joined_on), row.offer_decision == "accepted", row.offer_decision == "pending", row.offered_salary, row.id), reverse=True)
            primary = primary[0] if primary else None
            row = {"id": str(student.id), "register": student.gr_no or enrolment.roll_number or str(student.id), "name": student.name,
                   "dept": str(department.id), "department": department.code or department.name, "year": year,
                   "willing": profile.consent == "willing", "consent": profile.consent or "undecided", "eligible": eligible,
                   "placed": bool(primary), "company": primary.drive_id.recruiter_id.name if primary else "—",
                   "salary": round(primary.offered_salary / 100000, 2) if primary else 0,
                   "accepted": bool(primary and primary.offer_decision == "accepted"), "joined": bool(primary and primary.joined_on),
                   "cgpa": profile.cgpa if profile.cgpa_recorded else None, "aptitude": profile.quantitative if profile.readiness_recorded else None,
                   "coding": profile.technical if profile.technical_recorded else None, "communication": profile.verbal if profile.readiness_recorded else None,
                   "resume": bool(profile.resume and profile.resume_verified), "reason": profile.non_willing_reason or ("Participation not recorded" if profile.consent != "declined" else "Reason not recorded"),
                   "profile_id": profile.id or False, "enrolment_id": enrolment.id}
            students.append(row)
            for offer in all_offers[student.id]:
                offers.append({"id": str(offer.id), "candidate_id": offer.id, "student_id": row["id"], "register": row["register"],
                               "name": student.name, "dept": row["dept"], "department": row["department"], "year": offer.drive_id.graduation_year or year,
                               "company": offer.drive_id.recruiter_id.name, "role": offer.drive_id.name,
                               "salary": round(offer.offered_salary / 100000, 2), "accepted": offer.offer_decision == "accepted",
                               "joined": bool(offer.joined_on), "decision": offer.offer_decision,
                               "join_date": str(offer.joined_on) if offer.joined_on else "", "reference": offer.offer_reference or ""})
        drive_rows, academic_cache = [], {}
        portal = self.env["campus.student.portal"]
        for drive in drives:
            selected = (drive.course_ids.department_id | drive.batch_ids.course_id.department_id).filtered(lambda dep: dep.company_id == company)
            selected = selected or departments
            drive_date = fields.Datetime.context_timestamp(self, drive.interview_on).date()
            today = fields.Date.context_today(self)
            if drive_date < today or drive.state in {"done", "cancelled"}:
                continue
            status = {"draft": "Draft", "submitted": "Awaiting approval", "done": "Completed", "cancelled": "Cancelled"}.get(drive.state)
            if not status:
                status = "Registration open" if drive.portal_published and drive.application_deadline and drive.application_deadline >= today and drive_date >= today else "Scheduled" if drive_date >= today else "Registration closed"
            selected_ids = {str(department.id) for department in selected}
            eligible_ids = []
            for student in students:
                if (not student["willing"] or student["placed"] or student["dept"] not in selected_ids
                        or drive.graduation_year and student["year"] != drive.graduation_year
                        or drive.minimum_cgpa and (student["cgpa"] is None or student["cgpa"] < drive.minimum_cgpa)):
                    continue
                enrolment = enrolments.browse(student["enrolment_id"])
                key = (int(student["id"]), enrolment.id)
                if key not in academic_cache:
                    academic_cache[key] = portal._placement_academic(student_records.browse(key[0]), enrolment)
                if drive._portal_matches(enrolment, academic_cache[key]):
                    eligible_ids.append(student["id"])
            drive_rows.append({"id": str(drive.id), "company": drive.recruiter_id.name, "role": drive.name,
                               "date": str(drive_date), "deadline": str(drive.application_deadline) if drive.application_deadline else "",
                               "salary": drive.expected_ctc_lpa, "cgpa": drive.minimum_cgpa, "dept": ",".join(sorted(selected_ids)),
                               "department_codes": ",".join(department.code or department.name for department in selected), "location": drive.location,
                               "mode": dict(MODES)[drive.placement_mode], "coordinator": drive.coordinator_name or drive.spoc_id.name,
                               "status": status, "year": drive.graduation_year, "process": drive.recruitment_process or "Registration → aptitude assessment → technical interview → HR interview → offer decision",
                               "eligible_ids": eligible_ids})
        plans = self._records("campus.placement.improvement.plan", [("active", "=", True)])
        years = sorted({student["year"] for student in students} | {drive.graduation_year for drive in drives if drive.graduation_year}, reverse=True)
        current = fields.Date.context_today(self).year + (1 if fields.Date.context_today(self).month >= 7 else 0)
        return {"company": {"id": company.id, "name": company.name, "demo": company.campus_demo},
                "today": str(fields.Date.context_today(self)), "snapshotDate": str(fields.Date.context_today(self)),
                "years": years or [current], "currentYear": current if current in years or not years else years[0], "unassigned_count": unassigned,
                "departments": [{"id": str(department.id), "code": department.code or department.name, "name": department.name,
                                 "coordinator": department.placement_coordinator or "Not assigned"} for department in departments],
                "students": students, "drives": drive_rows, "offers": offers,
                "plans": [{"id": plan.id, "title": plan.name, "owner": plan.owner_label, "note": plan.note, "year": plan.graduation_year,
                           "dept": str(plan.department_id.id) if plan.department_id else "All", "kind": plan.kind,
                           "student_id": str(plan.student_id.id) if plan.student_id else "", "status": dict(plan._fields["state"].selection)[plan.state]} for plan in plans],
                "can_reset_preview": self._preview_enabled()}

    @api.model
    def create_drive(self, values):
        self._check_owner()
        expected = {"company", "role", "date", "deadline", "salary", "cgpa", "dept", "mode", "location", "coordinator", "year", "request_key"}
        if not isinstance(values, dict) or set(values) != expected:
            raise ValidationError(_("Complete the placement drive form."))
        try:
            request_key = str(UUID(_text(values["request_key"], 36)))
        except ValueError as exc:
            raise ValidationError(_("Reopen the placement drive form and try again.")) from exc
        self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [self.env.company.id])
        if self._records("campus.placement.drive", [("owner_request_key", "=", request_key)]):
            return self.get_data()
        company_name = _text(values["company"], 60)
        role, location, coordinator = _text(values["role"], 80), _text(values["location"], 60), _text(values["coordinator"], 60)
        salary, cgpa = _number(values["salary"], 1, 200), _number(values["cgpa"], 0, 10)
        year = _number(values["year"], 1900, 2200)
        if int(year) != year:
            raise ValidationError(_("Choose a whole graduating year."))
        try:
            drive_date, deadline = fields.Date.to_date(values["date"]), fields.Date.to_date(values["deadline"])
            department_ids = {int(value) for value in _text(values["dept"], 2000).split(",")}
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose valid drive dates and departments.")) from exc
        if not drive_date or not deadline or deadline > drive_date or deadline < fields.Date.context_today(self):
            raise ValidationError(_("The application deadline must be today or later and on or before the drive date."))
        departments = self._records("op.department", [("id", "in", list(department_ids)), ("active", "=", True)])
        if set(departments.ids) != department_ids:
            raise AccessError(_("Choose departments from the currently selected college."))
        courses = self._records("op.course", [("department_id", "in", departments.ids), ("active", "=", True)])
        if set(courses.department_id.ids) != department_ids:
            raise ValidationError(_("Each eligible department needs at least one academic programme."))
        mode = {label: key for key, label in MODES}.get(values["mode"])
        if not mode:
            raise ValidationError(_("Choose a valid placement mode."))
        partner = self.env["res.partner"].search([("is_company", "=", True), ("name", "=ilike", company_name), ("company_id", "in", [False, self.env.company.id])], limit=1)
        if not partner:
            partner = partner.create({"name": company_name, "is_company": True, "company_id": self.env.company.id})
        timezone = pytz.timezone(self.env.user.tz or "Asia/Kolkata")
        interview = timezone.localize(datetime.combine(drive_date, time(10))).astimezone(pytz.utc).replace(tzinfo=None)
        drive = self.env["campus.placement.drive"].with_context(mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True).create({"name": role, "recruiter_id": partner.id, "company_id": self.env.company.id,
            "interview_on": interview, "application_deadline": deadline, "expected_ctc_lpa": salary, "minimum_cgpa": cgpa,
            "course_ids": [(6, 0, courses.ids)], "graduation_year": int(year), "placement_mode": mode, "location": location,
            "coordinator_name": coordinator, "portal_published": True, "job_description": role,
            "recruitment_process": "Registration → aptitude assessment → technical interview → HR interview → offer decision",
            "owner_preview_added": self._preview_enabled(), "owner_request_key": request_key})
        drive.action_submit()
        drive.action_approve()
        return self.get_data()

    @api.model
    def save_plan(self, values):
        self._check_owner()
        if not isinstance(values, dict) or set(values) - {"kind", "year", "dept", "student_id"}:
            raise ValidationError(_("Choose a placement insight or student to follow up."))
        kind = values.get("kind")
        if kind not in {"skills", "outreach", "resume", "student"}:
            raise ValidationError(_("Choose a valid improvement plan."))
        data = self.get_data()
        year = _number(values.get("year"), 1900, 2200)
        department = str(values.get("dept", "All"))
        if int(year) != year or year not in data["years"] or department != "All" and department not in {row["id"] for row in data["departments"]}:
            raise AccessError(_("Choose a graduating batch and department from this college."))
        pool = [row for row in data["students"] if row["year"] == year and (department == "All" or row["dept"] == department)]
        affected = [row for row in pool if row["willing"] and not row["placed"]]
        student_id = False
        if kind == "student":
            affected = [row for row in affected if row["id"] == str(values.get("student_id"))]
            if not affected:
                raise AccessError(_("Choose a willing, unplaced student from the selected cohort."))
            student_id = int(affected[0]["id"])
            title, owner, note = f"Student {affected[0]['register']}", "Placement mentor", "Individual readiness follow-up"
        elif kind == "skills":
            affected = [row for row in affected if row["eligible"] and any(row[key] is not None and row[key] < 70 for key in ("aptitude", "coding"))]
            title, owner, note = "Close the interview-readiness gap", "Training & Placement Officer", "Four-week placement improvement review"
        elif kind == "resume":
            affected = [row for row in affected if not row["resume"]]
            title, owner, note = "Make every profile application-ready", "Career Development Cell", "Four-week placement improvement review"
        else:
            options = [row for row in data["departments"] if department == "All" or row["id"] == department]
            def rate(dep):
                eligible = [row for row in pool if row["dept"] == dep["id"] and row["eligible"] and row["willing"]]
                placed = sum(row["placed"] for row in eligible)
                return placed / len(eligible) if eligible else 0
            lowest = min(options, key=rate) if options else None
            if not lowest:
                raise ValidationError(_("Add a department before planning recruiter outreach."))
            affected = [row for row in affected if row["eligible"] and row["dept"] == lowest["id"]]
            title, owner, note = f"Strengthen {lowest['code']} recruiter outreach", lowest["code"] + " Placement Coordinator", "Four-week placement improvement review"
        self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [self.env.company.id])
        key = f"{kind}:{int(year)}:{department if department != 'All' else 0}:{student_id or 0}"
        if self._records("campus.placement.improvement.plan", [("plan_key", "=", key)]):
            raise ValidationError(_("This improvement plan is already saved for the selected cohort."))
        self.env["campus.placement.improvement.plan"].with_context(mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True).create({"name": title, "company_id": self.env.company.id,
            "kind": kind, "graduation_year": int(year), "department_id": int(department) if department != "All" else False,
            "student_id": student_id, "student_ids": [(6, 0, [int(row["id"]) for row in affected])],
            "owner_label": owner, "note": note, "owner_preview_added": self._preview_enabled()})
        return self.get_data()

    @api.model
    def reset_preview(self):
        self._check_owner()
        if not self._preview_enabled():
            raise AccessError(_("Sample reset is available only in the isolated placement preview."))
        self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", [self.env.company.id])
        drives = self._records("campus.placement.drive", [("owner_preview_added", "=", True), ("active", "=", True)])
        # Keep any application history; reset only archives preview-added opportunities.
        drives._set_system_values({"active": False, "state": "cancelled"})
        self._records("campus.placement.improvement.plan", [("owner_preview_added", "=", True)]).unlink()
        return self.get_data()


class StudentPlacementOutcome(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _placement_application_row(self, application, now):
        row = super()._placement_application_row(application, now)
        if application.state == "selected":
            if application.offer_decision != "pending":
                label = dict(application._fields["offer_decision"].selection)[application.offer_decision]
                row["timeline"].append({"title": "Offer " + label.lower(), "text": self._dates(application.offer_accepted_on), "tone": "done"})
                row["status"] = "Offer " + label.lower()
            if application.joined_on:
                row["timeline"].append({"title": "Joining confirmed", "text": self._dates(application.joined_on), "tone": "done"})
                row["status"] = "Joined"
        return row
