import base64
import csv
import io
from collections import defaultdict
from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval

from odoo import _, api, fields, models

ROLES = ("owner", "registrar", "admissions", "accountant", "exams", "readonly", "hod")
# Client (OWL) actions have no res_model; access is checked against the model they edit.
CLIENT_ACTION_MODELS = {
    "action_examinations_overview": "op.exam",
    "action_examinations_sessions": "op.exam.session",
    "action_examinations_marks": "op.exam",
    "action_examinations_grades": "op.grade.configuration",
    "action_examinations_results": "op.result.line",
    "action_examinations_papers": "op.exam",
    "action_admissions_overview": "op.admission",
    "action_admissions_enquiries": "crm.lead",
    "action_admissions_applications": "op.admission",
    "action_admissions_documents": "campus.admission.document",
    "action_admissions_register": "op.admission.register",
    "action_students_directory": "op.student",
    "action_students_enrolments": "op.student.course",
    "action_staff_profile": "campus.faculty.detail",
    "action_faculty_appraisal_dashboard": "campus.faculty.achievement",
    "action_staff_od_management": "op.faculty",
    "action_faculty_leave_page": "hr.leave",
    "action_faculty_attendance_page": "hr.attendance",
    "action_student_attendance_workspace": "op.attendance.sheet",
    "action_subject_attendance_workspace": "op.attendance.sheet",
    "action_payroll_history_page": "campus.payslip",
}

MODULES = [
    ("home", "Dashboard", "home", [("Overview", "owner-overview")]),
    ("admissions", "Admissions", "address-card-o", [("Enquiries", "mvp_enquiries"), ("Applications & review", "mvp_applications"), ("Documents", "mvp_documents"), ("Admission register", "mvp_intakes")]),
    ("students", "Students", "graduation-cap", [("Student directory", "mvp_students"), ("Enrolments & transfers", "mvp_enrolments")]),
    ("academics", "Academics", "university", [("Academic years", "mvp_years"), ("Departments", "mvp_departments"), ("Programmes", "mvp_programmes"), ("Semesters", "mvp_terms"), ("Sections", "mvp_sections"), ("Subjects & curriculum", "mvp_subjects")]),
    ("staff", "Faculty & Staff", "users", [("Staff directory", "mvp_faculty"), ("Teaching allocation", "mvp_timetable"), ("Staff Profile", "action_staff_profile"), ("Faculty development and appraisal", "action_faculty_appraisal_dashboard"), ("OD Management", "action_staff_od_management"), ("Leave Management", "action_faculty_leave_page"), ("Payroll History", "action_payroll_history_page")]),
    ("timetable", "Timetable", "calendar", [("Class timetable", "mvp_timetable"), ("Faculty timetable", "mvp_faculty_timetable"), ("Rooms", "mvp_rooms")]),
    ("attendance", "Attendance", "calendar-check-o", [("Staff attendance", "action_faculty_attendance_page"), ("Student Attendance", "action_student_attendance_workspace"), ("Take attendance", "mvp_attendance"), ("Attendance register", "mvp_attendance_registers"), ("Student summary & shortage", "mvp_report_attendance")]),
    ("fees", "Fees & Payments", "inr", [("Fee heads", "mvp_fee_heads"), ("Fee structures", "mvp_structures"), ("Student fee accounts", "mvp_fees"), ("Assign fee structure", "mvp_assign_fees"), ("Invoices & dues", "mvp_invoices"), ("Overdue follow-up", "mvp_overdue_invoices"), ("Receipts", "mvp_receipts")]),
    ("learning", "Learning & LMS", "book", [("Assignments", "mvp_learning_assignments"), ("Review submissions", "mvp_learning_submissions"), ("LMS accounts & retries", "mvp_lms_accounts")]),
    ("exams", "Examinations", "file-text-o", [("Exam sessions", "mvp_exam_sessions"), ("Schedule & marks entry", "mvp_exams"), ("Grade rules", "mvp_grades"), ("Results & missing entries", "mvp_results")]),
    ("communication", "Communication", "bullhorn", [("Notices & audiences", "mvp_notices"), ("Student requests & support", "mvp_student_requests")]),
    ("reports", "Reports", "bar-chart", [("Admissions", "mvp_report_admissions"), ("Students", "mvp_report_students"), ("Attendance", "mvp_report_attendance"), ("Fee collection", "mvp_report_collection"), ("Outstanding dues", "mvp_report_dues"), ("Results", "mvp_report_results"), ("Faculty workload", "mvp_report_faculty")]),
    ("settings", "Settings", "cog", [("College profile & attendance policy", "mvp_college"), ("Document requirements", "mvp_requirements"), ("Student request catalogue", "mvp_student_request_types"), ("Audit log", "mvp_audit"), ("Users & roles", "base.action_res_users"), ("ID & receipt numbering", "base.ir_sequence_form"), ("Import students", "mvp_import_students")]),
]


class OwnerDashboard(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _is_mvp_user(self):
        return any(self.env.user.has_group("ideastone_erp.group_mvp_" + role) for role in ROLES)

    def _owner_modules(self):
        """Owner workspace modules. Add-on modules extend this list."""
        return list(MODULES)

    def _client_action_models(self):
        """Access-check model for each client (OWL) action. Add-on modules extend this map."""
        return dict(CLIENT_ACTION_MODELS)

    @api.model
    def get_overview(self):
        if self.env.user.has_group("ideastone_erp.group_od_hod_approver") or not self._is_mvp_user():
            return super().get_overview()
        modules = []
        navigation = []
        client_models = self._client_action_models()
        for key, label, icon, entries in self._owner_modules():
            items = []
            for title, action in entries:
                if action == "owner-overview":
                    items.append({"label": title, "page": action})
                    continue
                ref = self.env.ref(action if "." in action else "ideastone_erp." + action, raise_if_not_found=False)
                if not ref:
                    continue
                # Read only these code-owned action definitions. Target records
                # continue to use the caller's ACLs and college record rules.
                ref = ref.sudo()
                if action in {"base.action_res_users", "base.ir_sequence_form"} and not self.env.user.has_group("ideastone_erp.group_mvp_owner"):
                    continue
                if action in {"mvp_college", "mvp_import_students", "mvp_requirements", "mvp_lms_accounts"} and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
                    continue
                report_model = {"mvp_report_admissions": "op.admission", "mvp_report_students": "op.student", "mvp_report_attendance": "op.attendance.line", "mvp_report_collection": "account.payment", "mvp_report_dues": "account.move", "mvp_report_results": "op.result.line", "mvp_report_faculty": "op.faculty"}.get(action)
                if report_model and not self.env[report_model].check_access_rights("read", raise_exception=False):
                    continue
                target_model = client_models.get(action) or ref.res_model
                if not self.env[target_model].check_access_rights("read", raise_exception=False):
                    continue
                item = {"label": title, "action": ref.get_external_id()[ref.id], "action_id": ref.id, "model": target_model, "group": label, "allowed": True}
                items.append(item)
                navigation.append(item)
            if items:
                modules.append({"key": key, "label": label, "icon": icon, "items": items})
        return {"company": self.env.company.name, "user": self.env.user.name, "today": str(fields.Date.context_today(self)),
                "is_admin": True, "is_owner_workspace": True, "is_demo": self.env.company.campus_demo,
                "workspace_role": "Owner / Admin" if self.env.user.has_group("ideastone_erp.group_mvp_registrar") else "College staff",
                "faculty_modules": modules, "navigation": navigation, "stats": [], "pages": [], "queues": [], "quick": [],
                "appointments": [], "faculty_tasks": [], "faculty_schedule": [], "faculty_surveys": [],
                "library_allowed": False, "report_allowed": True, "payroll_allowed": False}

    def _mvp_filters(self, filters=None):
        if not self._is_mvp_user():
            raise AccessError(_("College reporting permission is required."))
        if filters is None:
            filters = {}
        if not isinstance(filters, dict):
            raise ValidationError(_("Use valid college report filters."))
        today = fields.Date.context_today(self)
        id_keys = ["year_id", "course_id", "batch_id", "subject_id", "faculty_id", "student_id", "cashier_id", "source_id", "exam_id", "fee_head_id", "department_id"]
        try:
            start = fields.Date.to_date(filters.get("date_from") or today.replace(day=1))
            end = fields.Date.to_date(filters.get("date_to") or today)
            ids = {key: int(filters.get(key) or 0) for key in id_keys}
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValidationError(_("Select valid report dates and record filters.")) from exc
        if start > end or (end - start).days > 1096 or end == date.max:
            raise ValidationError(_("Select a valid reporting period of at most three years."))
        if any(value < 0 or value > 2147483647 or (filters.get(key) is True or not isinstance(filters.get(key), (str, int, type(None)))) for key, value in ids.items()):
            raise ValidationError(_("Select valid records for the report filters."))
        year_id = ids["year_id"]
        if year_id:
            year = self.env["op.academic.year"].browse(year_id).exists()
            year.check_access_rule("read")
            if not year or year.company_id != self.env.company:
                raise AccessError(_("Select an academic year in the active college."))
        return {"date_from": start, "date_to": end, **ids,
                "status": str(filters.get("status") or ""), "method": str(filters.get("method") or "")}

    def _mvp_records(self, model, domain, limit=50000):
        source = self.env[model]
        if not source.check_access_rights("read", raise_exception=False):
            return source
        if source.search_count(domain) > limit:
            raise ValidationError(_("Choose a shorter period or narrower programme filter (maximum 50,000 records)."))
        return source.search(domain, limit=limit)

    def _mvp_source(self, kind, f):
        company = [("company_id", "=", self.env.company.id)]
        def dates(field):
            return [(field, ">=", f["date_from"]), (field, "<", f["date_to"] + timedelta(days=1))]
        mapping = {
            "admissions": ("op.admission", company + dates("application_date") + [("campus_managed", "=", True)]),
            "students": ("op.student", company),
            "attendance": ("op.attendance.line", company + dates("attendance_date") + [("attendance_id.state", "=", "done"), "|", ("attendance_id.session_id", "=", False), ("attendance_id.session_id.state", "!=", "cancel")]),
            "collection": ("account.payment", company + [("campus_receipt_number", "!=", False), "|", "&", ("date", ">=", f["date_from"]), ("date", "<=", f["date_to"]), "&", ("campus_reversal_id.date", ">=", f["date_from"]), ("campus_reversal_id.date", "<=", f["date_to"])]),
            "dues": ("account.move", company + [("campus_student_id", "!=", False), ("state", "=", "posted"), ("move_type", "=", "out_invoice"), ("invoice_date", "<=", f["date_to"])]),
            "results": ("op.result.line", company + [("exam_id.campus_managed", "=", True)] + dates("exam_id.start_time")),
            "faculty": ("op.faculty", company + [("active", "=", True)]),
        }
        if kind not in mapping:
            raise ValidationError(_("Unknown college report."))
        model, domain = mapping[kind]
        year_paths = {"admissions": "campus_year_id", "attendance": "batch_id.campus_year_id",
                      "collection": "campus_invoice_id.campus_year_id", "dues": "campus_year_id", "results": "exam_id.campus_year_id"}
        course_paths = {"admissions": "course_id", "attendance": "course_id", "collection": "campus_invoice_id.campus_course_id", "dues": "campus_course_id", "results": "exam_id.course_id"}
        batch_paths = {"admissions": "batch_id", "attendance": "batch_id", "results": "exam_id.batch_id"}
        for key, paths in [("year_id", year_paths), ("course_id", course_paths), ("batch_id", batch_paths)]:
            if f[key] and kind in paths:
                domain.append((paths[kind], "=", f[key]))
        if kind == "students":
            placement = [(path, "=", f[key]) for key, path in [("year_id", "academic_years_id"), ("course_id", "course_id"), ("batch_id", "batch_id")] if f[key]]
            if placement:
                domain.append(("course_detail_ids", "any", placement))
        if f["source_id"] and kind == "admissions":
            domain.append(("campus_source_id", "=", f["source_id"]))
        if f["status"] and kind in {"admissions", "students"}:
            domain.append(("campus_stage" if kind == "admissions" else "campus_status", "=", f["status"]))
        if kind == "attendance":
            for key, path in [("student_id", "student_id"), ("faculty_id", "attendance_id.faculty_id")]:
                if f[key]:
                    domain.append((path, "=", f[key]))
            if f["subject_id"]:
                domain += ["|", ("attendance_id.campus_subject_id", "=", f["subject_id"]), ("attendance_id.campus_manual_subject_id", "=", f["subject_id"])]
        if kind == "collection":
            if f["method"]:
                domain.append(("campus_method", "=", f["method"]))
            if f["cashier_id"]:
                domain.append(("campus_cashier_id", "=", f["cashier_id"]))
        if f["student_id"] and kind in {"students", "dues", "collection", "results"}:
            path = {"students": "id", "dues": "campus_student_id", "collection": "campus_invoice_id.campus_student_id", "results": "student_id"}[kind]
            domain.append((path, "=", f["student_id"]))
        if kind == "results":
            for key, path in [("exam_id", "exam_id"), ("subject_id", "exam_id.subject_id"), ("faculty_id", "exam_id.responsible_id")]:
                if f[key]:
                    domain.append((path, "=", f[key]))
        if f["fee_head_id"] and kind in {"collection", "dues"}:
            domain.append(("campus_invoice_id.invoice_line_ids.product_id" if kind == "collection" else "invoice_line_ids.product_id", "=", f["fee_head_id"]))
        if kind == "faculty":
            if f["faculty_id"]:
                domain.append(("id", "=", f["faculty_id"]))
            if f["department_id"]:
                domain.append(("main_department_id", "=", f["department_id"]))
        return model, domain

    def _attendance_rows(self, records):
        rows = {}
        policy = self.env.company.campus_excused_policy
        for line in records:
            if line.excused and policy == "exclude":
                continue
            key = (line.student_id.id, line.batch_id.id, line.attendance_id.campus_subject_id.id or line.attendance_id.campus_manual_subject_id.id)
            row = rows.setdefault(key, {"student": line.student_id.name, "number": line.student_id.gr_no or "", "section": line.batch_id.name,
                                       "subject": line.attendance_id.campus_subject_id.name or line.attendance_id.campus_manual_subject_id.name or "", "sessions": 0, "present": 0})
            row["sessions"] += 1
            row["present"] += int(line.present or line.late or (line.excused and policy == "present"))
        for row in rows.values():
            row["rate"] = round(row["present"] * 100 / row["sessions"], 2)
            row["shortage"] = row["present"] * 100 < self.env.company.campus_attendance_threshold * row["sessions"]
        return list(rows.values())

    @api.model
    def get_owner_metrics(self, filters=None):
        f = self._mvp_filters(filters)
        sources = {key: self._mvp_source(key, f) for key in ["admissions", "students", "attendance", "collection", "dues", "results", "faculty"]}
        data = {key: self._mvp_records(*value) for key, value in sources.items()}
        admission = data["admissions"]
        students = data["students"].filtered(lambda s: s.active and s.campus_status == "active")
        attendance = self._attendance_rows(data["attendance"])
        paid = sum(p.amount for p in data["collection"] if f["date_from"] <= p.date <= f["date_to"])
        reversed_amount = sum(p.amount for p in data["collection"] if p.campus_reversal_id and f["date_from"] <= p.campus_reversal_id.date <= f["date_to"])
        due_rows = self._mvp_report_rows("dues", f, data["dues"])
        attended = sum(r["present"] for r in attendance)
        sessions = sum(r["sessions"] for r in attendance)
        stats = [
            ("Active students", len(students), "active_students", "Current status in selected academic year"),
            ("Applications", len(admission), "admissions", "Submitted in selected date range"),
            ("Awaiting review", len(admission.filtered(lambda r: r.campus_stage in {"submitted", "documents", "review"})), "review", "Selected range · awaiting a decision"),
            ("Attendance rate", f"{attended * 100 / sessions:.1f}%" if sessions else "—", "attendance", "Completed sessions · selected range"),
            ("Net fees collected", self._mvp_money(paid - reversed_amount), "collection", "Receipts less reversals in selected range"),
            ("Outstanding fees", self._mvp_money(sum(r["balance"] for r in due_rows)), "dues", "As of " + str(f["date_to"])),
            ("Upcoming exams", self._mvp_upcoming_count(f), "upcoming", "Next 30 days · selected academic year"),
            ("Active faculty / staff", len(data["faculty"]), "faculty", "Current active staff directory"),
        ]
        cards = []
        for label, value, key, detail in stats:
            model, domain = sources[{"active_students": "students", "review": "admissions", "upcoming": "results"}.get(key, key)]
            allowed = self.env[model].check_access_rights("read", raise_exception=False)
            cards.append({"label": label, "value": value if allowed else "—", "detail": detail if allowed else "Reporting access required", "kind": key, "allowed": allowed})
        funnel = [{"label": label, "value": sum(r.campus_stage == state for r in admission)} for state, label in self.env["op.admission"]._fields["campus_stage"].selection]
        programme = defaultdict(int)
        for student in students:
            matching = student.course_detail_ids.filtered(lambda e: e.state == "running" and (not f["year_id"] or e.academic_years_id.id == f["year_id"]) and (not f["course_id"] or e.course_id.id == f["course_id"]) and (not f["batch_id"] or e.batch_id.id == f["batch_id"]))
            for course in matching.course_id:
                programme[course.name] += 1
        collection = defaultdict(lambda: {"collected": 0, "dues": 0})
        for p in data["collection"]:
            if f["date_from"] <= p.date <= f["date_to"]:
                collection[p.date.strftime("%Y-%m")]["collected"] += p.amount
            if p.campus_reversal_id and f["date_from"] <= p.campus_reversal_id.date <= f["date_to"]:
                collection[p.campus_reversal_id.date.strftime("%Y-%m")]["collected"] -= p.amount
        for row in due_rows:
            collection[row["due"][:7]]["dues"] += row["balance"]
        trend = defaultdict(lambda: [0, 0])
        for line in data["attendance"]:
            if line.excused and self.env.company.campus_excused_policy == "exclude":
                continue
            bucket = trend[str(line.attendance_date)]
            bucket[1] += 1
            bucket[0] += int(line.present or line.late or (line.excused and self.env.company.campus_excused_policy == "present"))
        audits = self._mvp_records("campus.mvp.audit", [("company_id", "=", self.env.company.id), ("create_date", ">=", f["date_from"]), ("create_date", "<", f["date_to"] + timedelta(days=1))], limit=50000) if self.env["campus.mvp.audit"].check_access_rights("read", raise_exception=False) else self.env["campus.mvp.audit"]
        years = self.env["op.academic.year"].search([("company_id", "=", self.env.company.id)])
        setup = []
        if self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            for title, model, action in [("Academic year", "op.academic.year", "mvp_years"), ("Department", "op.department", "mvp_departments"), ("Programme", "op.course", "mvp_programmes"), ("Section", "op.batch", "mvp_sections"), ("Subject", "op.subject", "mvp_subjects")]:
                setup.append({"label": title, "ready": bool(self.env[model].search_count([("company_id", "=", self.env.company.id)])), "action": "ideastone_erp." + action})
        upcoming_domain = [("company_id", "=", self.env.company.id), ("state", "!=", "cancel"), ("start_time", ">=", fields.Datetime.now()), ("start_time", "<", fields.Datetime.now() + timedelta(days=30))]
        if f["year_id"]:
            upcoming_domain.append(("campus_year_id", "=", f["year_id"]))
        upcoming = self._mvp_records("op.exam", upcoming_domain).sorted("start_time")[:8]
        return {"stats": cards, "years": [{"id": y.id, "name": y.name} for y in years],
                "funnel": funnel, "programmes": [{"label": k, "value": v} for k, v in sorted(programme.items())],
                "collection": [{"label": k, **v} for k, v in sorted(collection.items())],
                "trend": [{"label": k, "value": round(v[0] * 100 / v[1], 2)} for k, v in sorted(trend.items())],
                "recent": [{"id": a.id, "name": a.name, "when": str(a.create_date), "actor": a.actor_id.name} for a in audits[:8]],
                "setup": setup, "notices": self.env["campus.circular"]._mvp_notices(),
                "upcoming": [{"id": e.id, "name": e.name, "when": str(e.start_time)} for e in upcoming],
                "due_dates": sorted(due_rows, key=lambda r: r["due"])[:8]}

    def _mvp_money(self, amount):
        return f"{self.env.company.currency_id.symbol} {amount:,.2f}"

    def _mvp_upcoming_count(self, f):
        domain = [("company_id", "=", self.env.company.id), ("state", "!=", "cancel"),
                  ("start_time", ">=", fields.Datetime.now()), ("start_time", "<=", fields.Datetime.now() + timedelta(days=30))]
        if f["year_id"]:
            domain.append(("campus_year_id", "=", f["year_id"]))
        return len(self._mvp_records("op.exam", domain))

    @api.model
    def get_owner_source_action(self, kind, filters=None):
        f = self._mvp_filters(filters)
        source_kind = {"active_students": "students", "review": "admissions", "upcoming": "results"}.get(kind, kind)
        model, domain = self._mvp_source(source_kind, f)
        if kind == "active_students":
            domain += [("active", "=", True), ("campus_status", "=", "active")]
        elif kind == "review":
            domain += [("campus_stage", "in", ["submitted", "documents", "review"])]
        elif kind == "upcoming":
            model = "op.exam"
            domain = [("company_id", "=", self.env.company.id), ("state", "!=", "cancel"), ("start_time", ">=", fields.Datetime.now()), ("start_time", "<=", fields.Datetime.now() + timedelta(days=30))]
            if f["year_id"]:
                domain.append(("campus_year_id", "=", f["year_id"]))
        elif kind == "dues":
            records = self._mvp_records(model, domain)
            domain += [("id", "in", [r["id"] for r in self._mvp_report_rows("dues", f, records)])]
        self.env[model].check_access_rights("read")
        action_name = {"op.student": "mvp_students", "op.admission": "mvp_applications", "op.faculty": "mvp_faculty", "op.exam": "mvp_exams", "op.result.line": "mvp_results"}.get(model)
        action = self.get_owner_action("ideastone_erp." + action_name) if action_name else {"type": "ir.actions.act_window", "view_mode": "tree,form", "res_model": model}
        return dict(action, name=kind.title(), domain=domain)

    @api.model
    def get_owner_action(self, xmlid):
        if not self._is_mvp_user():
            raise AccessError(_("College workspace permission is required."))
        allowed = {action for module in self.get_overview()["faculty_modules"] for item in module["items"]
                   for action in (item.get("action"), item.get("source_action")) if action}
        if xmlid not in allowed:
            raise AccessError(_("This action is outside your permitted college workspace."))
        action = self.env["ir.actions.actions"]._for_xml_id(xmlid)
        target_model = self._client_action_models().get(xmlid.removeprefix("ideastone_erp.")) or action["res_model"]
        model = self.env[target_model]
        model.check_access_rights("read")
        if xmlid == "ideastone_erp.mvp_college":
            action["res_id"] = self.env.company.id
        elif xmlid in {"ideastone_erp.mvp_student_request_types", "ideastone_erp.mvp_fee_heads"}:
            action["domain"] = ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)]
        elif "company_id" in model._fields:
            domain = safe_eval(action.get("domain") or "[]") if isinstance(action.get("domain"), str) else action.get("domain") or []
            action["domain"] = domain + [("company_id", "=", self.env.company.id)]
        context = safe_eval(action.get("context") or "{}", {"uid": self.env.uid, "active_id": False}) if isinstance(action.get("context"), str) else action.get("context") or {}
        action["context"] = dict(context, default_company_id=self.env.company.id, campus_module=self._mvp_module_for(xmlid))
        return action

    def _mvp_module_for(self, xmlid):
        return next((key for key, _label, _icon, items in self._owner_modules() if any((action if "." in action else "ideastone_erp." + action) == xmlid for _title, action in items)), "home")

    def _mvp_report_rows(self, kind, f, records=None):
        if records is None:
            records = self._mvp_records(*self._mvp_source(kind, f))
        if kind == "attendance":
            return self._attendance_rows(records)
        rows = []
        for rec in records:
            if kind == "admissions":
                rows.append({"application": rec.application_number, "name": rec.name, "programme": rec.course_id.name, "stage": rec.campus_stage, "source": rec.campus_source_id.name or "", "date": str(rec.application_date), "student_number": rec.student_id.gr_no or ""})
            elif kind == "students":
                for e in rec.course_detail_ids.filtered(lambda e: (not f["year_id"] or e.academic_years_id.id == f["year_id"]) and (not f["course_id"] or e.course_id.id == f["course_id"]) and (not f["batch_id"] or e.batch_id.id == f["batch_id"])):
                    rows.append({"number": rec.gr_no or "", "student": rec.name, "programme": e.course_id.name, "section": e.batch_id.name, "year": e.academic_years_id.name, "semester": e.academic_term_id.name, "status": rec.campus_status})
            elif kind == "collection":
                base = {"receipt": rec.campus_receipt_number, "student": rec.campus_invoice_id.campus_student_id.name, "invoice": rec.campus_invoice_id.name, "method": rec.campus_method, "cashier": rec.campus_cashier_id.name}
                if f["date_from"] <= rec.date <= f["date_to"]:
                    rows.append(dict(base, date=str(rec.date), collected=rec.amount, reversed=0, net=rec.amount))
                if rec.campus_reversal_id and f["date_from"] <= rec.campus_reversal_id.date <= f["date_to"]:
                    rows.append(dict(base, date=str(rec.campus_reversal_id.date), collected=0, reversed=rec.amount, net=-rec.amount))
            elif kind == "dues":
                # Current balances use native reconciliation. Historic custom receipts retain
                # their original date and reversal date, even after reconcile links are removed.
                if f["date_to"] >= fields.Date.context_today(self):
                    balance = rec.amount_residual
                else:
                    payments = self.env["account.payment"].search([("campus_invoice_id", "=", rec.id), ("date", "<=", f["date_to"])])
                    net = sum(p.amount for p in payments if not p.campus_reversal_id or p.campus_reversal_id.date > f["date_to"])
                    balance = max(0, rec.amount_total - net)
                if balance > 0:
                    due = rec.invoice_date_due or rec.invoice_date
                    rows.append({"id": rec.id, "invoice": rec.name, "student": rec.campus_student_id.name, "programme": rec.campus_course_id.name, "gross": rec.amount_total, "paid": rec.amount_total - balance, "balance": balance, "due": str(due), "days_overdue": max(0, (f["date_to"] - due).days)})
            elif kind == "results":
                rows.append({"exam": rec.exam_id.name, "subject": rec.exam_id.subject_id.name, "student": rec.student_id.name, "marks": rec.marks if rec.campus_entered else "Missing", "maximum": rec.exam_id.total_marks, "percentage": rec.campus_percentage if rec.campus_entered else "", "grade": rec.grade or "", "result": rec.status or "Missing", "publication": rec.exam_id.campus_state})
            elif kind == "faculty":
                domain = [("faculty_id", "=", rec.id), ("company_id", "=", self.env.company.id), ("state", "!=", "cancel"), ("start_datetime", ">=", f["date_from"]), ("start_datetime", "<", f["date_to"] + timedelta(days=1))]
                if f["year_id"]:
                    domain.append(("campus_year_id", "=", f["year_id"]))
                for key, path in [("course_id", "course_id"), ("batch_id", "batch_id"), ("subject_id", "subject_id")]:
                    if f[key]:
                        domain.append((path, "=", f[key]))
                sessions = self._mvp_records("op.session", domain)
                rows.append({"staff_id": rec.campus_staff_code or "", "staff": rec.name, "department": rec.main_department_id.name or "", "designation": rec.campus_designation or "", "subjects": len(sessions.subject_id), "sections": len(sessions.batch_id), "sessions": len(sessions)})
        return rows


class CollegeReport(models.TransientModel):
    _name = "campus.mvp.report"
    _description = "Filtered college reports and CSV export"

    kind = fields.Selection([(k, k.title()) for k in ["admissions", "students", "attendance", "collection", "dues", "results", "faculty"]], required=True, default="students")
    date_from = fields.Date(required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    year_id = fields.Many2one("op.academic.year", string="Academic year")
    course_id = fields.Many2one("op.course", string="Programme")
    batch_id = fields.Many2one("op.batch", string="Section")
    subject_id = fields.Many2one("op.subject")
    faculty_id = fields.Many2one("op.faculty")
    student_id = fields.Many2one("op.student")
    cashier_id = fields.Many2one("res.users")
    source_id = fields.Many2one("utm.source")
    exam_id = fields.Many2one("op.exam")
    fee_head_id = fields.Many2one("product.product", domain="[('campus_fee_head','=',True)]")
    department_id = fields.Many2one("op.department")
    status = fields.Char(string="Status code (optional)")
    method = fields.Selection([("cash", "Cash"), ("upi", "UPI"), ("bank", "Bank transfer"), ("card", "Card"), ("other", "Other")])
    only_shortage = fields.Boolean(string="Only below attendance threshold")
    file = fields.Binary(readonly=True)
    filename = fields.Char(readonly=True)
    summary = fields.Text(readonly=True)

    def action_csv(self):
        self.ensure_one()
        dashboard = self.env["campus.dashboard"]
        filters = {key: self[key].id if self._fields[key].type == "many2one" else str(self[key] or "") for key in ["date_from", "date_to", "year_id", "course_id", "batch_id", "subject_id", "faculty_id", "student_id", "cashier_id", "source_id", "exam_id", "fee_head_id", "department_id", "status", "method"]}
        f = dashboard._mvp_filters(filters)
        model, _domain = dashboard._mvp_source(self.kind, f)
        self.env[model].check_access_rights("read")
        rows = dashboard._mvp_report_rows(self.kind, f)
        if self.kind == "attendance" and self.only_shortage:
            rows = [r for r in rows if r["shortage"]]
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([self.env.company.name, self.kind, self.date_from, self.date_to, self.year_id.name or "All years"])
        if self.kind == "attendance":
            writer.writerow(["Threshold", self.env.company.campus_attendance_threshold, "Excused policy", self.env.company.campus_excused_policy])
        if rows:
            writer.writerow(list(rows[0]))
        for row in rows:
            writer.writerow(["'" + str(value) if str(value).lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) and not isinstance(value, (int, float)) else value for value in row.values()])
        if not rows:
            writer.writerow(["No records match these filters. Complete the source workflow or change the reporting period."])
        self.write({"file": base64.b64encode(out.getvalue().encode("utf-8-sig")), "filename": "College-%s.csv" % self.kind,
                    "summary": _("Exported %s rows using your current college and record permissions.") % len(rows)})
        return {"type": "ir.actions.act_url", "url": f"/web/content/campus.mvp.report/{self.id}/file/{self.filename}?download=true", "target": "self"}
