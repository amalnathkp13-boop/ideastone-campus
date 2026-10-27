import json
from datetime import timedelta

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
            ("Student Attendance", "op.attendance.sheet", "ideastone_erp.action_student_attendance_workspace", "Academics"),
            ("Subject-wise Attendance", "op.attendance.sheet", "ideastone_erp.action_subject_attendance_workspace", "Staff"),
            ("Examinations", "op.exam", "openeducat_exam.act_open_op_exam_view", "Academics"),
            ("Results", "op.result.line", "ideastone_erp.action_results", "Academics"),
            ("Assignments", "op.assignment", "openeducat_assignment.act_open_op_assignment_view", "Academics"),
            ("Review submissions", "op.assignment.sub.line", "ideastone_erp.mvp_learning_submissions", "Academics"),
            ("Library catalogue", "op.media", "openeducat_library.act_open_op_media_view", "Library"),
            ("Library circulation", "op.media.movement", "ideastone_erp.action_circulation", "Library"),
            ("Fee terms", "op.fees.terms", "openeducat_fees.act_open_fees_terms_view", "Purchase and accounts"),
            ("Fee invoices", "account.move", "ideastone_erp.action_fee_invoices", "Purchase and accounts"),
            ("Accounting entries", "account.move", "ideastone_erp.action_ledger", "Purchase and accounts"),
            ("Purchase orders", "purchase.order", "ideastone_erp.action_orders", "Purchase and accounts"),
            ("Stock movements", "stock.picking", "ideastone_erp.action_stock", "Purchase and accounts"),
            ("Maintenance", "maintenance.request", "ideastone_erp.action_maintenance", "Campus services"),
            ("Leave requests", "hr.leave", "ideastone_erp.action_faculty_leave_page", "Staff"),
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
        navigation += self._navigation_extensions()
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
            if item["label"] == "Subject-wise Attendance":
                if not self.env.user.has_group("openeducat_core.group_op_faculty"):
                    continue
                item["group"] = "Subject Attendance"
            if admin or item["allowed"]:
                visible.append(item)
        faculty = self.env["op.faculty"].search([("user_id", "=", self.env.uid), "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)], limit=1) if self.env["op.faculty"].check_access_rights("read", raise_exception=False) else self.env["op.faculty"]
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
        faculty_modules = self._faculty_modules(visible, faculty, pages) if faculty and not admin and self.env.user.has_group("openeducat_core.group_op_faculty") else []
        faculty_tasks, faculty_schedule, faculty_surveys = [], [], []
        if faculty_modules:
            allocations = self.env["op.session"].read_group([
                ("faculty_id", "=", faculty.id), ("company_id", "=", self.env.company.id), ("state", "!=", "cancel"),
            ], ["subject_id"], ["subject_id"])
            assigned_subjects = set(faculty.faculty_subject_ids.ids) | {row["subject_id"][0] for row in allocations if row["subject_id"]}
            for stat in stats:
                if stat["label"] == "Assigned subjects":
                    stat.update(value=len(assigned_subjects), detail="Faculty subjects and timetable")
            # Survey participation uses Odoo's token-checked website workflow. This
            # bounded projection exposes only invitations addressed to this account;
            # faculty do not receive survey design or other respondents' ACLs.
            invitations = self.env["survey.user_input"].sudo().search([
                ("partner_id", "=", self.env.user.partner_id.id), ("test_entry", "=", False),
            ], limit=30)
            faculty_surveys = [{"id": invitation.id, "name": invitation.survey_id.title,
                "state": invitation.state, "deadline": str(invitation.deadline or ""),
                "expired": bool(invitation.deadline and invitation.deadline < fields.Datetime.now()),
                "url": invitation.get_print_url() if invitation.state == "done" else invitation.get_start_url(),
            } for invitation in invitations]
            tasks = self.env["campus.faculty.task"].search([("state", "in", ["planned", "progress"])], limit=5)
            faculty_tasks = [{"id": task.id, "name": task.name, "due": str(task.deadline), "state": task.state} for task in tasks]
            if self.env["op.session"].check_access_rights("read", raise_exception=False):
                sessions = self.env["op.session"].search([("faculty_id", "=", faculty.id), ("company_id", "=", self.env.company.id),
                    ("state", "=", "confirm"), ("start_datetime", ">=", fields.Datetime.now()),
                    ("start_datetime", "<", fields.Datetime.now() + timedelta(days=7))], order="start_datetime", limit=5)
                faculty_schedule = [{"id": s.id, "subject": s.subject_id.name, "batch": s.batch_id.name,
                    "when": fields.Datetime.context_timestamp(self, s.start_datetime).strftime("%d %b %Y · %H:%M")} for s in sessions]
            stats += [{"label": "Open tasks", "value": self.env["campus.faculty.task"].search_count([("state", "in", ["planned", "progress"])]), "detail": "Your personal diary"},
                      {"label": "Activities", "value": self.env["campus.faculty.activity"].search_count([]), "detail": "Your clubs, SDP and training"}]
        return {"company": self.env.company.name, "user": self.env.user.name,
                "faculty_modules": faculty_modules,
                "faculty_tasks": faculty_tasks, "faculty_schedule": faculty_schedule, "faculty_surveys": faculty_surveys,
                "navigation": visible, "stats": stats, "pages": pages, "queues": queues, "quick": quick,
                "is_admin": admin, "is_hod": self.env.user.has_group("ideastone_erp.group_od_hod_approver"),
                "workspace_role": "College administrator" if admin else "HOD" if self.env.user.has_group("ideastone_erp.group_od_hod_approver") else "Faculty" if faculty else "Staff",
                "today": fields.Date.to_string(fields.Date.context_today(self)), "library_allowed": library,
                "report_allowed": self.env["op.attendance.line"].check_access_rights("read", raise_exception=False),
                "payroll_allowed": self.env["campus.payslip"].check_access_rights("read", raise_exception=False),
                "appointments": [{"id": r.id, "faculty": r.faculty_id.name, "role": "Library In-charge", "scope": ", ".join(r.media_type_ids.mapped("name")),
                                  "state": r.state, "effective": r.effective, "until": str(r.date_to)} for r in appointments]}

    def _navigation_extensions(self):
        """Extra staff navigation entries (label, model, action, group). Add-on modules extend this."""
        return []

    def _faculty_module_definitions(self):
        """Staff sidebar modules (key, label, icon, navigation groups). Add-on modules extend this."""
        return [
            ("home", "Home", "home", []),
            ("teaching", "My task list", "graduation-cap", ["Academic management", "Examination & results", "Mentorship & student support"]),
            ("search", "Search", "search", []),
            ("staff", "My profile & payroll", "user", ["HR & payroll"]),
            ("attendance", "Subject-wise Attendance", "calendar-check-o", ["Subject Attendance"]),
            ("od", "OD Management", "calendar-check-o", ["OD Management"]),
            ("library", "Library & learning", "book", ["Library & learning"]),
            ("grievances", "Grievances & others", "commenting-o", []),
            ("services", "Campus services", "building-o", ["Campus services"]),
            ("hostel", "Hostel", "bed", ["Campus services"]),
            ("engagement", "Communication", "comments-o", ["Communication & student portal"]),
            ("reports", "Reports", "bar-chart", []),
            ("analytics", "Dashboard", "dashboard", []),
            ("help", "Help", "question-circle", []),
        ]

    def _faculty_modules(self, visible, faculty, pages):
        """Navigation is discovery only. Every action keeps its model ACLs and record rules."""
        definitions = self._faculty_module_definitions()
        result = []
        for key, label, icon, groups in definitions:
            items = [dict(item, action_id=self.env.ref(item["action"]).id) for item in visible
                     if item["allowed"] and item["group"] in groups]
            if key == "home":
                items = [{"label": "Faculty overview", "page": "overview"}, {"label": "Find a module", "page": "modules"}]
            elif key == "teaching" and self.env["campus.faculty.task"].check_access_rights("read", raise_exception=False):
                items = [item for item in items if item["model"] not in {
                    "campus.faculty.activity", "campus.faculty.document", "campus.faculty.assessment", "op.student",
                }]
                items.insert(0, {"label": "My tasks & e-diary", "action": "ideastone_erp.action_faculty_task",
                                 "action_id": self.env.ref("ideastone_erp.action_faculty_task").id})
            elif key == "staff":
                items.insert(0, {"label": "My staff profile", "profile_id": faculty.id})
            elif key == "library":
                items.insert(0, {"label": "OPAC & digital library", "url": "/my/campus/library"})
                if any(p["key"] == "library" for p in pages):
                    items.insert(0, {"label": "Circulation desk", "page": "library"})
            elif key == "reports":
                items = [{"label": "Reports & exports", "page": "reports"}]
                report_tools = [
                    ("report_internal", "Internal mark generation & analysis", "campus.faculty.assessment"),
                    ("report_students", "Class & students", "op.student"),
                    ("report_photos", "Class & student photos", "op.student"),
                    ("report_education", "Previous academic information", "campus.student.education"),
                    ("report_attendance", "Subject-wise attendance report", "op.attendance.sheet"),
                    ("report_tests", "Institution tests", "op.exam"),
                    ("report_counseling", "Students counseling", "campus.counseling"),
                    ("report_lesson", "Notes of lesson", "campus.teaching.plan"),
                    ("report_lesson_review", "NOL approval", "campus.teaching.plan"),
                    ("report_chronicle", "My chronicle this year", "campus.faculty.achievement"),
                    ("report_university", "University examination results", "op.result.line"),
                    ("report_autonomous", "Autonomous ESE results", "op.result.line"),
                ]
                items += [{"label": title, "tool": tool, "model": model} for tool, title, model in report_tools
                          if self.env[model].check_access_rights("read", raise_exception=False)]
            elif key == "search":
                items = [{"label": "Find a module", "page": "modules"}]
                if self.env["op.student"].check_access_rights("read", raise_exception=False):
                    items.append({"label": "Search my students", "tool": "assigned_students"})
            elif key == "analytics":
                items = [{"label": "Faculty analytics", "page": "analytics"}]
            elif key == "grievances":
                items = [{"label": "My grievances", "tool": "grievance"}] if self.env["campus.service.request"].check_access_rights("read", raise_exception=False) else []
            elif key == "hostel":
                items = [item for item in items if item["label"].startswith("Hostel")]
            elif key == "services":
                items = [item for item in items if not item["label"].startswith("Hostel")]
                if self.env["campus.service.request"].check_access_rights("read", raise_exception=False):
                    items.append({"label": "Register complaint on student", "tool": "student_complaint"})
            elif key == "help":
                items = [{"label": "Faculty guide", "page": "help"}]
            if key == "teaching":
                items.append({"label": "Survey direct", "page": "surveys"})
                tools = [("assigned_students", "My assigned students", "op.student"),
                         ("subject_attendance", "Subject-wise attendance", "op.attendance.sheet"),
                         ("alternate", "Alternate hour", "campus.service.request"),
                         ("club", "Club functions & attendance", "campus.faculty.activity"),
                         ("sdp", "SDP functions & attendance", "campus.faculty.activity"),
                         ("vac", "VAC & placement training", "campus.faculty.activity"),
                         ("certificates", "Exam certificates", "campus.faculty.document"),
                         ("question_papers", "Question papers", "campus.faculty.document"),
                         ("answer_keys", "Answer keys", "campus.faculty.document"),
                         ("internal", "Internal mark generation", "campus.faculty.assessment"),
                         ("additional", "Additional internal marks", "campus.faculty.assessment"),
                         ("practical", "Practical external marks", "campus.faculty.assessment"),
                         ("holidays", "College holidays", "resource.calendar.leaves")]
                for tool, title, model in tools:
                    if self.env[model].check_access_rights("read", raise_exception=False):
                        items.append({"label": title, "tool": tool, "model": model})
            if items:
                result.append({"key": key, "label": label, "icon": icon, "items": items})
        return result

    @api.model
    def get_faculty_action(self, tool):
        faculty = self.env["op.faculty"].search([("user_id", "=", self.env.uid), "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)], limit=1)
        if not faculty or not self.env.user.has_group("openeducat_core.group_op_faculty"):
            raise AccessError(_("A linked faculty account is required."))
        if tool == "subject_attendance":
            action = self.env["ir.actions.actions"]._for_xml_id("ideastone_erp.action_subject_attendance_workspace")
            action["context"] = dict(self.env.context, campus_module="attendance", campus_tool=tool)
            return action
        specs = {
            "assigned_students": ("My assigned students", "op.student", [], {}),
            "alternate": ("Alternate teaching hour", "campus.service.request", [("kind", "=", "alternate")], {"default_kind": "alternate", "default_faculty_id": faculty.id}),
            "club": ("Club functions & attendance", "campus.faculty.activity", [("kind", "=", "club")], {"default_kind": "club"}),
            "sdp": ("SDP functions & attendance", "campus.faculty.activity", [("kind", "=", "sdp")], {"default_kind": "sdp"}),
            "vac": ("VAC & placement training", "campus.faculty.activity", [("kind", "=", "vac")], {"default_kind": "vac"}),
            "certificates": ("Exam certificates", "campus.faculty.document", [("kind", "=", "certificate")], {"default_kind": "certificate"}),
            "question_papers": ("Question papers", "campus.faculty.document", [("kind", "=", "question")], {"default_kind": "question"}),
            "answer_keys": ("Answer keys", "campus.faculty.document", [("kind", "=", "answer")], {"default_kind": "answer"}),
            "holidays": ("College holidays", "resource.calendar.leaves", [("resource_id", "=", False)], {}),
            "grievance": ("My grievances", "campus.service.request", [("kind", "=", "grievance")], {"default_kind": "grievance"}),
            "student_complaint": ("Register complaint on student", "campus.service.request", [("kind", "=", "student_complaint")], {"default_kind": "student_complaint", "default_faculty_id": faculty.id}),
            "report_internal": ("Internal mark generation & analysis", "campus.faculty.assessment", [], {}),
            "report_students": ("Class & students", "op.student", [], {}),
            "report_photos": ("Class & student photos", "op.student", [], {}),
            "report_education": ("Previous academic information", "campus.student.education", [], {}),
            "report_attendance": ("Subject-wise attendance report", "op.attendance.sheet", [("faculty_id", "=", faculty.id), ("state", "=", "done")], {"group_by": "campus_subject_id"}),
            "report_tests": ("Institution tests", "op.exam", [("campus_exam_kind", "=", "institution")], {"default_campus_exam_kind": "institution"}),
            "report_counseling": ("Students counseling", "campus.counseling", [("mentor_id", "=", faculty.id)], {}),
            "report_lesson": ("Notes of lesson", "campus.teaching.plan", [("faculty_id", "=", faculty.id)], {}),
            "report_lesson_review": ("NOL approval", "campus.teaching.plan", [("review_state", "=", "submitted")], {}),
            "report_chronicle": ("My chronicle this year", "campus.faculty.achievement", [("faculty_id", "=", faculty.id), ("date_from", ">=", fields.Date.context_today(self).replace(month=1, day=1))], {}),
            "report_university": ("University examination results", "op.result.line", [("exam_id.campus_exam_kind", "=", "university")], {}),
            "report_autonomous": ("Autonomous ESE results", "op.result.line", [("exam_id.campus_exam_kind", "=", "autonomous")], {}),
        }
        for kind, label in [("internal", "Internal mark generation"), ("additional", "Additional internal marks"), ("practical", "Practical external marks")]:
            specs[kind] = (label, "campus.faculty.assessment", [("kind", "=", kind)], {"default_kind": kind})
        if tool not in specs:
            raise AccessError(_("Unknown faculty workspace."))
        label, model, domain, context = specs[tool]
        self.env[model].check_access_rights("read")
        if "company_id" in self.env[model]._fields:
            domain += ["|", ("company_id", "=", False), ("company_id", "in", self.env.companies.ids)]
        if tool in {"assigned_students", "report_students", "report_photos"}:
            batches = self.env["op.session"].search([("faculty_id", "=", faculty.id), ("company_id", "=", self.env.company.id)]).batch_id
            domain += [("course_detail_ids.batch_id", "in", batches.ids)]
        if model in {"op.exam", "op.result.line"}:
            batches = self.env["op.session"].search([("faculty_id", "=", faculty.id), ("company_id", "=", self.env.company.id)]).batch_id
            prefix = "exam_id." if model == "op.result.line" else ""
            domain += [(prefix + "responsible_id", "in", faculty.ids), (prefix + "batch_id", "in", batches.ids)]
        views = [(False, "tree"), (False, "form")]
        if tool == "report_photos":
            views.insert(0, (self.env.ref("openeducat_core.kanban_view_student").id, "kanban"))
        module = "reports" if tool.startswith("report_") else {"grievance": "grievances", "student_complaint": "services", "assigned_students": "search"}.get(tool, "teaching")
        return {"type": "ir.actions.act_window", "name": label, "res_model": model,
                "views": views, "domain": domain,
                "context": dict(self.env.context, **context, campus_module=module, campus_tool=tool)}
