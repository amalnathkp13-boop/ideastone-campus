from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext, plaintext2html

from odoo import _, api, fields, models

FEE_CATEGORIES = [("fees", "Fees"), ("exam", "Examination"), ("event", "Event"), ("general", "General")]
FEE_AUDIENCES = {"student": "Students", "student_parent": "Students & guardians", "faculty": "Staff",
                 "parent": "Guardians", "all": "Everyone"}


class FeeCircular(models.Model):
    _inherit = "campus.circular"

    audience = fields.Selection(selection_add=[("student_parent", "Students & guardians")],
                                ondelete={"student_parent": "set default"})
    fee_notice_category = fields.Selection(FEE_CATEGORIES, default="fees", required=True, string="Fee circular category")
    fee_department_id = fields.Many2one("op.department", string="Fee circular department", check_company=True)
    fee_academic_scope = fields.Char(string="Academic year / semester")

    @api.constrains("fee_department_id", "audience", "campus_group_id")
    def _check_fee_scope(self):
        for rec in self.filtered(lambda n: n.campus_managed and n.campus_category == "Fees"):
            if rec.fee_department_id and rec.audience == "faculty":
                raise ValidationError(_("Use All departments or Accounts office for staff fee circulars."))
            if rec.campus_group_id and rec.campus_group_id == self.env.ref("ideastone_erp.group_mvp_accountant") and rec.audience != "faculty":
                raise ValidationError(_("Accounts office scope requires the Staff audience."))


class FeeCircularWorkspace(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _client_action_models(self):
        return dict(super()._client_action_models(), action_accountant_fee_circulars="campus.circular")

    def _fee_notice(self, record_id):
        self._accountant_access()
        try:
            record_id = int(record_id)
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose a valid fee circular.")) from exc
        record = self.env["campus.circular"].with_context(active_test=False).search([
            ("id", "=", record_id), ("company_id", "=", self.env.company.id),
            ("campus_managed", "=", True), ("campus_category", "=", "Fees")], limit=1)
        if not record:
            raise AccessError(_("This fee circular is outside the active college."))
        return record

    @api.model
    def get_fee_circulars(self):
        self._accountant_access()
        today = fields.Date.context_today(self)
        notices = self.with_context(active_test=False)._mvp_records("campus.circular", [
            ("company_id", "=", self.env.company.id), ("campus_managed", "=", True), ("campus_category", "=", "Fees")])
        notices = notices.sorted(lambda rec: (rec.date_from, rec.id), reverse=True)
        departments = self.env["op.department"].search(["|", ("company_id", "=", False),
            ("company_id", "=", self.env.company.id)], order="name")
        year = self.env["op.academic.year"].search([("company_id", "=", self.env.company.id),
            ("start_date", "<=", today), ("end_date", ">=", today)], limit=1)
        first, last = (year.start_date, year.end_date) if year else (today.replace(month=1, day=1), today.replace(month=12, day=31))
        period = notices.filtered(lambda rec: first <= rec.date_from <= last)
        # Aggregate only acknowledgements belonging to permission-checked fee circulars.
        read_counts = {}
        for key, model in [("students", "campus.student.notice.read"), ("parents", "campus.parent.notice.read")]:
            grouped = self.env[model].sudo().read_group([("notice_id", "in", notices.ids)], ["notice_id"], ["notice_id"])
            read_counts[key] = {row["notice_id"][0]: row["notice_id_count"] for row in grouped}
        rows = []
        for rec in notices:
            local_publish = fields.Datetime.context_timestamp(self, rec.communication_publish_at) if rec.communication_publish_at else False
            actual = fields.Datetime.context_timestamp(self, rec.approved_on) if rec.approved_on else False
            publish = (local_publish.date() if local_publish else rec.date_from) if rec.campus_status == "scheduled" else (
                actual.date() if actual and rec.campus_status != "draft" else False)
            office = rec.campus_group_id == self.env.ref("ideastone_erp.group_mvp_accountant")
            body = html2plaintext(rec.body or "")
            rows.append({"id": rec.id, "name": rec.name, "reference": rec.reference, "body": body, "summary": body[:100],
                "category": rec.fee_notice_category, "category_label": dict(FEE_CATEGORIES)[rec.fee_notice_category],
                "audience": rec.audience, "audience_label": FEE_AUDIENCES.get(rec.audience, rec.audience),
                "scope": "accounts" if office else str(rec.fee_department_id.id) if rec.fee_department_id else "all",
                "scope_label": "Accounts office" if office else rec.fee_department_id.name or "All departments",
                "academic_scope": rec.fee_academic_scope or "", "effective_from": str(rec.date_from),
                "due_date": str(rec.date_to) if rec.date_to else "", "publish_date": str(publish) if publish else "",
                "publish_at": local_publish.strftime("%Y-%m-%dT%H:%M") if local_publish else "",
                "status": rec.campus_status, "updated": rec.write_date.isoformat(),
                "student_reads": read_counts["students"].get(rec.id, 0), "parent_reads": read_counts["parents"].get(rec.id, 0)})
        return {"today": str(today), "timezone": self.env.user.tz or "UTC", "year": year.name or str(today.year),
                "departments": [{"id": d.id, "name": d.name} for d in departments], "rows": rows,
                "counts": {"total": len(period), **{status: len(period.filtered(lambda rec, status=status: rec.campus_status == status))
                    for status in ("published", "scheduled", "draft", "archived")}}}

    @api.model
    def save_fee_circular(self, values, record_id=False):
        self._accountant_access()
        if not isinstance(values, dict):
            raise ValidationError(_("Enter valid circular details."))
        name = str(values.get("name") or "").strip()
        body = str(values.get("body") or "").strip()
        reference = str(values.get("reference") or "").strip()
        academic_scope = str(values.get("academic_scope") or "").strip()
        category = values.get("category", "fees")
        audience = values.get("audience", "student")
        status = values.get("status", "draft")
        if not name or not body or len(name) > 200 or len(body) > 20000 or len(reference) > 80 or len(academic_scope) > 160:
            raise ValidationError(_("Enter a circular name and message within the allowed lengths."))
        if category not in dict(FEE_CATEGORIES) or audience not in FEE_AUDIENCES or status not in {"draft", "scheduled", "published"}:
            raise ValidationError(_("Select a valid category, audience and publication state."))
        scope = str(values.get("scope") or "all")
        department = self.env["op.department"]
        if scope not in {"all", "accounts"}:
            try:
                department = department.search([("id", "=", int(scope)), "|", ("company_id", "=", False),
                                               ("company_id", "=", self.env.company.id)], limit=1)
            except (TypeError, ValueError) as exc:
                raise ValidationError(_("Select a valid department.")) from exc
            if not department:
                raise AccessError(_("Select a department in the active college."))
        if scope == "accounts" and audience != "faculty":
            raise ValidationError(_("Accounts office scope requires the Staff audience."))
        try:
            first = fields.Date.to_date(values.get("effective_from") or fields.Date.context_today(self))
            last = fields.Date.to_date(values.get("due_date")) if values.get("due_date") else False
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose valid effective and due dates.")) from exc
        if not first or last and last < first:
            raise ValidationError(_("The due date must be on or after the effective date."))
        planned = self.env["campus.owner.communication.ui"]._local_datetime(values.get("publish_at"))
        now = fields.Datetime.now()
        if status == "scheduled" and (not planned or planned <= now):
            raise ValidationError(_("Choose a future schedule date and time."))
        if planned:
            release_date = fields.Datetime.context_timestamp(self, planned).date()
            if release_date < first or last and release_date > last:
                raise ValidationError(_("The scheduled release must fall between the effective and due dates."))
        if status == "published" and (first > fields.Date.context_today(self) or planned and planned > now):
            raise ValidationError(_("Choose Scheduled for a future release."))
        vals = {"name": name, "body": plaintext2html(body),
            "campus_managed": True, "campus_category": "Fees", "fee_notice_category": category, "audience": audience,
            "fee_department_id": department.id or False, "fee_academic_scope": academic_scope,
            "campus_group_id": self.env.ref("ideastone_erp.group_mvp_accountant").id if scope == "accounts" else False,
            "date_from": first, "date_to": last, "communication_publish_at": planned or False}
        if record_id:
            rec = self._fee_notice(record_id)
            rec._lock()
            if rec.campus_status != "draft":
                raise ValidationError(_("Only draft circulars can be edited. Archive a released circular and create a new one for corrections."))
            if values.get("updated") != rec.write_date.isoformat():
                raise ValidationError(_("This circular changed in another session. Close and reopen it before saving."))
            if reference:
                vals["reference"] = reference
            rec.write(vals)
        else:
            vals.update(company_id=self.env.company.id, reference=reference or self.env["ir.sequence"].next_by_code("campus.fee.circular"))
            if not vals["reference"]:
                raise ValidationError(_("Configure fee circular numbering before creating a circular."))
            rec = self.env["campus.circular"].create(vals)
        if status != "draft":
            rec.action_campus_publish()
        return rec.id

    @api.model
    def archive_fee_circular(self, record_id):
        rec = self._fee_notice(record_id)
        rec.action_campus_archive()
        return True
