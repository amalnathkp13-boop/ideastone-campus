import base64
import binascii
from datetime import timedelta
from urllib.parse import quote

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

PAGES = [("myprofile", "My staff profile"), ("qualifications", "Staff qualifications and documents"),
         ("development", "Faculty development and appraisal"), ("agreements", "Salary agreements"),
         ("monthly", "Monthly payroll"), ("history", "Payroll History"), ("leave", "Leave requests")]


class FacultyProfileNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if data.get("faculty_modules") and not any(data.get(k) for k in ("is_owner_workspace", "is_admin", "is_hod", "is_coe_workspace")):
            data["faculty_profile_enabled"] = True
            staff = next((m for m in data["faculty_modules"] if m["key"] == "staff"), None)
            if staff:
                staff["items"] = [{"label": label, "action": "ideastone_erp.action_faculty_profile_" + key,
                                   "action_id": self.env.ref("ideastone_erp.action_faculty_profile_" + key).id} for key, label in PAGES]
        return data


class FacultyProfileFields(models.Model):
    _inherit = "op.faculty"

    campus_profile_review_date = fields.Date("Next profile review")


class FacultyDocumentFields(models.Model):
    _inherit = "campus.faculty.detail"

    campus_category = fields.Selection([(key, label) for key, label in [
        ("academic", "Academic"), ("identity", "Identity"), ("professional", "Professional development"), ("membership", "Membership")]], default="academic")
    campus_expiry_date = fields.Date("Valid until")


class FacultyActivityFields(models.Model):
    _inherit = "campus.faculty.achievement"

    campus_hours = fields.Float("Development hours")

    @api.constrains("campus_hours")
    def _check_development_hours(self):
        if any(not 0 <= r.campus_hours <= 10000 for r in self):
            raise ValidationError(_("Enter development hours between 0 and 10,000."))


class FacultyProfileWorkspace(models.AbstractModel):
    _name = "campus.faculty.workspace"
    _description = "Own faculty profile, documents, development and payroll"

    def _faculty(self):
        record = self.env["campus.question.paper"]._faculty()
        faculty = self.env["op.faculty"].browse(record.id)
        faculty.check_access_rights("read")
        faculty.check_access_rule("read")
        return faculty

    def _records(self, model, faculty):
        return self.env[model].search([("faculty_id", "=", faculty.id), ("company_id", "=", self.env.company.id)], order="create_date desc, id desc", limit=1000)

    @api.model
    def get_workspace(self):
        faculty = self._faculty()
        employee = self.env["campus.faculty.leave.ui"]._employee()
        today = fields.Date.context_today(self)
        detail = self._records("campus.faculty.detail", faculty)
        activities = self._records("campus.faculty.achievement", faculty)
        profile_fields = ["name", "email", "mobile", "birth_date", "gender", "campus_staff_code", "campus_designation", "main_department_id",
            "campus_service_type", "campus_joining_date", "campus_reporting_id", "campus_emergency_phone", "campus_communication_address", "campus_profile_review_date"]
        profile = faculty.read(profile_fields)[0]
        completion = [profile[k] for k in profile_fields if k not in {"name", "campus_profile_review_date"}]
        profile.update(completion=round(100 * sum(bool(v) for v in completion) / len(completion)), missing=sum(not v for v in completion),
            tenure=round((today - faculty.campus_joining_date).days / 365.25, 1) if faculty.campus_joining_date else None)
        documents = detail.read(["name", "kind", "campus_category", "campus_expiry_date", "verification", "filename", "create_date", "next_action", "institution", "year"])
        for row in documents:
            expiry = fields.Date.to_date(row["campus_expiry_date"])
            row["status"] = "Expiring soon" if expiry and today <= expiry <= today + timedelta(days=30) else "Expired" if expiry and expiry < today else dict(detail._fields["verification"].selection)[row["verification"]]
        employee_domain = [("employee_id", "=", employee.id), ("company_id", "=", self.env.company.id), ("state", "in", ["approved", "done"])]
        # Salary terms have no faculty model ACL. Expose only this linked employee's approved, non-bank fields.
        agreements = self.env["campus.salary.agreement"].sudo().search(employee_domain, order="date_from desc, id desc", limit=100) if employee else self.env["campus.salary.agreement"]
        agreement_rows = agreements.read(["name", "date_from", "date_to", "basic", "allowance", "fixed_deduction", "tds", "state", "approved_by", "approved_on"]) if agreements else []
        slips = self.env["campus.payslip"].search(employee_domain, order="date_from desc, id desc", limit=500) if employee else self.env["campus.payslip"]
        payroll = slips.read(["name", "date_from", "date_to", "agreement_id", "gross", "pf", "esi", "tds", "deductions", "net", "late_days", "late_grace_days", "late_deducted_days", "late_deduction", "state", "payment_reference"])
        for row, slip in zip(payroll, slips, strict=True):
            terms = slip.agreement_id.sudo()
            row.update(basic=terms.basic, allowance=terms.allowance)
        currency = self.env.company.currency_id
        return {"profile": profile, "company": self.env.company.name, "demo": self.env.company.campus_demo, "today": today,
            "documents": documents, "activities": activities.read(["name", "kind", "date_from", "date_to", "description", "filename", "state", "campus_hours"]),
            "kinds": [{"id": key, "name": label} for key, label in activities._fields["kind"].selection],
            "agreements": agreement_rows, "payroll": payroll, "leave": self.env["campus.faculty.leave.ui"].get_page_data(),
            "currency": currency.name, "currency_symbol": currency.symbol}

    @api.model
    def save_profile(self, values):
        faculty = self._faculty()
        allowed = {"email", "mobile", "campus_emergency_phone", "campus_communication_address"}
        if not isinstance(values, dict) or not values or set(values) - allowed or any(not isinstance(v, str) or len(v) > 2000 for v in values.values()):
            raise ValidationError(_("Update only your contact details using valid text."))
        faculty.write({key: value.strip() for key, value in values.items()})
        return True

    def _file(self, values, field):
        if not values.get(field):
            return
        if not isinstance(values[field], str) or len(values[field]) > 14 * 1024 * 1024:
            raise ValidationError(_("Use a file up to 10 MB."))
        try:
            raw = base64.b64decode(values[field], validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise ValidationError(_("Choose a valid PDF, PNG or JPEG file.")) from exc
        if not raw or len(raw) > 10 * 1024 * 1024 or not raw.startswith((b"%PDF-", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            raise ValidationError(_("Use a PDF, PNG or JPEG file up to 10 MB."))
        filename = values.get("filename")
        if not isinstance(filename, str) or not 1 <= len(filename) <= 200 or "/" in filename or "\\" in filename:
            raise ValidationError(_("Choose a valid file name."))

    @api.model
    def save_record(self, kind, values, record_id=0):
        faculty = self._faculty()
        configs = {"document": ("campus.faculty.detail", {"name", "kind", "campus_category", "campus_expiry_date", "institution", "year", "document", "filename"}, "document"),
                   "activity": ("campus.faculty.achievement", {"name", "kind", "date_from", "date_to", "description", "campus_hours", "evidence", "filename"}, "evidence")}
        if not isinstance(kind, str) or kind not in configs or type(record_id) is not int or record_id < 0 or not isinstance(values, dict):
            raise ValidationError(_("Choose a valid own staff record."))
        model, allowed, binary = configs[kind]
        if not values or set(values) - allowed or not isinstance(values.get("name"), str) or not 1 <= len(values["name"].strip()) <= 250:
            raise ValidationError(_("Enter a name and only the supported staff record fields."))
        self._file(values, binary)
        for key, value in values.items():
            if key not in {binary, "year", "campus_hours"} and value is not False and (not isinstance(value, str) or len(value) > 5000):
                raise ValidationError(_("Enter valid staff record details."))
        if "campus_hours" in values and (type(values["campus_hours"]) not in (int, float) or not 0 <= values["campus_hours"] <= 10000):
            raise ValidationError(_("Enter valid development hours."))
        if "year" in values and type(values["year"]) is not int:
            raise ValidationError(_("Enter a valid qualification year."))
        record = self._records(model, faculty).filtered(lambda r: r.id == record_id) if record_id else self.env[model]
        if record_id and not record:
            raise AccessError(_("This record is outside your faculty account and active college."))
        if kind == "activity" and record and record.state != "draft":
            raise ValidationError(_("Only draft activities can be edited. Submitted evidence must be reviewed through the approval workflow."))
        if record:
            record.write(values)
        else:
            record = self.env[model].create(dict(values, faculty_id=faculty.id, company_id=self.env.company.id))
        return record.id

    @api.model
    def record_action(self, kind, record_id):
        faculty = self._faculty()
        if type(record_id) is not int or record_id <= 0 or not isinstance(kind, str):
            raise ValidationError(_("Choose a valid own record."))
        if kind in {"document", "activity", "submit"}:
            model = "campus.faculty.detail" if kind == "document" else "campus.faculty.achievement"
            rec = self._records(model, faculty).filtered(lambda r: r.id == record_id)
            if not rec:
                raise AccessError(_("This record is outside your faculty account."))
            if kind == "submit":
                rec.action_submit()
                return True
            field = "document" if kind == "document" else "evidence"
            if not rec[field]:
                raise ValidationError(_("No supporting file is attached to this record."))
            return {"type": "ir.actions.act_url", "url": f"/web/content/{model}/{rec.id}/{field}/{quote(rec.filename or 'document', safe='')}?download=true", "target": "new"}
        if kind == "payslip":
            employee = self.env["campus.faculty.leave.ui"]._employee()
            slip = self.env["campus.payslip"].search([("id", "=", record_id), ("employee_id", "=", employee.id),
                ("company_id", "=", self.env.company.id), ("state", "in", ["approved", "done"])])
            if not slip:
                raise AccessError(_("This approved payslip is outside your account."))
            return self.env.ref("ideastone_erp.report_payslip").report_action(slip)
        raise ValidationError(_("Choose a valid staff action."))
