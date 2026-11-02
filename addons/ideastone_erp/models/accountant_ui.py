from collections import defaultdict
from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

ACCOUNTANT_MODULES = [
    ("home", "Dashboard", "home", [("Accounts overview", "accountant-overview")]),
    ("students", "Students & dues", "graduation-cap", [
        ("Student fee directory", "accountant_directory_students"),
        ("Pending fee students", "accountant_directory_pending"),
        ("Student fee accounts", "accountant_directory_accounts"),
    ]),
    ("collections", "Collections", "inr", [
        ("Overview", "accountant-collections-overview"),
        ("Fee structures", "mvp_structures"),
        ("Assign fee structure", "mvp_assign_fees"),
        ("Invoices", "mvp_invoices"),
        ("Receipts", "mvp_receipts"),
        ("Collection report", "mvp_report_collection"),
        ("Dues report", "mvp_report_dues"),
        ("Export files", "accountant-collections-exports"),
    ]),
    ("transport", "Transport billing", "bus", [
        ("Transport overview", "accountant_transport_dashboard"),
        ("Transport fee bills", "accountant_transport"),
    ]),
    ("spending", "Spending", "credit-card", [
        ("Event bills", "accountant_spending_events"),
        ("Maintenance bills", "accountant_spending_maintenance"),
    ]),
    ("communication", "Fee circulars", "bullhorn", [
        ("Fee related circulars", "accountant_notices"),
    ]),
]


def _current_enrolment(student, year_id=0):
    return student.course_detail_ids.filtered(lambda e: e.state == "running" and
        (not year_id or e.academic_years_id.id == year_id)).sorted(
            key=lambda e: e.academic_term_id.term_start_date or e.academic_years_id.start_date or date.min,
            reverse=True)[:1]


class AccountantDashboard(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _accountant_only(self):
        user = self.env.user
        return user.has_group("ideastone_erp.group_mvp_accountant") and not (
            user.has_group("ideastone_erp.group_mvp_owner")
            or user.has_group("ideastone_erp.group_mvp_registrar")
            or user.has_group("ideastone_erp.group_manager")
        )

    def _accountant_access(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
            raise AccessError(_("College accountant permission is required."))

    def _owner_modules(self):
        modules = super()._owner_modules()
        if self._accountant_only():
            return ACCOUNTANT_MODULES
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant"):
            return modules
        owner_accounts = [("Accounts summary", "accountant-overview"), ("Student fee directory", "accountant_directory_students"),
            ("Pending fee students", "accountant_directory_pending"), ("Transport fee bills", "accountant_transport"),
            ("Event & maintenance bills", "accountant_expenses"), ("Fee circulars", "accountant_notices")]
        return modules + [("accounts", "Accounts", "ledger", owner_accounts)]

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self._accountant_only():
            data.update(workspace_role="Accountant", is_accountant_workspace=True, report_allowed=False)
        return data

    @api.model
    def get_accountant_metrics(self, filters=None):
        self._accountant_access()
        f = self._mvp_filters(filters)
        company = [("company_id", "=", self.env.company.id)]
        departments = self.env["op.department"].search(
            ["|", ("company_id", "=", False), ("company_id", "=", self.env.company.id)], order="name")
        department_id = f["department_id"]
        if department_id and department_id not in departments.ids:
            raise AccessError(_("Select a department in the active college."))
        sale_types = {"out_invoice", "out_refund"}
        vendor_types = {"in_invoice", "in_refund"}

        def in_department(move):
            if not department_id:
                return True
            if move.move_type in sale_types:
                return move.campus_course_id.department_id.id == department_id
            return move.campus_spend_department_id.id == department_id

        def receipt_in_department(payment):
            return not department_id or payment.campus_invoice_id.campus_course_id.department_id.id == department_id

        period = [("invoice_date", ">=", f["date_from"]), ("invoice_date", "<=", f["date_to"])]
        moves = self._mvp_records("account.move", company + period + [("state", "=", "posted"),
            ("move_type", "in", list(sale_types | vendor_types))]).filtered(in_department)
        paid = self._mvp_records(*self._mvp_source("collection", f)).filtered(receipt_in_department)
        collections = sum(p.amount for p in paid if f["date_from"] <= p.date <= f["date_to"])
        collections -= sum(p.amount for p in paid if p.campus_reversal_id and f["date_from"] <= p.campus_reversal_id.date <= f["date_to"])
        income = sum(m.amount_total * (1 if m.move_type == "out_invoice" else -1)
                     for m in moves if m.move_type in sale_types)
        outgoing = sum(m.amount_total * (1 if m.move_type == "in_invoice" else -1)
                       for m in moves if m.move_type in vendor_types)
        bills = moves.filtered(lambda m: m.move_type in vendor_types)
        spend = defaultdict(float)
        for bill in bills:
            spend[bill.campus_spend_category or "unclassified"] += bill.amount_total * (1 if bill.move_type == "in_invoice" else -1)

        due_model, due_domain = self._mvp_source("dues", f)
        due_moves = self._mvp_records(due_model, due_domain).filtered(in_department)
        due_rows = self._mvp_report_rows("dues", f, due_moves)
        pending = defaultdict(lambda: {"amount": 0.0, "overdue": 0, "invoices": 0})
        for row in due_rows:
            # The report row already applies the selected as-of date and reversals.
            invoice = self.env["account.move"].browse(row["id"])
            item = pending[invoice.campus_student_id.id]
            item["amount"] += row["balance"]
            item["overdue"] += int(row["days_overdue"] > 0)
            item["invoices"] += 1
        students = self.env["op.student"].browse(list(pending))
        student_rows = []
        for student in students:
            enrolment = _current_enrolment(student, f["year_id"])
            amount = pending[student.id]
            student_rows.append({"id": student.id, "name": student.name, "number": student.gr_no or student.register_no or "",
                "department": enrolment.course_id.department_id.name or "", "semester": enrolment.academic_term_id.name or "",
                "pending": amount["amount"], "overdue": amount["overdue"], "invoices": amount["invoices"]})
        student_rows.sort(key=lambda row: (-row["pending"], row["name"]))

        allocations = self._mvp_records("campus.transport.allocation", company + [("state", "=", "approved")], limit=50000)
        if department_id:
            allocations = allocations.filtered(lambda a: _current_enrolment(a.student_id).course_id.department_id.id == department_id)
        transport = [{"id": a.id, "student": a.student_id.name, "route": a.route_id.name,
                      "fee": a.stop_id.fee, "invoice": a.invoice_id.name or "",
                      "pending": a.invoice_id.amount_residual if a.invoice_id.state == "posted" else 0,
                      "status": "Not billed" if not a.invoice_id else "Draft" if a.invoice_id.state == "draft"
                          else "Paid" if a.invoice_id.amount_residual <= 0 else "Pending"}
                     for a in allocations if not f["year_id"] or a.year_id.id == f["year_id"]]
        notices = self.env["campus.circular"].search(company + [("campus_category", "=", "Fees")], order="date_from desc", limit=6)
        all_bills = self._mvp_records("account.move", company + period + [
            ("move_type", "in", list(vendor_types)), ("state", "!=", "cancel")]).filtered(in_department)
        draft_bills = all_bills.filtered(lambda bill: bill.state == "draft")

        # A fixed 12-month window lets the selector change the chart without a second RPC.
        trend_start = fields.Date.subtract(f["date_to"].replace(day=1), months=11)
        trend_filters = dict(f, date_from=trend_start)
        trend_receipts = self._mvp_records(*self._mvp_source("collection", trend_filters)).filtered(receipt_in_department)
        trend_invoices = self._mvp_records("account.move", company + [
            ("invoice_date", ">=", trend_start), ("invoice_date", "<=", f["date_to"]),
            ("state", "=", "posted"), ("move_type", "in", list(sale_types))]).filtered(in_department)
        trend = [{"month": fields.Date.add(trend_start, months=i).strftime("%Y-%m"),
                  "label": fields.Date.add(trend_start, months=i).strftime("%b"),
                  "collections": 0.0, "income": 0.0} for i in range(12)]
        by_month = {row["month"]: row for row in trend}
        for payment in trend_receipts:
            if trend_start <= payment.date <= f["date_to"]:
                by_month[payment.date.strftime("%Y-%m")]["collections"] += payment.amount
            reversal = payment.campus_reversal_id
            if reversal and trend_start <= reversal.date <= f["date_to"]:
                by_month[reversal.date.strftime("%Y-%m")]["collections"] -= payment.amount
        for invoice in trend_invoices:
            by_month[invoice.invoice_date.strftime("%Y-%m")]["income"] += invoice.amount_total * (
                1 if invoice.move_type == "out_invoice" else -1)

        pending_total = sum(row["balance"] for row in due_rows)
        overdue_total = sum(row["balance"] for row in due_rows if row["days_overdue"] > 0)
        billed_total = sum(move.amount_total for move in due_moves)
        overdue_30 = len({self.env["account.move"].browse(row["id"]).campus_student_id.id
                          for row in due_rows if row["days_overdue"] > 30})
        activity = []
        for payment in paid:
            if f["date_from"] <= payment.date <= f["date_to"]:
                activity.append({"id": f"receipt-{payment.id}", "reference": payment.campus_receipt_number,
                    "name": "Student fee receipt", "detail": payment.campus_invoice_id.campus_student_id.name or "Fee collection",
                    "amount": payment.amount, "date": str(payment.date), "status": "Posted"})
            reversal = payment.campus_reversal_id
            if reversal and f["date_from"] <= reversal.date <= f["date_to"]:
                activity.append({"id": f"reversal-{payment.id}", "reference": payment.campus_receipt_number,
                    "name": "Receipt reversal", "detail": payment.campus_invoice_id.campus_student_id.name or "Fee collection",
                    "amount": -payment.amount, "date": str(reversal.date), "status": "Reversed"})
        for bill in all_bills:
            activity.append({"id": f"bill-{bill.id}", "reference": bill.name if bill.name != "/" else bill.ref or "Draft bill",
                "name": bill.ref or bill.partner_id.name or "Vendor bill", "detail": bill.partner_id.name or "Vendor invoice",
                "amount": bill.amount_total * (1 if bill.move_type == "in_invoice" else -1),
                "date": str(bill.invoice_date or bill.date),
                "status": "Draft" if bill.state == "draft" else "Paid" if bill.payment_state == "paid" else "Posted"})
        activity.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
        return {
            "currency": self.env.company.currency_id.symbol,
            "period": {"from": str(f["date_from"]), "to": str(f["date_to"])},
            "departments": [{"id": department.id, "name": department.name} for department in departments],
            "selected_department": department_id,
            "cards": [
                {"key": "collections", "label": "Fee collections", "value": collections, "detail": "Receipts less reversals in period", "pill": "This period"},
                {"key": "income", "label": "Billed income", "value": income, "detail": "Posted invoices less credits", "pill": "This period"},
                {"key": "dues", "label": "Outstanding dues", "value": pending_total, "detail": f"{len(student_rows)} student accounts pending", "pill": "Due now" if pending_total else "Clear"},
                {"key": "spending", "label": "Recorded spending", "value": outgoing, "detail": f"Across {len(bills)} posted vendor bills", "pill": "Recorded"},
            ],
            "trend": trend,
            "collection_status": {"collected": max(0.0, billed_total - pending_total),
                "pending": max(0.0, pending_total - overdue_total), "overdue": overdue_total,
                "total": billed_total, "overdue_30": overdue_30},
            "activity": activity[:6],
            "queue": [
                {"key": "dues", "title": "Outstanding student dues", "count": len(student_rows),
                 "detail": f"{len(student_rows)} student accounts · {self._mvp_money(pending_total)} remaining",
                 "hint": "Prioritize overdue balances", "action": "accountant_directory_pending"},
                {"key": "bills", "title": "Draft vendor bills to review", "count": len(draft_bills),
                 "detail": f"{len(draft_bills)} bills · {self._mvp_money(sum(b.amount_total for b in draft_bills))} total",
                 "hint": "Check evidence and category", "action": "accountant_expenses"},
                {"key": "transport", "title": "Transport allocations to bill", "count": sum(1 for row in transport if not row["invoice"]),
                 "detail": f"{sum(1 for row in transport if not row['invoice'])} approved allocations not billed",
                 "hint": "Create linked fee invoices", "action": "accountant_transport"},
                {"key": "circulars", "title": "Fee circulars in draft", "count": self.env["campus.circular"].search_count(
                    company + [("campus_category", "=", "Fees"), ("campus_status", "=", "draft")]),
                 "detail": "Review fee notices before publishing", "hint": "Open circular records", "action": "accountant_notices"},
            ],
            "pending_count": len(student_rows),
            "pending": student_rows[:10],
            "transport_unbilled": sum(1 for row in transport if not row["invoice"]),
            "transport": transport[:8],
            "spending": [{"label": key.title(), "value": spend[key]} for key in ("event", "maintenance", "other", "unclassified")],
            "recent_bills": [{"id": m.id, "name": m.name, "vendor": m.partner_id.name, "date": str(m.invoice_date),
                              "category": (m.campus_spend_category or "unclassified").title(), "amount": m.amount_total}
                             for m in bills.sorted("invoice_date", reverse=True)[:8]],
            "notices": [{"id": n.id, "name": n.name, "date": str(n.date_from), "status": n.campus_status} for n in notices],
        }

    @api.model
    def get_accountant_collections_overview(self, filters=None):
        """Live figures for the Collections landing page, scoped to the active college."""
        self._accountant_access()
        f = self._mvp_filters(filters)
        company_id = self.env.company.id
        departments = self.env["op.department"].search([
            "|", ("company_id", "=", False), ("company_id", "=", company_id)], order="name")
        if f["department_id"] and f["department_id"] not in departments.ids:
            raise AccessError(_("Select a department in the active college."))

        def matching_department(record):
            return not f["department_id"] or record.campus_course_id.department_id.id == f["department_id"]

        invoices = self._mvp_records("account.move", [
            ("company_id", "=", company_id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("campus_student_id", "!=", False),
            ("invoice_date", ">=", f["date_from"]), ("invoice_date", "<=", f["date_to"]),
        ]).filtered(matching_department)
        all_dues = self._mvp_records(*self._mvp_source("dues", f)).filtered(matching_department)
        due_rows = self._mvp_report_rows("dues", f, all_dues)
        balances = {row["id"]: row for row in due_rows}
        billed = sum(invoice.amount_total for invoice in invoices)
        open_period = sum(balances[invoice.id]["balance"] for invoice in invoices if invoice.id in balances)
        overdue_period = sum(balances[invoice.id]["balance"] for invoice in invoices
                             if invoice.id in balances and balances[invoice.id]["days_overdue"] > 0)
        collected_period = max(0.0, billed - open_period)

        def receipts(start, end):
            receipt_filters = dict(f, date_from=start, date_to=end)
            payments = self._mvp_records(*self._mvp_source("collection", receipt_filters)).filtered(
                lambda payment: matching_department(payment.campus_invoice_id))
            amount = sum(payment.amount for payment in payments if start <= payment.date <= end)
            amount -= sum(payment.amount for payment in payments if payment.campus_reversal_id
                          and start <= payment.campus_reversal_id.date <= end)
            return payments, amount

        payments, collected_month = receipts(f["date_from"], f["date_to"])
        previous_start = fields.Date.subtract(f["date_from"], months=1)
        previous_end = f["date_from"] - timedelta(days=1)
        _, previous_collected = receipts(previous_start, previous_end)
        change = round((collected_month - previous_collected) / previous_collected * 100, 1) if previous_collected else None
        semester = self.env["op.academic.term"].search([
            ("company_id", "=", company_id), ("term_start_date", "<=", f["date_to"]),
            ("term_end_date", ">=", f["date_to"]),
        ], order="term_start_date desc", limit=1)
        semester_start = semester.term_start_date if semester else fields.Date.subtract(f["date_to"], months=6)
        semester_start = min(semester_start, f["date_to"])
        _, collected_semester = receipts(semester_start, f["date_to"])

        by_department = {department.id: {"id": department.id, "name": department.name,
                         "billed": 0.0, "collected": 0.0} for department in departments}
        for invoice in invoices:
            department = invoice.campus_course_id.department_id
            key = department.id or 0
            if key not in by_department:
                by_department[key] = {"id": key, "name": department.name or "Unassigned", "billed": 0.0, "collected": 0.0}
            by_department[key]["billed"] += invoice.amount_total
            by_department[key]["collected"] += invoice.amount_total - balances.get(invoice.id, {}).get("balance", 0.0)
        department_rows = [dict(row, rate=round(row["collected"] / row["billed"] * 100) if row["billed"] else 0)
                           for row in by_department.values() if row["billed"]]
        department_rows.sort(key=lambda row: row["name"])
        if f["department_id"]:
            department_rows = [row for row in department_rows if row["id"] == f["department_id"]]

        outstanding = sum(row["balance"] for row in due_rows)
        overdue = sum(row["balance"] for row in due_rows if row["days_overdue"] > 0)
        students_due = len({self.env["account.move"].browse(row["id"]).campus_student_id.id for row in due_rows})
        recent = [{"id": payment.id, "reference": payment.campus_receipt_number,
                   "student": payment.campus_invoice_id.campus_student_id.name or "Student fee receipt",
                   "date": str(payment.date), "amount": payment.amount} for payment in payments
                  if f["date_from"] <= payment.date <= f["date_to"]]
        recent.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
        recent_invoices = [{"id": invoice.id, "reference": invoice.name,
                            "student": invoice.campus_student_id.name,
                            "department": invoice.campus_course_id.department_id.name or "",
                            "amount": invoice.amount_total,
                            "due": str(invoice.invoice_date_due or invoice.invoice_date),
                            "status": "Paid" if invoice.id not in balances else
                                      "Overdue" if balances[invoice.id]["days_overdue"] > 0 else "Pending"}
                           for invoice in invoices.sorted("invoice_date", reverse=True)[:4]]
        return {
            "currency": self.env.company.currency_id.symbol,
            "period": {"from": str(f["date_from"]), "to": str(f["date_to"]),
                       "label": f["date_to"].strftime("%b · %Y").upper()},
            "departments": [{"id": department.id, "name": department.name} for department in departments],
            "collected_month": collected_month, "collected_semester": collected_semester,
            "previous_change": change, "semester_label": semester.name if semester else "Last six months",
            "outstanding": outstanding, "overdue": overdue, "students_due": students_due,
            "invoice_count": len(invoices),
            "status": {"billed": billed, "collected": collected_period,
                       "pending": max(0.0, open_period - overdue_period), "overdue": overdue_period},
            "by_department": department_rows, "recent": recent[:4], "recent_invoices": recent_invoices,
        }

    @api.model
    def get_accountant_collection_records(self, screen, year_id=0):
        """Records for the accountant's Collections tabs; native actions remain the editors."""
        self._accountant_access()
        screens = {"structures", "assign", "invoices", "receipts", "reports", "dues", "exports"}
        if screen not in screens or isinstance(year_id, bool):
            raise ValidationError(_("Select a valid Collections page."))
        try:
            year_id = int(year_id or 0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError(_("Select a valid academic year.")) from exc
        company = self.env.company
        years = self.env["op.academic.year"].search([("company_id", "=", company.id)], order="start_date desc")
        if year_id and year_id not in years.ids:
            raise AccessError(_("Select an academic year in the active college."))
        scope = [("company_id", "=", company.id)]
        rows = []

        def add(record_id, cells, status=""):
            rows.append({"id": record_id, "cells": cells, "status": status})

        def metric(value, label, detail, color="blue", money=False):
            return {"value": value, "label": label, "detail": detail, "color": color, "money": money}

        if screen == "structures":
            domain = scope + [("campus_managed", "=", True)]
            if year_id:
                domain.append(("campus_year_id", "=", year_id))
            plans = self._mvp_records("op.fees.terms", domain).sorted("id", reverse=True)
            for plan in plans[:200]:
                status = "Active" if plan.active and plan.line_ids else "Draft"
                heads = ", ".join(plan.line_ids.campus_product_id.mapped("name")) or "Not configured"
                add(plan.id, [f"FEE-{plan.id:05d}", plan.name, heads,
                              plan.campus_course_id.name or "All programmes", plan.campus_year_id.name or "—",
                              len(plan.line_ids), status], status)
            columns = ["Structure ID", "Fee structure", "Fee head", "Applies to", "Academic year", "Installments", "Status"]
            metrics = [metric(sum(sum(line.campus_amount for line in plan.line_ids) for plan in plans), "Scheduled fee value", "Across saved structures", money=True),
                       metric(len(plans.filtered(lambda plan: plan.active and plan.line_ids)), "Active structures", "Ready for assignment", "green"),
                       metric(len(plans.filtered(lambda plan: not plan.line_ids)), "Draft plans", "Add fee installments before assignment", "amber")]
        elif screen == "assign":
            domain = scope + [("campus_managed", "=", True)]
            if year_id:
                domain.append(("campus_year_id", "=", year_id))
            fees = self._mvp_records("op.student.fees.details", domain).sorted("id", reverse=True)
            for fee in fees[:200]:
                plan = fee.fees_line_id.fees_id
                status = "Invoiced" if fee.invoice_id else "Assigned"
                add(fee.id, [f"ASG-{fee.id:05d}", fee.student_id.name,
                             fee.course_id.department_id.name or fee.course_id.name or "—",
                             plan.name or "—", str(fee.date or ""), status], status)
            columns = ["Assignment ID", "Student", "Department", "Fee structure", "Effective date", "Status"]
            metrics = [metric(len(fees), "Fee installments assigned", "Saved student fee records"),
                       metric(len(fees.student_id), "Students covered", "With a fee assignment", "green"),
                       metric(sum(fee.amount for fee in fees), "Assigned amount", "Before concessions", "amber", True)]
        elif screen in {"invoices", "reports", "dues"}:
            domain = scope + [("campus_student_id", "!=", False), ("move_type", "=", "out_invoice")]
            if year_id:
                domain.append(("campus_year_id", "=", year_id))
            invoices = self._mvp_records("account.move", domain).sorted(key=lambda invoice: (invoice.invoice_date or date.min, invoice.id), reverse=True)
            today = fields.Date.context_today(self)
            posted = invoices.filtered(lambda invoice: invoice.state == "posted")
            if screen == "invoices":
                for invoice in invoices[:200]:
                    due = invoice.invoice_date_due or invoice.invoice_date
                    status = "Draft" if invoice.state == "draft" else "Cancelled" if invoice.state == "cancel" else "Paid" if invoice.amount_residual <= 0 else "Overdue" if due and due < today else "Pending"
                    add(invoice.id, [invoice.name if invoice.name != "/" else "Draft", invoice.campus_student_id.name,
                                     invoice.campus_course_id.department_id.name or "—", invoice.amount_total,
                                     str(due or ""), status], status)
                columns = ["Invoice ID", "Student", "Department", "Amount", "Due date", "Status"]
                metrics = [metric(len(invoices), "Invoices issued", "Saved student invoices"),
                           metric(sum(invoice.amount_total for invoice in posted), "Total billed", "Posted invoices", "green", True),
                           metric(sum(invoice.amount_residual for invoice in posted), "Open balance", "Pending and overdue", "amber", True)]
            elif screen == "dues":
                due_invoices = posted.filtered(lambda invoice: invoice.amount_residual > 0)
                for invoice in due_invoices[:200]:
                    due = invoice.invoice_date_due or invoice.invoice_date
                    days = max(0, (today - due).days) if due else 0
                    status = "Overdue" if days else "Pending"
                    add(invoice.id, [invoice.name, invoice.campus_student_id.name,
                                     invoice.campus_course_id.department_id.name or "—", invoice.amount_residual,
                                     str(due or ""), f"{days} days" if days else "Not overdue", status], status)
                columns = ["Invoice ID", "Student", "Department", "Balance", "Due date", "Aging", "Follow-up"]
                metrics = [metric(sum(invoice.amount_residual for invoice in due_invoices), "Open balance", "Across unpaid invoices", money=True),
                           metric(len(due_invoices.filtered(lambda invoice: bool(invoice.invoice_date_due or invoice.invoice_date) and (invoice.invoice_date_due or invoice.invoice_date) < today)), "Overdue invoices", "Past due date", "amber"),
                           metric(len(due_invoices), "Accounts to review", "Reconcile before follow-up", "green")]
            else:
                departments = defaultdict(lambda: {"billed": 0.0, "collected": 0.0, "outstanding": 0.0})
                for invoice in posted:
                    name = invoice.campus_course_id.department_id.name or "Unassigned"
                    departments[name]["billed"] += invoice.amount_total
                    departments[name]["collected"] += invoice.amount_total - invoice.amount_residual
                    departments[name]["outstanding"] += invoice.amount_residual
                for index, (name, values) in enumerate(sorted(departments.items())):
                    rate = round(values["collected"] / values["billed"] * 100) if values["billed"] else 0
                    add(index, [name, values["billed"], values["collected"], values["outstanding"], f"{rate}%"])
                columns = ["Department", "Billed", "Collected", "Outstanding", "Collection rate"]
                metrics = [metric(sum(invoice.amount_total for invoice in posted), "Total billed", "Posted student invoices", money=True),
                           metric(sum(invoice.amount_total - invoice.amount_residual for invoice in posted), "Collected", "Against posted invoices", "green", True),
                           metric(sum(invoice.amount_residual for invoice in posted), "Open balance", "Reconcile with receipts", "amber", True)]
        elif screen == "receipts":
            domain = scope + [("campus_receipt_number", "!=", False)]
            if year_id:
                domain.append(("campus_invoice_id.campus_year_id", "=", year_id))
            receipts = self._mvp_records("account.payment", domain).sorted(key=lambda payment: (payment.date or date.min, payment.id), reverse=True)
            for payment in receipts[:200]:
                status = "Reversed" if payment.campus_reversal_id else "Posted"
                add(payment.id, [payment.campus_receipt_number, str(payment.date or ""),
                                 payment.campus_invoice_id.campus_student_id.name or payment.partner_id.name,
                                 payment.campus_invoice_id.name or "—", payment.amount,
                                 dict(payment._fields["campus_method"].selection).get(payment.campus_method, "—"),
                                 payment.campus_cashier_id.name or "—", status], status)
            columns = ["Receipt ID", "Date", "Payer", "Invoice ref", "Amount", "Method", "Cashier", "Status"]
            metrics = [metric(sum(payment.amount * (-1 if payment.campus_reversal_id else 1) for payment in receipts), "Net receipts", "After reversals", money=True),
                       metric(len(receipts), "Receipts recorded", "Saved collection records", "green"),
                       metric(len(receipts.filtered("campus_reversal_id")), "Reversed receipts", "Check reconciliation", "amber")]
        else:
            columns = []
            metrics = [metric(3, "Export datasets", "Invoices, receipts and dues"),
                       metric("CSV", "File format", "Spreadsheet ready", "green"),
                       metric("Scoped", "Academic year", "Uses the selected college", "amber")]

        money_columns = {"invoices": [3], "receipts": [4], "reports": [1, 2, 3], "dues": [3]}
        date_columns = {"assign": [4], "invoices": [4], "receipts": [1], "dues": [4]}
        return {"screen": screen, "columns": columns, "rows": rows,
                "years": [{"id": year.id, "name": year.name} for year in years],
                "metrics": metrics, "total": len(rows), "currency": company.currency_id.symbol,
                "money_columns": money_columns.get(screen, []), "date_columns": date_columns.get(screen, [])}


class AccountantExpense(models.Model):
    _inherit = "account.move"

    campus_spend_department_id = fields.Many2one("op.department", string="Spending department", index=True)
    campus_spend_category = fields.Selection([
        ("event", "College event"), ("maintenance", "Maintenance"), ("other", "Other"),
    ], string="College spending category", index=True)

    @api.constrains("campus_spend_category", "move_type")
    def _check_spend_category(self):
        if any(m.campus_spend_category and m.move_type not in {"in_invoice", "in_refund"} for m in self):
            raise ValidationError(_("Classify spending on vendor bills or vendor credits only."))


class AccountantStudent(models.Model):
    _inherit = "op.student"

    campus_fee_currency_id = fields.Many2one("res.currency", compute="_compute_accountant_directory")
    campus_fee_pending = fields.Monetary(compute="_compute_accountant_directory", search="_search_campus_fee_pending",
        currency_field="campus_fee_currency_id")
    campus_fee_status = fields.Char(compute="_compute_accountant_directory")
    campus_current_department = fields.Char(compute="_compute_accountant_directory")
    campus_current_semester = fields.Char(compute="_compute_accountant_directory")

    def _compute_accountant_directory(self):
        invoices = self.env["account.move"].search([("campus_student_id", "in", self.ids),
            ("company_id", "=", self.env.company.id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("amount_residual", ">", 0)])
        balances = defaultdict(float)
        overdue = set()
        today = fields.Date.context_today(self)
        for invoice in invoices:
            balances[invoice.campus_student_id.id] += invoice.amount_residual
            if (invoice.invoice_date_due or invoice.invoice_date or invoice.date) < today:
                overdue.add(invoice.campus_student_id.id)
        for student in self:
            enrolment = _current_enrolment(student)
            student.campus_fee_currency_id = self.env.company.currency_id
            student.campus_fee_pending = balances[student.id]
            student.campus_fee_status = "Overdue" if student.id in overdue else "Pending" if balances[student.id] else "Clear"
            student.campus_current_department = enrolment.course_id.department_id.name or ""
            student.campus_current_semester = enrolment.academic_term_id.name or ""

    def _search_campus_fee_pending(self, operator, value):
        if operator != ">" or value != 0:
            raise ValidationError(_("Filter pending fees using an amount greater than zero."))
        invoices = self.env["account.move"].search([("campus_student_id", "!=", False),
            ("company_id", "=", self.env.company.id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("amount_residual", ">", 0)])
        return [("id", "in", invoices.campus_student_id.ids)]


class AccountantTransport(models.Model):
    _inherit = "campus.transport.allocation"

    def write(self, vals):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not (
            self.env.user.has_group("ideastone_erp.group_manager") or
            self.env.user.has_group("ideastone_erp.group_mvp_owner") or
            self.env.user.has_group("ideastone_erp.group_services")
        ):
            raise AccessError(_("The accountant may bill approved transport allocations, but may not edit them."))
        return super().write(vals)

    def action_invoice(self):
        if not (self.env.user.has_group("ideastone_erp.group_mvp_accountant") or
                self.env.user.has_group("ideastone_erp.group_manager")):
            raise AccessError(_("Transport billing requires accountant permission."))
        return super().action_invoice()


class AccountantTransportStop(models.Model):
    _inherit = "campus.transport.stop"

    fee_product_id = fields.Many2one("product.product", string="Transport fee product",
        domain="[('campus_fee_head','=',True)]", check_company=True)


class AccountantNotice(models.Model):
    _inherit = "campus.circular"

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            for vals in vals_list:
                vals.setdefault("campus_category", "Fees")
                vals.setdefault("campus_managed", True)
                if (vals.get("campus_category") != "Fees" or not vals.get("campus_managed")
                        or vals.get("company_id", self.env.company.id) != self.env.company.id
                        or vals.get("audience", "student") not in {"student", "parent", "all"}
                        or any(vals.get(key) for key in ("campus_course_id", "campus_batch_id", "campus_group_id"))):
                    raise AccessError(_("Accountants may create fee circulars in the active college only."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.user.has_group("ideastone_erp.group_mvp_accountant") and not self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            if (any(n.campus_category != "Fees" or n.company_id != self.env.company for n in self)
                    or vals.get("campus_category", "Fees") != "Fees"
                    or vals.get("company_id", self.env.company.id) != self.env.company.id
                    or vals.get("audience", "student") not in {"student", "parent", "all"}
                    or any(vals.get(key) for key in ("campus_course_id", "campus_batch_id", "campus_group_id"))):
                raise AccessError(_("Accountants may edit fee circulars only."))
        return super().write(vals)

    def action_campus_publish(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant") or self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            return super().action_campus_publish()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.company_id != self.env.company or rec.campus_category != "Fees" or rec.campus_status != "draft" or rec.date_to and rec.date_to < today:
                raise ValidationError(_("Publish an unexpired draft fee circular in the active college."))
            rec._lock()
            future = rec.date_from > today
            rec._set_system_values({"campus_status": "scheduled" if future else "published",
                "state": "submitted" if future else "approved", "approved_by": self.env.uid,
                "approved_on": fields.Datetime.now()})
            self.env["campus.mvp.audit"]._log(rec, "Fee circular scheduled" if future else "Fee circular published")
        return True

    def action_campus_archive(self):
        if not self.env.user.has_group("ideastone_erp.group_mvp_accountant") or self.env.user.has_group("ideastone_erp.group_mvp_registrar"):
            return super().action_campus_archive()
        for rec in self:
            if rec.company_id != self.env.company or rec.campus_category != "Fees":
                raise AccessError(_("Accountants may archive fee circulars in the active college only."))
            rec._lock()
            rec._set_system_values({"campus_status": "archived", "state": "done"})
            self.env["campus.mvp.audit"]._log(rec, "Fee circular archived")
        return True
