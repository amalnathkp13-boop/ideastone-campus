import json

from odoo.exceptions import AccessError

from odoo import _, api, fields, models, tools


class Dashboard(models.AbstractModel):
    _name = "campus.dashboard"
    _description = "Permission aware campus dashboard"

    @api.model
    def get_overview(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Campus overview requires an internal staff account."))
        with tools.file_open("ideastone_erp/models/navigation.json", "r") as source:
            navigation = json.load(source)
        standard = [
            ("Admissions", "op.admission", "openeducat_admission.act_open_op_admission_view", "Admissions"),
            ("Students", "op.student", "openeducat_core.act_open_op_student_view", "Academics"),
            ("Faculty", "op.faculty", "openeducat_core.act_open_op_faculty_view", "Staff"),
            ("Subjects", "op.subject", "ideastone_erp.action_subjects", "Academics"),
            ("Timetable", "op.session", "openeducat_timetable.act_open_op_session_view", "Academics"),
            ("Class attendance", "op.attendance.sheet", "openeducat_attendance.act_open_op_attendance_sheet_view", "Academics"),
            ("Examinations", "op.exam", "openeducat_exam.act_open_op_exam_view", "Academics"),
            ("Results", "op.result.line", "ideastone_erp.action_results", "Academics"),
            ("Assignments", "op.assignment", "openeducat_assignment.act_open_op_assignment_view", "Academics"),
            ("Library catalogue", "op.media", "openeducat_library.act_open_op_media_view", "Library"),
            ("Library circulation", "op.media.movement", "ideastone_erp.action_circulation", "Library"),
            ("Fee terms", "op.fees.terms", "openeducat_fees.act_open_fees_terms_view", "Purchase and accounts"),
            ("Fee invoices", "account.move", "ideastone_erp.action_fee_invoices", "Purchase and accounts"),
            ("Accounting entries", "account.move", "ideastone_erp.action_ledger", "Purchase and accounts"),
            ("Purchase orders", "purchase.order", "ideastone_erp.action_orders", "Purchase and accounts"),
            ("Stock movements", "stock.picking", "ideastone_erp.action_stock", "Purchase and accounts"),
            ("Maintenance", "maintenance.request", "ideastone_erp.action_maintenance", "Campus services"),
            ("Leave requests", "hr.leave", "ideastone_erp.action_leave", "Staff"),
            ("Staff attendance", "hr.attendance", "ideastone_erp.action_staff_attendance", "Staff"),
            ("Admission leads / agents", "crm.lead", "ideastone_erp.action_leads", "Admissions"),
            ("Surveys", "survey.survey", "ideastone_erp.action_surveys", "Engagement"),
            ("Events and clubs", "event.event", "ideastone_erp.action_events", "Engagement"),
            ("Alumni forums", "forum.forum", "ideastone_erp.action_forums", "Engagement"),
            ("Payment providers", "payment.provider", "ideastone_erp.action_payment_providers", "Purchase and accounts"),
        ]
        navigation += [{"label": label, "model": model, "action": action, "group": group} for label, model, action, group in standard]
        categories = {
            "Admissions": "Administration & admissions", "Staff": "HR & payroll",
            "Academics": "Academic management", "Library": "Library & learning",
            "Learning": "Library & learning", "Purchase and accounts": "Finance & fees",
            "Campus services": "Campus services", "Engagement": "Communication & student portal",
        }
        admin = self.env.user.has_group("ideastone_erp.group_college_admin") or self.env.user.has_group("ideastone_erp.group_manager")
        navigation += [
            {"label": "Departments", "model": "op.department", "action": "openeducat_core.act_open_op_department_view", "group": "Admissions"},
            {"label": "Programmes", "model": "op.course", "action": "openeducat_core.act_open_op_course_view", "group": "Admissions"},
            {"label": "Batches", "model": "op.batch", "action": "openeducat_core.act_open_op_batch_view", "group": "Admissions"},
            {"label": "Learning platform", "model": "op.course", "action": "ideastone_lms.action_lms_frame", "group": "Learning"},
        ]
        visible = []
        for item in navigation:
            if not self.env.ref(item["action"], raise_if_not_found=False):
                continue
            item["allowed"] = bool(item["model"] in self.env and self.env[item["model"]].check_access_rights("read", raise_exception=False))
            item["group"] = categories.get(item["group"], item["group"])
            if item["label"] in {"Examinations", "Results", "Mark reviews and revaluation"}:
                item["group"] = "Examination & results"
            if item["label"] in {"Mentor counseling"}:
                item["group"] = "Mentorship & student support"
            if admin or item["allowed"]:
                visible.append(item)
        faculty = self.env["op.faculty"].search([("user_id", "=", self.env.uid)], limit=1) if self.env["op.faculty"].check_access_rights("read", raise_exception=False) else self.env["op.faculty"]
        stats = []
        if admin:
            for label, model, domain in [
                ("Active students", "op.student", [("active", "=", True)]),
                ("Faculty", "op.faculty", [("active", "=", True)]),
                ("Programmes", "op.course", []),
                ("Pending service requests", "campus.service.request", [("state", "=", "submitted")]),
            ]:
                if self.env[model].check_access_rights("read", raise_exception=False):
                    stats.append({"label": label, "value": self.env[model].search_count(domain), "detail": "Current permitted records"})
        else:
            stats = [{"label": "Authorized screens", "value": len(visible), "detail": "Your account permissions"},
                     {"label": "Assigned subjects", "value": len(faculty.faculty_subject_ids), "detail": "Current faculty allocation"}]
        pages = [{"key": "overview", "label": "Overview", "icon": "home"},
                 {"key": "modules", "label": "All modules" if admin else "My modules", "icon": "th-large"},
                 {"key": "reports", "label": "Reports", "icon": "bar-chart"}]
        approver = self.env.user.has_group("ideastone_erp.group_role_approver")
        if admin or approver:
            pages.append({"key": "access", "label": "Access control", "icon": "shield", "action": "ideastone_erp.action_responsibilities"})
        if admin:
            pages.append({"key": "staff", "label": "Staff directory", "icon": "users", "action": "openeducat_core.act_open_op_faculty_view"})
        if faculty:
            pages.append({"key": "profile", "label": "My staff profile", "icon": "user", "profile_id": faculty.id})
        library = False
        try:
            self.env["campus.responsibility"]._library_scope()
            library = True
            pages.append({"key": "library", "label": "Library desk", "icon": "book"})
        except AccessError:
            pass
        appointments = self.env["campus.responsibility"]
        if appointments.check_access_rights("read", raise_exception=False):
            appointments = appointments.search([("company_id", "=", self.env.company.id)], limit=8)
        queues = []
        if admin or approver:
            count = self.env["campus.responsibility"].search_count([("state", "=", "requested"), ("company_id", "=", self.env.company.id)])
            queues.append({"label": "Faculty role requests", "count": count, "detail": "Appointments awaiting independent approval", "action": "ideastone_erp.action_responsibilities"})
        quick = [x for x in visible if x["allowed"] and x["label"] in ("Admissions", "Class attendance", "Timetable", "Fee invoices", "Mentor counseling", "Lesson plans")][:4]
        return {"company": self.env.company.name, "user": self.env.user.name,
                "navigation": visible, "stats": stats, "pages": pages, "queues": queues, "quick": quick,
                "is_admin": admin, "workspace_role": "College administrator" if admin else "Faculty" if faculty else "Staff",
                "today": fields.Date.to_string(fields.Date.context_today(self)), "library_allowed": library,
                "report_allowed": self.env["op.attendance.line"].check_access_rights("read", raise_exception=False),
                "payroll_allowed": self.env["campus.payslip"].check_access_rights("read", raise_exception=False),
                "appointments": [{"id": r.id, "faculty": r.faculty_id.name, "role": "Library In-charge", "scope": ", ".join(r.media_type_ids.mapped("name")),
                                  "state": r.state, "effective": r.effective, "until": str(r.date_to)} for r in appointments]}
