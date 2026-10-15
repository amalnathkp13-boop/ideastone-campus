import json

from odoo.exceptions import AccessError

from odoo import _, api, models, tools


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
        visible = []
        for item in navigation:
            if item["model"] in self.env and self.env[item["model"]].check_access_rights("read", raise_exception=False):
                if self.env.ref(item["action"], raise_if_not_found=False):
                    visible.append(item)
        visible.append({"label": "Learning platform", "group": "Learning", "action": "ideastone_lms.action_lms_frame", "model": "op.course"})
        stats = []
        for label, model, domain in [
            ("Active students", "op.student", [("active", "=", True)]),
            ("Faculty", "op.faculty", [("active", "=", True)]),
            ("Programmes", "op.course", []),
            ("Pending requests", "campus.service.request", [("state", "=", "submitted")]),
        ]:
            if self.env[model].check_access_rights("read", raise_exception=False):
                stats.append({"label": label, "value": self.env[model].search_count(domain)})
        return {"company": self.env.company.name, "user": self.env.user.name, "navigation": visible, "stats": stats}
