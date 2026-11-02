from collections import defaultdict
from datetime import timedelta

from odoo.exceptions import AccessError

from odoo import _, api, fields, models


class PrincipalDashboard(models.AbstractModel):
    _name = "ideastone.principal.dashboard"
    _description = "Principal Dashboard Data"

    @api.model
    def get_overview(self):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            raise AccessError(_("Only a principal can view campus oversight data."))
        company = self.env.company
        counts = {}
        for key, model, domain in [
            ("students", "op.student", [("active", "=", True)]),
            ("faculty", "op.faculty", [("active", "=", True)]),
            ("applications", "op.admission", []),
            ("pending", "ideastone.principal.request", [("state", "=", "submitted")]),
            ("exams", "op.exam", []),
            ("notices", "ideastone.principal.notice", [("state", "=", "published")]),
        ]:
            source = self.env[model]
            if not source.check_access_rights("read", raise_exception=False):
                counts[key] = 0
                continue
            if "company_id" in source._fields:
                domain += [("company_id", "=", company.id)]
            counts[key] = source.search_count(domain)
        requests = self.env["ideastone.principal.request"].search(
            [("company_id", "=", company.id), ("state", "=", "submitted")],
            order="due_date, create_date", limit=8)
        notices = self.env["ideastone.principal.notice"].search(
            [("company_id", "=", company.id)], order="create_date desc", limit=8)
        leave = self.env["campus.student.leave"].search(
            [("company_id", "=", company.id), ("principal_id", "=", self.env.uid),
             ("state", "=", "principal")], order="create_date desc", limit=8)
        counts["student_leave"] = self.env["campus.student.leave"].search_count(
            [("company_id", "=", company.id), ("principal_id", "=", self.env.uid),
             ("state", "=", "principal")])
        return {
            "company": company.name, "user": self.env.user.name,
            "today": str(fields.Date.context_today(self)), "counts": counts,
            "requests": [{"id": row.id, "name": row.name, "type": dict(row._fields["request_type"].selection).get(row.request_type),
                          "requester": row.requester_id.name, "due": str(row.due_date or ""), "state": row.state}
                         for row in requests],
            "student_leave": [{"id": row.id, "student": row.student_id.name, "reason": row.reason or "",
                               "from": str(row.date or ""), "to": str(row.deadline or "")}
                              for row in leave],
            "notices": [{"id": row.id, "name": row.name, "audience": dict(row._fields["audience"].selection).get(row.audience),
                         "state": row.state, "date": str(row.published_on or row.create_date or "")[:10]}
                        for row in notices],
            "dashboard": self._performance(),
        }

    def _performance(self):
        company = self.env.company
        today = fields.Date.context_today(self)
        start = (today.replace(day=1) - timedelta(days=155)).replace(day=1)

        def records(model, domain, company_field="company_id"):
            source = self.env[model]
            if not source.check_access_rights("read", raise_exception=False):
                return source.browse()
            return source.search([(company_field, "=", company.id)] + domain, limit=50000)

        def percent(numerator, denominator):
            return round(100 * numerator / denominator, 1) if denominator else None

        years = records("op.academic.year", [("campus_current", "=", True)])
        year = years[:1]
        terms = records("op.academic.term", [("term_start_date", "<=", today), ("term_end_date", ">=", today)])
        term = terms.filtered(lambda row: not year or row.academic_year_id == year)[:1]
        attendance = records("op.attendance.line", [("attendance_date", ">=", start), ("attendance_date", "<=", today),
            ("attendance_id.state", "=", "done")], "attendance_id.company_id")
        monthly = defaultdict(lambda: {"present": 0, "sessions": 0, "billed": 0, "collected": 0})
        for offset in reversed(range(6)):
            monthly[fields.Date.subtract(today.replace(day=1), months=offset).strftime("%Y-%m")]
        departments = defaultdict(lambda: {"present": 0, "sessions": 0})
        students = defaultdict(lambda: {"present": 0, "sessions": 0})
        policy = company.campus_excused_policy
        for line in attendance:
            if line.excused and policy == "exclude":
                continue
            present = int(line.present or line.late or (line.excused and policy == "present"))
            bucket = monthly[str(line.attendance_date)[:7]]
            bucket["present"] += present
            bucket["sessions"] += 1
            dept = departments[line.course_id.department_id.name or _("Unassigned department")]
            dept["present"] += present
            dept["sessions"] += 1
            student = students[line.student_id.id]
            student["present"] += present
            student["sessions"] += 1
        invoices = records("account.move", [("campus_student_id", "!=", False), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("invoice_date", ">=", year.start_date if year else start),
            ("invoice_date", "<=", today)])
        billed = collected = 0
        overdue = 0
        for invoice in invoices:
            paid = max(0, invoice.amount_total - invoice.amount_residual)
            billed += invoice.amount_total
            collected += paid
            if invoice.invoice_date_due and invoice.invoice_date_due < today and invoice.amount_residual > 0:
                overdue += 1
            bucket = monthly[str(invoice.invoice_date)[:7]]
            bucket["billed"] += invoice.amount_total
            bucket["collected"] += paid
        trend = [{"month": key, "attendance": percent(value["present"], value["sessions"]),
                  "collection": percent(value["collected"], value["billed"])}
                 for key, value in sorted(monthly.items())[-6:]]
        threshold = company.campus_attendance_threshold
        shortage = sum(row["present"] * 100 < threshold * row["sessions"] for row in students.values())
        department_rows = [{"name": name, "rate": percent(row["present"], row["sessions"])}
                           for name, row in sorted(departments.items())]
        plans = records("campus.teaching.plan", [("planned_date", "<=", today)] +
                        ([("term_id.academic_year_id", "=", year.id)] if year else []))
        planned_hours = sum(plans.mapped("planned_hours"))
        delivered_hours = sum(min(plan.actual_hours, plan.planned_hours) for plan in plans if plan.execution_date and plan.execution_date <= today)
        exams = records("op.exam", [("state", "!=", "cancel")] + ([("campus_year_id", "=", year.id)] if year else []))
        sessions = records("op.session", [("state", "!=", "cancel")] +
                           ([("batch_id.campus_year_id", "=", year.id)] if year else []))
        candidates = records("campus.placement.candidate", [])
        candidate_ids = set(candidates.mapped("student_id").ids)
        selected_ids = set(candidates.filtered(lambda row: row.state == "selected").mapped("student_id").ids)
        counseling = records("campus.counseling", [("follow_up_date", "!=", False), ("follow_up_date", "<=", today)])
        at_risk = {student_id for student_id, row in students.items()
                   if row["present"] * 100 < threshold * row["sessions"]}
        reviewed = at_risk & set(counseling.mapped("student_id").ids)
        upcoming = exams.filtered(lambda row: row.start_time and row.start_time >= fields.Datetime.now()).sorted("start_time")[:1]
        admissions = records("op.admission", [("campus_managed", "=", True),
                                              ("campus_stage", "in", ["submitted", "documents", "review"])])
        insights = []
        below = [row for row in department_rows if row["rate"] is not None and row["rate"] < threshold]
        if below:
            insights.append({"title": _("Attendance needs attention"), "text": _("%(count)s departments are below the %(rate)s%% threshold. Review their attendance registers.", count=len(below), rate=threshold), "tag": _("PRIORITY · ACADEMICS"), "action": "ideastone_erp.mvp_report_attendance", "icon": "↗"})
        if overdue:
            insights.append({"title": _("Fee follow-up opportunity"), "text": _("%(count)s posted student invoices are overdue with an outstanding balance.", count=overdue), "tag": _("HIGH IMPACT · FINANCE"), "action": "ideastone_erp.mvp_report_dues", "icon": "₹"})
        if admissions:
            insights.append({"title": _("Admissions review queue"), "text": _("%(count)s managed applications await review.", count=len(admissions)), "tag": _("ACTION SUGGESTED · ADMISSIONS"), "action": "ideastone_erp.action_admissions_overview", "icon": "◷"})
        return {
            "year": year.name if year else _("No current academic year"),
            "semester": term.name if term else _("No current semester"),
            "students": len(records("op.student", [("active", "=", True)])),
            "faculty": len(records("op.faculty", [("active", "=", True)])),
            "programmes": len(records("op.course", [("active", "=", True)])),
            "fee_billed": round(billed, 2), "fee_collected": round(collected, 2), "fee_rate": percent(collected, billed),
            "currency": company.currency_id.symbol, "overdue": overdue,
            "trend": trend, "attendance_rate": percent(sum(v["present"] for v in students.values()), sum(v["sessions"] for v in students.values())),
            "departments": department_rows, "threshold": threshold, "shortage": shortage,
            "readiness": [
                {"name": _("Syllabus completion"), "value": percent(delivered_hours, planned_hours), "note": _("Delivered hours / planned hours due")},
                {"name": _("Internal marks submitted"), "value": percent(len(exams.filtered(lambda e: e.state == "done")), len(exams)), "note": _("Completed exams / recorded exams")},
                {"name": _("Exam-cell readiness"), "value": percent(len(exams.filtered(lambda e: e.campus_schedule_published)), len(exams)), "note": _("Published schedules / recorded exams")},
                {"name": _("Timetable publication"), "value": percent(len(sessions.filtered(lambda s: s.state in ("confirm", "done"))), len(sessions)), "note": _("Confirmed sessions / recorded sessions")},
            ],
            "mentoring_rate": percent(len(reviewed), len(at_risk)),
            "placement": {"rate": percent(len(selected_ids), len(candidate_ids)), "placed": len(selected_ids),
                          "seeking": len(candidate_ids - selected_ids), "total": len(candidate_ids)},
            "operations": [
                {"name": _("Fee collection"), "value": percent(collected, billed)},
                {"name": _("Timetable published"), "value": percent(len(sessions.filtered(lambda s: s.state in ("confirm", "done"))), len(sessions))},
                {"name": _("Exam readiness"), "value": percent(len(exams.filtered(lambda e: e.campus_schedule_published)), len(exams))},
                {"name": _("Staff attendance"), "value": None},
            ],
            "upcoming_exam": {"name": upcoming.name, "date": str(upcoming.start_time)[:10]} if upcoming else None,
            "insights": insights,
        }


class PrincipalNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _is_mvp_user(self):
        return super()._is_mvp_user() or self.env.user.has_group("ideastone_principal.group_principal")

    def _client_action_models(self):
        return dict(super()._client_action_models(),
                    **{"ideastone_principal.action_principal_overview": "ideastone.principal.request",
                       "ideastone_principal.action_principal_decisions": "ideastone.principal.request",
                       "ideastone_principal.action_principal_notices_workspace": "ideastone.principal.notice"})

    def _owner_modules(self):
        modules = super()._owner_modules()
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            return modules
        selected = {"admissions", "students", "academics", "staff", "attendance",
                    "exams", "fees", "learning", "calendar", "communication", "reports"}
        modules = [(key, label, icon, entries) for key, label, icon, entries in modules if key in selected]
        return [
            ("home", "Principal overview", "home", [("Overview", "ideastone_principal.action_principal_overview")]),
            ("decisions", "Decisions", "check-square-o", [
                ("Pending decisions", "ideastone_principal.action_principal_decisions"),
                ("Student leave approvals", "ideastone_erp.action_student_leave")]),
            *modules,
            ("principal_notices", "Principal notices", "bullhorn", [("Notices & circulars", "ideastone_principal.action_principal_notices_workspace")]),
        ]

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self.env.user.has_group("ideastone_principal.group_principal"):
            data.update(is_principal_workspace=True, workspace_role="Principal", is_admin=False)
        return data
