import base64
import binascii
from collections import Counter
from datetime import timedelta
from urllib.parse import quote

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

from .late_punch import late_punch_dates

PAGES = [("myprofile", "My staff profile"), ("qualifications", "Staff qualifications and documents"),
         ("development", "Faculty development and appraisal"), ("agreements", "Salary agreements"),
         ("monthly", "Monthly payroll"), ("history", "Payroll History"), ("leave", "Leave requests")]
HOD_LABELS = {
    "myprofile": "HOD Profile", "qualifications": "Qualifications & Documents",
    "development": "Development & Appraisal", "agreements": "Salary Agreement",
    "monthly": "Monthly Payroll", "leave": "Leave Requests",
}
AGREEMENT_AMOUNTS = ("basic", "allowance", "fixed_deduction", "tds")
PAYSLIP_AMOUNTS = ("gross", "pf", "esi", "tds", "deductions", "net", "late_deduction")


def profile_items(env, labels=None):
    return [{
        "label": (labels or {}).get(key, label),
        "action": "ideastone_erp.action_faculty_profile_" + key,
        "action_id": env.ref("ideastone_erp.action_faculty_profile_" + key).id,
    } for key, label in PAGES]


class FacultyProfileNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if data.get("faculty_modules") and not any(data.get(k) for k in ("is_owner_workspace", "is_admin", "is_hod", "is_coe_workspace")):
            data["faculty_profile_enabled"] = True
            staff = next((m for m in data["faculty_modules"] if m["key"] == "staff"), None)
            if staff:
                staff["items"] = profile_items(self.env)
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

    def _hod_department(self):
        user = self.env.user
        department = user.dept_id.sudo()
        return department if user.has_group("ideastone_erp.group_mvp_hod") and department.company_id == self.env.company else department.browse()

    def _hod_staff(self, department):
        return self.env["op.faculty"].sudo().search([
            ("main_department_id", "=", department.id), ("company_id", "=", self.env.company.id),
        ], order="name, id")

    def _hod_employees(self, department):
        staff = self._hod_staff(department)
        return self.env["hr.employee"].sudo().search([
            ("company_id", "=", self.env.company.id), ("leave_manager_id", "=", self.env.uid),
            ("user_id", "!=", self.env.uid),
            "|", ("id", "in", staff.emp_id.ids), ("user_id", "in", staff.user_id.ids),
        ])

    def _hod_leave(self, department, today):
        employees = self._hod_employees(department)
        leaves = self.env["hr.leave"].search([
            ("company_id", "=", self.env.company.id), ("employee_id", "in", employees.ids), ("holiday_type", "=", "employee"),
        ], order="request_date_from desc, id desc", limit=100)
        reviewed = leaves.filtered(lambda row: row.state in ("validate", "refuse"))
        approved = reviewed.filtered(lambda row: row.state == "validate")
        types = Counter(leave.holiday_status_id.name for leave in approved)
        states = dict(leaves._fields["state"].selection)
        exceptions = [{"staff": employee.name, "date": str(day), "day": day.strftime("%a")}
                      for employee in employees for day in late_punch_dates(self.sudo().env, employee, today.replace(day=1))]
        return {
            "requests": [{
                "id": leave.id, "staff": leave.employee_id.name, "type": leave.holiday_status_id.name,
                "from": str(leave.request_date_from), "to": str(leave.request_date_to),
                "days": leave.number_of_days_display, "reason": leave.name or "",
                "status": states.get(leave.state, leave.state),
                "can_review": leave.state == "confirm" and leave.validation_type in ("manager", "both") and leave.can_approve,
            } for leave in leaves],
            "approved": len(approved), "pending": len(leaves.filtered(lambda row: row.state in ("confirm", "validate1"))),
            "approval_percent": round(100 * len(approved) / len(reviewed)) if reviewed else None,
            "most_common": types.most_common(1)[0][0] if types else _("No approved requests"),
            "exceptions": sorted(exceptions, key=lambda row: (row["date"], row["staff"]), reverse=True),
        }

    @api.model
    def review_hod_leave(self, leave_id, decision):
        department = self._hod_department()
        if not department or type(leave_id) is not int or decision not in ("approve", "refuse"):
            raise AccessError(_("Choose a request assigned to your department for review."))
        domain = [
            ("id", "=", leave_id), ("company_id", "=", self.env.company.id),
            ("employee_id", "in", self._hod_employees(department).ids),
            ("employee_id.leave_manager_id", "=", self.env.uid), ("holiday_type", "=", "employee"),
            ("state", "=", "confirm"), ("validation_type", "in", ["manager", "both"]),
        ]
        leave = self.env["hr.leave"].search(domain)
        if leave:
            self.env.cr.execute("SELECT id FROM hr_leave WHERE id=%s FOR UPDATE", [leave.id])
            leave.invalidate_recordset()
            leave = leave.search(domain)
        if not leave or not leave.can_approve:
            raise AccessError(_("This request is no longer assigned to you for approval."))
        return leave.action_approve() if decision == "approve" else leave.action_refuse()

    @api.model
    def get_workspace(self, page=None):
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
        department = self._hod_department()
        hod = {"department": department.name, "labels": HOD_LABELS} if department else None
        if department and page in ("qualifications", "development"):
            staff = self._hod_staff(department)
            peers = [("faculty_id", "in", (staff - faculty.sudo()).ids), ("company_id", "=", self.env.company.id)]
            if page == "qualifications":
                documents += [{
                    "id": row.id, "name": _("Identity document") if row.campus_category == "identity" else row.name,
                    "kind": row.kind, "campus_category": row.campus_category, "campus_expiry_date": row.campus_expiry_date,
                    "verification": row.verification, "create_date": row.create_date, "faculty": row.faculty_id.name, "peer": True,
                } for row in detail.sudo().search(peers, order="create_date desc, id desc", limit=1000)]
            else:
                hod["staff"] = [{"id": member.id, "name": member.name} for member in staff]
                hod["activities"] = activities.sudo().search(peers + [("state", "in", ["submitted", "approved", "done"])],
                    order="date_from desc, id desc", limit=1000).read(
                        ["name", "kind", "date_from", "state", "campus_hours", "faculty_id", "filename"])
                for row in hod["activities"]:
                    row["has_evidence"] = bool(row.pop("filename"))
        if department and page == "leave":
            hod["leave"] = self._hod_leave(department, today)
        for row in documents:
            expiry = fields.Date.to_date(row["campus_expiry_date"])
            row["status"] = "Expiring soon" if expiry and today <= expiry <= today + timedelta(days=30) else "Expired" if expiry and expiry < today else dict(detail._fields["verification"].selection)[row["verification"]]
        employee_domain = [("employee_id", "=", employee.id), ("company_id", "=", self.env.company.id), ("state", "in", ["approved", "done"])]
        payroll_page = not department or page in (None, "agreements", "monthly", "history")
        # Salary terms have no faculty model ACL. Expose only this linked employee's approved, non-bank fields.
        agreements = self.env["campus.salary.agreement"].sudo().search(employee_domain, order="date_from desc, id desc", limit=100) if employee and payroll_page else self.env["campus.salary.agreement"]
        agreement_rows = agreements.read(["name", "date_from", "date_to", "basic", "allowance", "fixed_deduction", "tds", "state", "approved_by", "approved_on"]) if agreements else []
        slips = self.env["campus.payslip"].search(employee_domain, order="date_from desc, id desc", limit=500) if employee and payroll_page else self.env["campus.payslip"]
        payroll = slips.read(["name", "date_from", "date_to", "agreement_id", "gross", "pf", "esi", "tds", "deductions", "net", "late_days", "late_grace_days", "late_deducted_days", "late_deduction", "state", "payment_reference"])
        currency = self.env.ref("base.INR") if department else self.env.company.currency_id
        if department:
            for row, agreement in zip(agreement_rows, agreements, strict=True):
                row.update(self._inr_amounts(agreement, AGREEMENT_AMOUNTS, agreement.date_from))
        for row, slip in zip(payroll, slips, strict=True):
            terms = slip.agreement_id.sudo()
            if department:
                row.update(self._inr_amounts(slip, PAYSLIP_AMOUNTS, slip.date_to))
                row.update(self._inr_amounts(terms, ("basic", "allowance"), slip.date_to))
            else:
                row.update(basic=terms.basic, allowance=terms.allowance)
        return {"profile": profile, "company": self.env.company.name, "demo": self.env.company.campus_demo, "today": today, "hod": hod,
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
        if self._hod_department():
            faculty.check_access_rights("write")
            faculty.check_access_rule("write")
            faculty = faculty.sudo()
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
        records = self.env[model]
        if self._hod_department():
            # The HOD reporting guard applies to generic ERP writes. These actions
            # have already restricted the fields and resolved the caller's own record.
            records.check_access_rights("write" if record else "create")
            record.check_access_rule("write")
            record, records = record.sudo(), records.sudo()
        if record:
            record.write(values)
        else:
            record = records.create(dict(values, faculty_id=faculty.id, company_id=self.env.company.id))
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
                if self._hod_department():
                    rec.check_access_rights("write")
                    rec.check_access_rule("write")
                    rec = rec.sudo()
                rec.action_submit()
                return True
            field = "document" if kind == "document" else "evidence"
            if not rec[field]:
                raise ValidationError(_("No supporting file is attached to this record."))
            return {"type": "ir.actions.act_url", "url": f"/web/content/{model}/{rec.id}/{field}/{quote(rec.filename or 'document', safe='')}?download=true", "target": "new"}
        if kind == "payslip":
            slip = self._own_payslips([record_id])
            report = "report_hod_payslip" if self._hod_department() else "report_payslip"
            return self.env.ref("ideastone_erp." + report).report_action(slip)
        if kind == "agreement":
            agreement = self._own_agreements([record_id])
            return self.env.ref("ideastone_erp.report_hod_salary_agreement").report_action(agreement)
        if kind == "agreement_review":
            agreement = self._own_agreements([record_id])
            reviewer = agreement.approved_by
            if not reviewer.active or reviewer.id == self.env.uid or self.env.company not in reviewer.company_ids:
                raise ValidationError(_("No salary approver is available. Contact HR to request a review."))
            agreement._lock()
            activity_type = self.env.ref("mail.mail_activity_data_todo")
            summary = _("Salary agreement review requested")
            if not agreement.activity_ids.filtered(lambda row: row.user_id == reviewer and row.summary == summary):
                agreement.activity_schedule(activity_type_id=activity_type.id, user_id=reviewer.id, summary=summary)
            return True
        raise ValidationError(_("Choose a valid staff action."))

    def _own_agreements(self, ids):
        if not self._hod_department():
            raise AccessError(_("An assigned HOD department is required."))
        employee = self.env["campus.faculty.leave.ui"]._employee()
        agreements = self.env["campus.salary.agreement"].sudo().search([
            ("id", "in", ids), ("employee_id", "=", employee.id),
            ("company_id", "=", self.env.company.id), ("state", "in", ["approved", "done"]),
        ])
        if not employee or not ids or set(agreements.ids) != set(ids):
            raise AccessError(_("This approved salary agreement is outside your account."))
        return agreements

    def _own_payslips(self, ids):
        employee = self.env["campus.faculty.leave.ui"]._employee()
        slips = self.env["campus.payslip"].search([
            ("id", "in", ids), ("employee_id", "=", employee.id),
            ("company_id", "=", self.env.company.id), ("state", "in", ["approved", "done"]),
        ])
        if not employee or not ids or set(slips.ids) != set(ids):
            raise AccessError(_("This approved payslip is outside your account."))
        return slips

    def _inr_amounts(self, record, keys, day):
        currency = self.env.ref("base.INR")
        source = record.currency_id
        company = self.env.company
        if source == currency:
            return {key: record[key] for key in keys}
        for item in (source | currency) - company.currency_id:
            if not self.env["res.currency.rate"].sudo().search_count([
                ("currency_id", "=", item.id), ("company_id", "in", [False, company.root_id.id]),
                ("name", "<=", day),
            ], limit=1):
                raise ValidationError(_("Configure a %s exchange rate for %s to view this record in rupees.", item.name, day))
        rate = source._get_conversion_rate(source, currency, company, day)
        return {key: currency.round(record[key] * rate) for key in keys}


class HodSalaryAgreementReport(models.AbstractModel):
    _name = "report.ideastone_erp.hod_salary_agreement"
    _description = "Approved HOD salary agreement summary"

    @api.model
    def _get_report_values(self, docids, data=None):
        workspace = self.env["campus.faculty.workspace"]
        agreements = workspace._own_agreements(docids)
        return {"doc_ids": agreements.ids, "doc_model": agreements._name, "docs": agreements,
            "rupees": self.env.ref("base.INR"),
            "hod_amounts": {row.id: workspace._inr_amounts(row, AGREEMENT_AMOUNTS, row.date_from) for row in agreements}}


class HodPayslipReport(models.AbstractModel):
    _name = "report.ideastone_erp.hod_payslip_document"
    _description = "HOD payslip in rupees"

    @api.model
    def _get_report_values(self, docids, data=None):
        workspace = self.env["campus.faculty.workspace"]
        if not workspace._hod_department():
            raise AccessError(_("An assigned HOD department is required."))
        slips = workspace._own_payslips(docids)
        return {"doc_ids": slips.ids, "doc_model": slips._name, "docs": slips,
            "rupees": self.env.ref("base.INR"),
            "hod_amounts": {row.id: workspace._inr_amounts(row, PAYSLIP_AMOUNTS, row.date_to) for row in slips}}
