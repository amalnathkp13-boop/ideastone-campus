"""Student Success Radar: an explainable early-warning score per student.

The score is rule based and transparent on purpose. Every point is traceable to a
college record (attendance, results, fees, leave/OD, counselling) and each factor
is returned with the plain-English reason behind it, so a mentor can act on it and a
student can check it. No external service is involved.
"""
import math
from collections import Counter
from datetime import datetime, time, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

WEIGHTS = {"attendance": 40, "academics": 30, "fees": 15, "engagement": 15}
BANDS = (("high", 50), ("watch", 25), ("low", 0))


def pct(value):
    """75.0 -> '75', 72.5 -> '72.5' for messages."""
    return str(int(value)) if value is not None and float(value).is_integer() else str(value)


class SuccessRadar(models.AbstractModel):
    _name = "campus.success.radar"
    _description = "Student Success Radar (early-warning scores)"

    # ------------------------------------------------------------------ scope
    def _scope(self):
        """Return (role, student domain) for the current user, or raise."""
        user = self.env.user
        company = self.env.company
        base = [("company_id", "=", company.id), ("active", "=", True), ("campus_status", "=", "active")]
        if not user.active or not user.has_group("base.group_user"):
            raise AccessError(_("An internal staff account is required."))
        # An OD-approving HOD is scoped to their department even though the group implies the MVP HOD role.
        if any(user.has_group(group) for group in ("ideastone_erp.group_od_hod_approver", "ideastone_erp.group_mvp_hod", "ideastone_erp.group_exam_paper_hod")):
            if not user.dept_id or user.dept_id.company_id != company:
                raise AccessError(_("Assign this HOD a department in the active college before opening the radar."))
            return "hod", base + [("course_detail_ids", "any", [("state", "=", "running"), ("company_id", "=", company.id),
                                                                ("course_id.department_id", "=", user.dept_id.id)])]
        if self.env["campus.dashboard"]._is_mvp_user():
            return "owner", base
        if user.has_group("openeducat_core.group_op_faculty"):
            routes = self.env["campus.student.leave.routing"].sudo().search([
                ("advisor_id", "=", user.id), ("company_id", "=", company.id), ("active", "=", True)])
            if not routes:
                raise AccessError(_("No students are routed to you as their mentor yet."))
            return "mentor", base + [("id", "in", routes.student_id.ids)]
        raise AccessError(_("The Student Success Radar is available to college administrators, HODs and mentors."))

    # ---------------------------------------------------------------- scoring
    def _placement(self, student):
        today = fields.Date.context_today(self)
        placements = student.course_detail_ids.filtered(lambda e: e.company_id == student.company_id
            and (not e.campus_date_from or e.campus_date_from <= today)
            and (not e.campus_date_to or e.campus_date_to >= today))
        return placements.filtered(lambda e: e.state == "running").sorted(lambda e: (e.campus_date_from or fields.Date.today(), e.id), reverse=True)[:1]

    def _attendance(self, student, placement, today):
        company = student.company_id
        term = placement.academic_term_id
        start = term.term_start_date or placement.campus_date_from or today.replace(day=1)
        start = max(start, placement.campus_date_from or start)
        end = min(term.term_end_date or today, placement.campus_date_to or term.term_end_date or today)
        lines = self.env["op.attendance.line"].sudo().search([
            ("company_id", "=", company.id), ("student_id", "=", student.id), ("attendance_id.state", "=", "done"),
            ("attendance_date", ">=", start), ("attendance_date", "<=", min(end, today)),
            "|", ("attendance_id.session_id", "=", False), ("attendance_id.session_id.state", "!=", "cancel"),
        ] + ([("batch_id", "=", placement.batch_id.id)] if placement.batch_id else []))
        policy = company.campus_excused_policy
        conducted = attended = recent_conducted = recent_attended = 0
        recent_from = today - timedelta(days=28)
        for line in lines:
            if line.excused and policy == "exclude":
                continue
            present = bool(line.present or line.late or (line.excused and policy == "present"))
            conducted += 1
            attended += int(present)
            if line.attendance_date >= recent_from:
                recent_conducted += 1
                recent_attended += int(present)
        remaining = 0
        if placement.batch_id and end >= today:
            timezone = pytz.timezone(self.env.user.tz or "UTC")
            end_utc = timezone.localize(datetime.combine(end + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
            remaining = self.env["op.session"].sudo().search_count([
                ("company_id", "=", company.id), ("batch_id", "=", placement.batch_id.id), ("state", "!=", "cancel"),
                ("active", "=", True),
                ("start_datetime", ">", fields.Datetime.now()),
                ("start_datetime", "<", end_utc),
            ])
        rate = round(attended * 100 / conducted, 1) if conducted else None
        recent = round(recent_attended * 100 / recent_conducted, 1) if recent_conducted >= 4 else None
        threshold = company.campus_attendance_threshold
        threshold = int(threshold) if float(threshold).is_integer() else threshold
        # Smallest number of the remaining classes the student must attend to end the term at the threshold.
        need = None
        if conducted and remaining:
            need = max(0, math.ceil(threshold * (conducted + remaining) / 100 - attended))
        return {"rate": rate, "recent": recent, "conducted": conducted, "attended": attended, "remaining": remaining,
                "need": need, "threshold": threshold, "reachable": need is None or need <= remaining}

    def _academics(self, student, placement):
        domain = [("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("exam_id.state", "=", "done")]
        if placement:
            domain += [("exam_id.batch_id", "=", placement.batch_id.id)]
            if placement.academic_term_id:
                domain += [("exam_id.start_time", ">=", placement.academic_term_id.term_start_date),
                           ("exam_id.start_time", "<", placement.academic_term_id.term_end_date + timedelta(days=1))]
        lines = self.env["op.result.line"].sudo().search(domain)
        total = sum(line.exam_id.total_marks for line in lines if line.exam_id.total_marks)
        scored = sum(line.marks for line in lines if line.exam_id.total_marks)
        fails = sum(1 for line in lines if line.exam_id.total_marks and line.marks < line.exam_id.min_marks)
        return {"average": round(scored * 100 / total, 1) if total else None, "exams": len(lines), "fails": fails}

    def _fees(self, student, today):
        invoices = self.env["account.move"].sudo().search([
            ("company_id", "=", student.company_id.id), ("campus_student_id", "=", student.id), ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"), ("amount_residual", ">", 0), ("invoice_date_due", "<", today)])
        overdue = sum(abs(invoice.amount_residual_signed) for invoice in invoices)
        days = max((today - inv.invoice_date_due).days for inv in invoices) if invoices else 0
        return {"overdue": overdue, "days": days, "invoices": len(invoices)}

    def _engagement(self, student, placement, today):
        term = placement.academic_term_id
        start = term.term_start_date or placement.campus_date_from or today.replace(day=1)
        start = max(start, placement.campus_date_from or start)
        end = min(today, term.term_end_date or today, placement.campus_date_to or today)
        od_dates, leave_dates = set(), set()
        def dates(first, last):
            first, last = max(first, start), min(last, end)
            return {first + timedelta(days=offset) for offset in range(max(0, (last - first).days + 1))}
        od_domain = [("student_id", "=", student.id), ("company_id", "=", student.company_id.id),
                     ("date_from", "<=", end), ("date_to", ">=", start),
                     ("state", "in", ["withheld", "proof_review", "completed"])]
        if term:
            od_domain.append(("term_id", "=", term.id))
        for od in self.env["campus.student.od"].sudo().search(od_domain):
            od_dates.update(dates(od.date_from, od.date_to))
        for leave in self.env["campus.student.leave"].sudo().search([
                ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("state", "=", "approved"),
                ("date", "<=", end), ("deadline", ">=", start)]):
            leave_dates.update(dates(leave.date, leave.deadline))
        last = self.env["campus.counseling"].sudo().search([
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("date", "<=", today)], order="date desc, id desc", limit=1)
        overdue_follow_up = int(bool(last and last.follow_up_date and last.follow_up_date < today))
        return {"od_days": len(od_dates), "leave_days": len(leave_dates - od_dates), "overdue_follow_up": overdue_follow_up,
                "last_counseling": fields.Date.to_string(last.date) if last else ""}

    def _score(self, att, acad, fees, eng):
        factors = []
        # Attendance (max 40): points grow as the term-to-date rate falls below threshold + 5.
        points = 0
        # Fewer than five completed classes is too little to judge; the factor waits.
        if att["rate"] is not None and att["conducted"] >= 5:
            points = min(WEIGHTS["attendance"], max(0, round((att["threshold"] + 5 - att["rate"]) * 3)))
            if att["recent"] is not None and att["recent"] <= att["rate"] - 10:
                points = min(WEIGHTS["attendance"], points + 10)
            if not att["reachable"]:
                points = WEIGHTS["attendance"]
        if points:
            detail = _("%(rate)s%% attendance against a %(threshold)s%% threshold") % {"rate": pct(att["rate"]), "threshold": att["threshold"]}
            if att["recent"] is not None and att["recent"] <= att["rate"] - 10:
                detail += _("; dropped to %s%% in the last four weeks") % pct(att["recent"])
            if not att["reachable"]:
                detail += _("; the currently scheduled classes are not enough to reach the threshold")
            factors.append({"key": "attendance", "label": _("Attendance"), "points": points, "detail": detail})
        # Academics (max 30): average below 50% and failed papers.
        a_points = 0
        if acad["average"] is not None:
            a_points = min(25, max(0, round((50 - acad["average"]) * 1.2))) + min(10, acad["fails"] * 5)
            a_points = min(WEIGHTS["academics"], a_points)
        if a_points:
            factors.append({"key": "academics", "label": _("Results"), "points": a_points,
                            "detail": _("%(avg)s%% average across %(n)s published exams, %(f)s below pass marks")
                            % {"avg": acad["average"], "n": acad["exams"], "f": acad["fails"]}})
        # Fees (max 15): any overdue balance, more the longer it stays unpaid.
        f_points = 0
        if fees["overdue"] > 0:
            f_points = min(WEIGHTS["fees"], 8 + (fees["days"] // 30) * 3)
            factors.append({"key": "fees", "label": _("Fees"), "points": f_points,
                            "detail": _("%(n)s invoice(s) overdue by up to %(d)s days") % {"n": fees["invoices"], "d": fees["days"]}})
        # Engagement (max 15): time away on leave/OD and missed counselling follow-ups.
        e_points = min(10, (eng["od_days"] + eng["leave_days"]) * 2) + (5 if eng["overdue_follow_up"] else 0)
        e_points = min(WEIGHTS["engagement"], e_points)
        if e_points:
            detail = _("%(od)s OD day(s) and %(lv)s leave day(s) this semester") % {"od": eng["od_days"], "lv": eng["leave_days"]}
            if eng["overdue_follow_up"]:
                detail += _("; a counselling follow-up is overdue")
            factors.append({"key": "engagement", "label": _("Engagement"), "points": e_points, "detail": detail})
        score = min(100, points + a_points + f_points + e_points)
        band = next(name for name, floor in BANDS if score >= floor)
        factors.sort(key=lambda item: -item["points"])
        return score, band, factors

    def _action(self, factors, att):
        if not factors:
            return _("No scored concerns in the available records. Review missing attendance or results before concluding the student is on track.")
        top = factors[0]["key"]
        if top == "attendance":
            if att["need"] is not None and att["remaining"]:
                if att["reachable"]:
                    return _("Mentor call this week: attend %(n)s of the next %(m)s scheduled classes to reach at least %(t)s%% across recorded and scheduled classes.") % {
                        "n": att["need"], "m": att["remaining"], "t": att["threshold"]}
                return _("Review attendance and the remaining timetable with the mentor; currently scheduled classes alone cannot make up the shortage.")
            return _("Mentor call this week to discuss attendance.")
        if top == "academics":
            return _("Refer to remedial classes and check the next internal assessment plan.")
        if top == "fees":
            return _("Accounts office to contact the guardian about the overdue fee.")
        return _("Schedule a counselling session and record the follow-up date.")

    def _assess(self, student, today):
        placement = self._placement(student)
        att = self._attendance(student, placement, today) if placement else {
            "rate": None, "recent": None, "conducted": 0, "attended": 0, "remaining": 0, "need": None,
            "threshold": student.company_id.campus_attendance_threshold, "reachable": True}
        acad = self._academics(student, placement)
        fees = self._fees(student, today)
        eng = self._engagement(student, placement, today) if placement else {"od_days": 0, "leave_days": 0, "overdue_follow_up": 0, "last_counseling": ""}
        score, band, factors = self._score(att, acad, fees, eng)
        route = self.env["campus.student.leave.routing"].sudo().search([
            ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("active", "=", True)], limit=1)
        return {
            "id": student.id, "name": student.name, "number": student.gr_no or "", "register": student.register_no or "",
            "batch": placement.batch_id.name or "" if placement else "", "batch_id": placement.batch_id.id if placement else 0,
            "programme": placement.course_id.name or "" if placement else "",
            "department": placement.course_id.department_id.name or "" if placement else "",
            "department_id": placement.course_id.department_id.id if placement else 0,
            "semester": placement.academic_term_id.name or "" if placement else "",
            "mentor": route.advisor_id.name or "" if route else "", "mentor_id": route.advisor_id.id if route else 0,
            "score": score, "band": band, "provisional": att["conducted"] < 5, "factors": factors, "action": self._action(factors, att),
            "attendance": att, "academics": acad, "fees": fees, "engagement": eng,
        }

    # ------------------------------------------------------------------ API
    @api.model
    def get_workspace(self, filters=None):
        role, domain = self._scope()
        filters = filters if isinstance(filters, dict) else {}
        today = fields.Date.context_today(self)
        students = self.env["op.student"].sudo().search(domain, order="name")
        if role == "hod":
            students = students.filtered(lambda student: self._placement(student).course_id.department_id == self.env.user.dept_id)
        rows = [self._assess(student, today) for student in students]
        all_rows = rows
        for key in ("department_id", "batch_id"):
            value = filters.get(key)
            if value not in (None, "", 0, "0"):
                try:
                    rows = [row for row in rows if row[key] == int(value)]
                except (TypeError, ValueError) as exc:
                    raise ValidationError(_("Choose a valid filter.")) from exc
        band = filters.get("band")
        if band in {"high", "watch", "low"}:
            rows = [row for row in rows if row["band"] == band]
        query = str(filters.get("query") or "").strip().lower()
        if query:
            rows = [row for row in rows if query in row["name"].lower() or query in row["number"].lower() or query in row["register"].lower()]
        rows.sort(key=lambda row: (-row["score"], row["name"]))
        bands = Counter(row["band"] for row in all_rows)
        top_factors = Counter(row["factors"][0]["key"] for row in all_rows if row["factors"])
        departments = sorted({(row["department_id"], row["department"]) for row in all_rows if row["department_id"]}, key=lambda item: item[1])
        batches = sorted({(row["batch_id"], row["batch"], row["department_id"]) for row in all_rows if row["batch_id"]}, key=lambda item: item[1])
        return {
            "role": role, "today": fields.Date.to_string(today), "company": self.env.company.name,
            "threshold": pct(self.env.company.campus_attendance_threshold),
            "currency_symbol": self.env.company.currency_id.symbol, "currency_code": self.env.company.currency_id.name,
            "summary": {"students": len(all_rows), "high": bands["high"], "watch": bands["watch"], "low": bands["low"],
                        "top_factors": [{"key": key, "count": count} for key, count in top_factors.most_common()]},
            "departments": [{"id": d, "name": n} for d, n in departments],
            "batches": [{"id": b, "name": n, "department_id": d} for b, n, d in batches],
            "rows": rows[:500], "truncated": len(rows) > 500,
            "can_counsel": self.env["campus.counseling"].check_access_rights("create", raise_exception=False),
            "can_open_student": self.env["op.student"].check_access_rights("read", raise_exception=False),
        }

    @api.model
    def get_counseling_action(self, student_id):
        role, domain = self._scope()
        if isinstance(student_id, bool) or not isinstance(student_id, (int, str)) or not str(student_id).isdigit() or not 0 < int(student_id) < 2147483648:
            raise ValidationError(_("Choose a valid student."))
        student = self.env["op.student"].sudo().search(domain + [("id", "=", int(student_id))], limit=1)
        if not student:
            raise AccessError(_("This student is outside your Student Success scope."))
        if role == "hod" and self._placement(student).course_id.department_id != self.env.user.dept_id:
            raise AccessError(_("This student's current placement is outside your department."))
        self.env["campus.counseling"].check_access_rights("create")
        mentor = self.env["op.faculty"].search([("user_id", "=", self.env.uid)], limit=1)
        return {"type": "ir.actions.act_window", "res_model": "campus.counseling", "view_mode": "form", "views": [(False, "form")],
                "target": "new", "name": _("Record counselling"),
                "context": {"default_student_id": student.id, "default_mentor_id": mentor.id, "default_company_id": student.company_id.id}}

    def student_nudge(self, student):
        """Compact guidance for the student's and parent's own portal pages."""
        today = fields.Date.context_today(self)
        row = self._assess(student, today)
        att = row["attendance"]
        name = student.name
        if att["rate"] is None:
            message = _("No attendance has been recorded for this semester yet.")
            parent_message = message
        elif att["need"] is not None and att["remaining"] and att["reachable"] and att["attended"] * 100 < (att["threshold"] + 5) * att["conducted"]:
            values = {"n": att["need"], "m": att["remaining"], "t": att["threshold"], "name": name}
            message = _("Attend %(n)s of your next %(m)s scheduled classes to reach at least %(t)s%% across recorded and scheduled classes.") % values
            parent_message = _("%(name)s needs to attend %(n)s of the next %(m)s scheduled classes to reach at least %(t)s%% across recorded and scheduled classes.") % values
        elif not att["reachable"]:
            message = _("Currently scheduled classes alone cannot bring attendance to %s%%. Review attendance and the remaining timetable with your mentor.") % att["threshold"]
            parent_message = _("Currently scheduled classes alone cannot bring %(name)s's attendance to %(t)s%%. Please review the timetable with the mentor.") % {"name": name, "t": att["threshold"]}
        elif att["attended"] * 100 < att["threshold"] * att["conducted"]:
            message = _("Recorded attendance is %(r)s%%, below %(t)s%%. No future classes are scheduled yet; ask your mentor to review the timetable.") % {"r": pct(att["rate"]), "t": att["threshold"]}
            parent_message = _("%(name)s's recorded attendance is %(r)s%%, below %(t)s%%. Please review the timetable with the mentor.") % {"name": name, "r": pct(att["rate"]), "t": att["threshold"]}
        else:
            message = _("Attendance is on track. Keep it above %s%%.") % att["threshold"]
            parent_message = _("%(name)s's attendance is on track, above %(t)s%%.") % {"name": name, "t": att["threshold"]}
        shortage = bool(att["conducted"] and att["attended"] * 100 < att["threshold"] * att["conducted"])
        if row["band"] == "high":
            title = _("Needs attention now")
        elif shortage:
            title = _("Attendance needs attention")
        elif row["band"] == "watch":
            title = _("Worth a closer look this week")
        elif att["conducted"] < 5:
            title = _("Limited attendance history")
        else:
            title = _("On track from available records")
        return {"score": row["score"], "band": row["band"], "display_band": "watch" if shortage and row["band"] == "low" else row["band"], "title": title, "factors": row["factors"], "action": row["action"],
                "attendance": att, "message": message, "parent_message": parent_message, "name": name}
