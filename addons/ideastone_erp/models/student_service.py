import base64
import re
import uuid
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html_sanitize

from odoo import _, api, fields, models


class StudentPortal(models.AbstractModel):
    _name = "campus.student.portal"
    _description = "Authenticated, scoped Student Portal projections and actions"

    def _identity(self):
        user = self.env.user
        if not user.active or not user.has_group("base.group_portal") or user.has_group("base.group_user"):
            raise AccessError(_("This workspace requires a student portal account."))
        students = self.env["op.student"].sudo().with_context(active_test=False).search([
            ("user_id", "=", user.id), ("company_id", "in", user.company_ids.ids)], limit=2)
        if len(students) != 1 or not students.active:
            raise AccessError(_("Your account has no linked student record, is inactive, or has more than one student link. Contact the college office."))
        if not students.company_id.campus_student_portal_enabled:
            raise AccessError(_("The Student Portal is not enabled for your college. Contact the college office."))
        return students

    def _records(self, model, domain, limit=5000, order=None):
        # All callers build the scope from _identity(), never a supplied student ID.
        source = self.env[model].sudo()
        if source.search_count(domain) > limit:
            raise ValidationError(_("This view contains too many records. Select a shorter academic period."))
        return source.search(domain, order=order)

    def _portal_context(self, enrolment=None, date_from=None, date_to=None):
        student = self._identity()
        placements = student.course_detail_ids.filtered(lambda e: e.company_id == student.company_id).sorted(lambda e: (e.campus_date_from or fields.Date.today(), e.id), reverse=True)
        current = placements.filtered(lambda e: e.state == "running")[:1] or placements[:1]
        if enrolment:
            try:
                current = placements.filtered(lambda e: e.id == int(enrolment))
            except (ValueError, TypeError):
                current = placements.browse()
            if not current:
                raise AccessError(_("The selected academic placement does not belong to your account."))
        today = fields.Date.context_today(self)
        first = current.academic_term_id.term_start_date or current.academic_years_id.start_date or today.replace(day=1)
        last = current.academic_term_id.term_end_date or current.academic_years_id.end_date or today
        try:
            first = fields.Date.to_date(date_from) if date_from else first
            last = fields.Date.to_date(date_to) if date_to else last
            if first > last or (last - first).days > 1096:
                raise ValueError()
        except (ValueError, TypeError) as exc:
            raise ValidationError(_("Choose a valid period of at most three years.")) from exc
        return student, current, placements, first, last

    def _dates(self, value):
        if not value:
            return ""
        if isinstance(value, datetime):
            return fields.Datetime.context_timestamp(self, value).strftime("%d %b %Y, %H:%M")
        return value.strftime("%d %b %Y")

    def _notice_records(self, student):
        today = fields.Date.context_today(self)
        enrolments = student.course_detail_ids.filtered(lambda e: e.state == "running")
        return self._records("campus.circular", [
            ("company_id", "=", student.company_id.id), ("state", "=", "approved"), ("active", "=", True),
            ("audience", "in", ["all", "student"]), ("date_from", "<=", today), "|", ("date_to", "=", False), ("date_to", ">=", today),
            "|", ("campus_managed", "=", False), ("campus_status", "=", "published"),
            "|", ("campus_course_id", "=", False), ("campus_course_id", "in", enrolments.course_id.ids),
            "|", ("campus_batch_id", "=", False), ("campus_batch_id", "in", enrolments.batch_id.ids),
            "|", ("campus_group_id", "=", False), ("campus_group_id", "in", self.env.user.groups_id.ids),
        ], limit=500, order="date_from desc, id desc")

    def _materials(self, student, enrolment=None):
        enrolments = enrolment or student.course_detail_ids
        subjects = enrolments.subject_ids or enrolments.course_id.subject_ids
        return self._records("campus.digital.resource", [
            ("company_id", "=", student.company_id.id), ("state", "=", "approved"), ("active", "=", True),
            "|", ("batch_ids", "=", False), ("batch_ids", "in", enrolments.batch_id.ids),
            "|", ("subject_id", "=", False), ("subject_id", "in", subjects.ids),
        ], limit=500)

    def _invoices(self, student):
        return self._records("account.move", [("company_id", "=", student.company_id.id), ("state", "=", "posted"), ("move_type", "=", "out_invoice"),
            "|", ("campus_student_id", "=", student.id), "&", ("campus_student_id", "=", False), ("partner_id", "=", student.partner_id.id)], limit=2000, order="invoice_date desc, id desc")

    def _requests(self, student):
        return self._records("campus.service.request", [("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("requester_id", "=", self.env.uid), ("portal_type_id", "!=", False)], limit=1000, order="id desc")

    def _serialize(self, student):
        # Odoo uses REPEATABLE READ: a lock alone does not refresh a waiter's
        # snapshot. Touch a dedicated revision so a concurrent stale transaction
        # is retried by Odoo before it checks for an existing request/read/feedback.
        self.env.cr.execute("UPDATE op_student SET campus_portal_revision=COALESCE(campus_portal_revision,0)+1 WHERE id=%s", [student.id])
        student.invalidate_recordset(["campus_portal_revision"])

    def _request_audience(self):
        return "student"

    def _types(self, student):
        types = self.with_context(active_test=False)._records("campus.student.request.type", ["|", ("company_id", "=", False), ("company_id", "=", student.company_id.id)], limit=100, order="sequence, name")
        overrides = set(types.filtered("company_id").mapped("code"))
        return types.filtered(lambda rec: rec.active and rec.portal_audience in {self._request_audience(), "both"} and (rec.company_id or rec.code not in overrides))

    def _scope(self, student, enrolment):
        if not enrolment:
            return []
        return [("company_id", "=", student.company_id.id), ("batch_id", "=", enrolment.batch_id.id)]

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        student, placement, placements, first, last = self._portal_context(enrolment, date_from, date_to)
        company = student.company_id
        today = fields.Date.context_today(self)
        subjects = placement.subject_ids or placement.course_id.subject_ids
        dates = [("attendance_date", ">=", first), ("attendance_date", "<=", last)]
        attendance = self._records("op.attendance.line", [("company_id", "=", company.id), ("student_id", "=", student.id), ("attendance_id.state", "=", "done"),
            "|", ("attendance_id.session_id", "=", False), ("attendance_id.session_id.state", "!=", "cancel")] + dates + ([("batch_id", "=", placement.batch_id.id)] if placement else []), order="attendance_date desc, id desc")
        policy = company.campus_excused_policy
        grouped, trend = {}, defaultdict(lambda: [0, 0])
        attendance_rows = []
        for line in attendance:
            subject = line.attendance_id.campus_subject_id or line.attendance_id.campus_manual_subject_id
            eligible = not line.excused or policy != "exclude"
            present = bool(line.present or line.late or line.excused and policy == "present")
            row = grouped.setdefault(subject.id, {"id": subject.id, "name": subject.name or "Recorded class", "attended": 0, "eligible": 0})
            if eligible:
                row["eligible"] += 1
                row["attended"] += int(present)
                key = line.attendance_date.strftime("%Y-%m")
                trend[key][0] += int(present)
                trend[key][1] += 1
            attendance_rows.append({"id": line.id, "subject": subject.name or "Recorded class", "date": self._dates(line.attendance_date), "status": line.campus_status, "eligible": eligible})
        for row in grouped.values():
            row["rate"] = round(row["attended"] * 100 / row["eligible"], 2) if row["eligible"] else None
            row["shortage"] = row["eligible"] and row["attended"] * 100 < company.campus_attendance_threshold * row["eligible"]
        conducted = sum(row["eligible"] for row in grouped.values())
        attended = sum(row["attended"] for row in grouped.values())
        rate = round(attended * 100 / conducted, 2) if conducted else None
        timezone = pytz.timezone(self.env.user.tz or "UTC")
        utc_first = timezone.localize(datetime.combine(first, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        utc_last = timezone.localize(datetime.combine(last + timedelta(days=1), time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        sessions = self._records("op.session", self._scope(student, placement) + [("start_datetime", ">=", utc_first), ("start_datetime", "<", utc_last), ("state", "in", ["confirm", "cancel"])], order="start_datetime") if placement else self.env["op.session"]
        # A section can run electives: only the student's authoritative subject list.
        sessions = sessions.filtered(lambda s: s.subject_id in subjects and (not placement.campus_date_from or fields.Datetime.context_timestamp(self, s.start_datetime).date() >= placement.campus_date_from) and (not placement.campus_date_to or fields.Datetime.context_timestamp(self, s.start_datetime).date() <= placement.campus_date_to))
        schedule = [{"id": s.id, "subject": s.subject_id.name, "code": s.subject_id.code, "start": self._dates(s.start_datetime), "end": self._dates(s.end_datetime), "day": str(fields.Datetime.context_timestamp(self, s.start_datetime).date()), "room": s.classroom_id.name or "Room not assigned", "faculty": s.faculty_id.name, "status": s.state, "updated": self._dates(s.write_date)} for s in sessions]
        exam_domain = self._scope(student, placement) + [("subject_id", "in", subjects.ids), ("state", "!=", "cancel"), "|", "&", ("campus_managed", "=", True), ("campus_schedule_published", "=", True), "&", ("campus_managed", "=", False), ("state", "in", ["schedule", "held", "result_updated", "done"])]
        exams = self._records("op.exam", exam_domain, order="start_time") if placement else self.env["op.exam"]
        marks = self._records("op.result.line", [("student_id", "=", student.id), ("company_id", "=", company.id), ("exam_id.state", "=", "done"),
            "|", ("exam_id.campus_managed", "=", False), "&", ("exam_id.campus_state", "=", "published"), ("campus_entered", "=", True)] + ([("exam_id.batch_id", "=", placement.batch_id.id)] if placement else []), order="id desc")
        invoices = self._invoices(student)
        payments = self._records("account.payment", [("company_id", "=", company.id), ("campus_invoice_id", "in", invoices.ids), ("campus_receipt_number", "!=", False)], order="date desc, id desc")
        assessed, due = sum(invoices.mapped("amount_total")), sum(invoices.mapped("amount_residual"))
        notices = self._notice_records(student)
        reads = self.env["campus.student.notice.read"].sudo().search([("student_id", "=", student.id), ("notice_id", "in", notices.ids)]).notice_id
        requests = self._requests(student)
        events = self._records("campus.student.request.event", [("request_id", "in", requests.ids)], limit=5000, order="id desc")
        states = dict(self.env["campus.service.request"]._fields["state"].selection)
        documents = self._records("campus.admission.document", [("student_id", "=", student.id), ("company_id", "=", company.id)], limit=500)
        materials = self._materials(student, placement)
        loans = self._records("op.media.movement", [("student_id", "=", student.id), ("company_id", "=", company.id)], limit=500, order="issued_date desc")
        catalogue = self.env["op.media.unit"].sudo()._read_group([("campus_company_id", "=", company.id)], ["media_id"], ["__count"], limit=200, order="media_id")
        books = self.env["op.media"].sudo().browse([media.id for media, _count in catalogue if media])
        navigation = [("dashboard", "Student Dashboard", "home"), ("profile", "My Profile", "user"), ("academics", "Academics", "graduation-cap"), ("timetable", "Timetable", "calendar"), ("attendance", "My Attendance", "calendar-check-o"), ("exams", "Examinations & Results", "file-text-o"), ("fees", "Fees & Payments", "inr"), ("notices", "Notices & Calendar", "bullhorn"), ("requests", "Requests & Certificates", "folder-open-o")]
        if loans or books or materials:
            navigation.append(("library", "Library", "book"))
        navigation += [("help", "Help & Feedback", "question-circle-o"), ("account", "Account & Preferences", "cog")]
        return {"company": company.name, "demo": company.campus_demo, "today": self._dates(today), "today_iso": str(today), "timezone": self.env.user.tz or "UTC", "student_id": student.id,
            "student": {"name": student.name, "number": student.gr_no or "Not assigned", "register": student.register_no or "Not assigned", "status": student.campus_status, "email": student.email or "", "phone": student.phone or "", "mobile": student.mobile or "", "street": student.street or "", "street2": student.street2 or "", "city": student.city or "", "zip": student.zip or "", "admitted": self._dates(student.campus_admission_date)},
            "guardians": [{"name": g.name, "phone": g.phone or g.mobile or "", "email": g.email or ""} for g in student.campus_guardian_ids],
            "contact_edit": company.campus_student_contact_edit, "support_email": company.email or "", "support_phone": company.phone or "", "login": self.env.user.login,
            "notice_badge": student.campus_notice_badge, "navigation": navigation,
            "placement": {"id": placement.id, "programme": placement.course_id.name or "Not assigned", "department": placement.course_id.department_id.name or "Not assigned", "semester": placement.academic_term_id.name or "Not assigned", "section": placement.batch_id.name or "Not assigned", "year": placement.academic_years_id.name or "Not assigned"},
            "placements": [{"id": e.id, "label": " / ".join(filter(None, [e.academic_years_id.name, e.academic_term_id.name, e.course_id.name, e.batch_id.name])) or "Recorded enrolment"} for e in placements],
            "filters": {"enrolment": str(placement.id or ""), "date_from": str(first), "date_to": str(last)},
            "subjects": [{"id": s.id, "name": s.name, "code": s.code, "credits": s.campus_credits, "type": s.type, "faculty": ", ".join(sessions.filtered(lambda p, subject=s: p.subject_id == subject).faculty_id.mapped("name")) or "Not allocated"} for s in subjects],
            "schedule": schedule, "today_classes": [row for row, session in zip(schedule, sessions, strict=True) if row["day"] == str(today) and session.state != "cancel" and session.end_datetime > fields.Datetime.now()],
            "attendance": {"attended": attended, "conducted": conducted, "rate": rate, "threshold": company.campus_attendance_threshold, "policy": policy, "shortage": conducted and attended * 100 < company.campus_attendance_threshold * conducted, "subjects": list(grouped.values()), "rows": attendance_rows, "trend": [{"month": month, "rate": round(n[0] * 100 / n[1], 2)} for month, n in sorted(trend.items())]},
            "exams": [{"id": e.id, "name": e.name, "subject": e.subject_id.name, "code": e.subject_id.code, "start": self._dates(e.start_time), "end": self._dates(e.end_time), "upcoming": e.start_time >= fields.Datetime.now()} for e in exams],
            "results": [{"exam": r.exam_id.name, "subject": r.exam_id.subject_id.name, "code": r.exam_id.subject_id.code, "marks": r.marks, "maximum": r.exam_id.total_marks, "grade": r.grade or "Not assigned", "status": r.status or "Not published"} for r in marks],
            "fees": {"assessed": assessed, "paid": assessed - due, "due": due, "recorded": bool(invoices), "symbol": company.currency_id.symbol, "progress": min(100, max(0, (assessed - due) * 100 / assessed)) if assessed else 0,
                "invoices": [{"id": i.id, "name": i.name, "date": self._dates(i.invoice_date), "due_date": self._dates(i.invoice_date_due), "total": i.amount_total, "paid": i.amount_total - i.amount_residual, "balance": i.amount_residual, "heads": ", ".join(i.invoice_line_ids.mapped("name")), "year": i.campus_year_id.name or "Not assigned", "programme": i.campus_course_id.name or "Not assigned", "concession": i.currency_id.round(sum(line.quantity * line.price_unit * line.discount / 100 for line in i.invoice_line_ids if not line.display_type or line.display_type == "product")), "state": i.payment_state, "overdue": bool(i.amount_residual and i.invoice_date_due and i.invoice_date_due < today)} for i in invoices],
                "payments": [{"id": p.id, "reference": p.campus_receipt_number, "date": self._dates(p.date), "amount": p.amount, "method": p.campus_method, "status": "Reversed" if p.campus_reversal_id else "Posted", "transaction": p.campus_reference or "", "url": f"/my/campus/student/download/receipt/{p.id}"} for p in payments]},
            "notices": [{"id": n.id, "name": n.name, "date": self._dates(n.date_from), "category": n.campus_category or "College notice", "body": html_sanitize(n.body), "read": n in reads, "files": [{"id": a.id, "name": a.name} for a in n.attachment_ids]} for n in notices], "unread": len(notices - reads),
            "requests": [{"id": r.id, "reference": r.portal_reference, "name": r.name, "description": r.description, "type": r.portal_type_id.name, "type_id": r.portal_type_id.id, "date": self._dates(r.create_date), "status": states[r.state], "state": r.state, "reply": r.portal_reply or "", "student_reply": r.portal_student_reply or "", "can_cancel": r.portal_type_id.allow_cancel and r.state in {"draft", "submitted"}, "file": bool(r.portal_result_file and r.state in {"ready", "done"}), "events": [{"name": e.name, "date": self._dates(e.create_date), "response": e.response or ""} for e in r.portal_event_ids.sorted("id", reverse=True)]} for r in requests],
            "updates": len(events.filtered(lambda e: e.id > student.campus_request_seen_event)),
            "request_types": [{"id": t.id, "code": t.code, "name": t.name, "guidance": t.guidance, "fee": t.fee_guidance or "", "max_mb": t.max_upload_mb, "require_file": t.require_file} for t in self._types(student)], "submission_key": uuid.uuid4().hex,
            "documents": [{"id": d.id, "name": d.name, "filename": d.filename, "state": d.state} for d in documents],
            "materials": [{"id": m.id, "name": m.name, "filename": m.filename, "subject": m.subject_id.name or "General resource", "date": self._dates(m.approved_on)} for m in materials],
            "loans": [{"name": loan.media_id.name, "code": loan.media_id.internal_code, "issued": self._dates(loan.issued_date), "due": self._dates(loan.return_date), "state": loan.state, "penalty": loan.penalty, "overdue": loan.state == "issue" and loan.return_date < today} for loan in loans],
            "books": [{"name": book.name, "code": book.internal_code} for book in books[:200]],
        }

    @api.model
    def act(self, operation, payload=None):
        student = self._identity()
        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValidationError(_("Invalid form submission."))
        if operation == "profile":
            allowed = {"phone", "mobile", "street", "street2", "city", "zip"}
            if not student.company_id.campus_student_contact_edit or set(payload) - allowed:
                raise AccessError(_("Official profile fields are managed by the college. Submit a correction request."))
            if any(not isinstance(v, str) or len(v) > 250 for v in payload.values()):
                raise ValidationError(_("Contact fields must be text of at most 250 characters."))
            for key in {"phone", "mobile"}.intersection(payload):
                if payload[key] and not re.fullmatch(r"[+()\d\s-]{7,25}", payload[key]):
                    raise ValidationError(_("Enter a valid contact phone number."))
            student.write(payload)
            self.env["campus.mvp.audit"]._log(student, "Student contact details updated", details={"fields": sorted(payload)})
        elif operation == "preferences":
            if set(payload) != {"notice_badge"} or not isinstance(payload["notice_badge"], bool):
                raise ValidationError(_("Invalid preference."))
            student.campus_notice_badge = payload["notice_badge"]
        elif operation == "notice":
            if not isinstance(payload.get("read", True), bool):
                raise ValidationError(_("Notice read state must be true or false."))
            notice = self._notice_records(student).filtered(lambda n: n.id == int(payload.get("notice_id") or 0))
            if not notice:
                raise AccessError(_("This notice is not available to your account."))
            self._serialize(student)
            existing = self.env["campus.student.notice.read"].sudo().search([("student_id", "=", student.id), ("notice_id", "=", notice.id)])
            if payload.get("read", True) and not existing:
                self.env["campus.student.notice.read"].sudo().create({"student_id": student.id, "notice_id": notice.id})
            elif not payload.get("read", True):
                existing.unlink()
        elif operation == "updates":
            latest = self.env["campus.student.request.event"].sudo().search([("request_id", "in", self._requests(student).ids)], order="id desc", limit=1)
            student.write({"campus_request_seen_at": fields.Datetime.now(), "campus_request_seen_event": latest.id or 0})
        elif operation == "request":
            return self._create_request(student, payload)
        elif operation in {"cancel", "reply"}:
            rec = self._requests(student).filtered(lambda r: r.id == int(payload.get("request_id") or 0))
            if not rec:
                raise AccessError(_("This request does not belong to your account."))
            rec._lock()
            if operation == "cancel":
                if not rec.portal_type_id.allow_cancel or rec.state not in {"draft", "submitted"}:
                    raise ValidationError(_("This request has entered review and cannot be cancelled by the student."))
                rec.write({"state": "cancelled"})
            else:
                reply = str(payload.get("reply") or "").strip()
                if rec.state != "information" or not reply or len(reply) > 5000:
                    raise ValidationError(_("Provide the requested information in at most 5,000 characters."))
                rec.write({"portal_student_reply": reply})
                rec.write({"state": "submitted"})
        elif operation == "feedback":
            period, comments = str(payload.get("period") or "").strip(), str(payload.get("comments") or "")
            score = int(payload.get("score") or 0)
            if not period or len(period) > 80 or not 1 <= score <= 5 or len(comments) > 5000:
                raise ValidationError(_("Enter a period, a rating from 1 to 5 and comments within 5,000 characters."))
            self._serialize(student)
            if self.env["campus.feedback"].sudo().search_count([("respondent_id", "=", self.env.uid), ("company_id", "=", student.company_id.id), ("kind", "=", "student"), ("period", "=", period), ("faculty_id", "=", False)]):
                raise ValidationError(_("Feedback has already been submitted for this period."))
            self.env["campus.feedback"].sudo().create({"name": "Student feedback: " + period, "student_id": student.id, "respondent_id": self.env.uid, "company_id": student.company_id.id, "kind": "student", "period": period, "score": score, "comments": comments})
        else:
            raise AccessError(_("This student action is not supported."))
        return {"saved": True}

    def _create_request(self, student, payload):
        self._serialize(student)
        key = str(payload.get("key") or "")
        if not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValidationError(_("Reload the request form before submitting."))
        existing = self._requests(student).filtered(lambda r: r.portal_key == key)
        if existing:
            return {"saved": True, "reference": existing.portal_reference}
        kind = self._types(student).filtered(lambda t: t.id == int(payload.get("type_id") or 0))
        if not kind:
            raise AccessError(_("Choose an available college request type."))
        title, description = str(payload.get("title") or "").strip(), str(payload.get("description") or "").strip()
        if not title or not description or len(title) > 200 or len(description) > 5000:
            raise ValidationError(_("Enter a title (200 characters maximum) and details (5,000 maximum)."))
        duplicate = self._requests(student).filtered(lambda r: r.portal_type_id == kind and r.state not in {"done", "rejected", "cancelled"})
        if duplicate:
            return {"saved": True, "reference": duplicate[0].portal_reference, "existing": True}
        model = self.env["campus.service.request"].sudo()
        content, filename = model._portal_upload(payload.get("file"), payload.get("filename"), kind.max_upload_mb)
        if kind.require_file and not content:
            raise ValidationError(_("Attach the required supporting file."))
        attendance = self.env["op.attendance.line"].sudo().browse()
        if payload.get("attendance_id"):
            attendance = self._records("op.attendance.line", [("id", "=", int(payload["attendance_id"])), ("student_id", "=", student.id), ("company_id", "=", student.company_id.id)])
            if not attendance:
                raise AccessError(_("The attendance reference does not belong to your account."))
        rec = model.create({"name": title, "description": description, "kind": kind.kind, "portal_type_id": kind.id,
            "portal_key": key, "student_id": student.id, "requester_id": self.env.uid, "company_id": student.company_id.id,
            "document": content, "filename": filename, "portal_attendance_id": attendance.id})
        rec.action_submit()
        return {"saved": True, "reference": rec.portal_reference}

    def _download(self, kind, record_id):
        student = self._identity()
        if kind == "receipt":
            payment = self._records("account.payment", [("id", "=", record_id), ("company_id", "=", student.company_id.id), ("campus_invoice_id", "in", self._invoices(student).ids), ("campus_receipt_number", "!=", False)])
            if not payment:
                raise AccessError(_("This receipt is not available to your account."))
            data, _format = self.env["ir.actions.report"].sudo()._render_qweb_pdf("ideastone_erp.mvp_receipt_report", payment.ids)
            return data, "Receipt-" + payment.campus_receipt_number.replace("/", "-") + ".pdf", "application/pdf"
        if kind == "document":
            record = self._records("campus.admission.document", [("id", "=", record_id), ("student_id", "=", student.id), ("company_id", "=", student.company_id.id)])
            content, filename = record.file, record.filename
        elif kind == "resource":
            record = self._materials(student).filtered(lambda r: r.id == record_id)
            content, filename = record.document, record.filename
        elif kind == "request":
            record = self._requests(student).filtered(lambda r: r.id == record_id and r.state in {"ready", "done"})
            content, filename = record.portal_result_file, record.portal_result_filename
        elif kind == "notice":
            record = self._notice_records(student).attachment_ids.filtered(lambda a: a.id == record_id)
            content, filename = record.datas, record.name
        else:
            raise AccessError(_("This document type is not available."))
        if not record or not content:
            raise AccessError(_("This document is not available to your account."))
        return base64.b64decode(content), filename or "document", "application/octet-stream"
