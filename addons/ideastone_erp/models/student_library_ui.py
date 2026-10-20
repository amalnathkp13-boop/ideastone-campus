import json
from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StudentLibraryUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    def _library_copies(self, student):
        return self._records("op.media.unit", [("campus_company_id", "=", student.company_id.id),
            ("media_id.active", "=", True)], limit=10000, order="media_id, id")

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student = self._identity()
        copies = self._library_copies(student)
        today = fields.Date.context_today(self)
        loans = self._records("op.media.movement", [("student_id", "=", student.id),
            ("company_id", "=", student.company_id.id)], limit=500, order="issued_date desc, id desc")
        books = []
        palette = ("", "green", "violet", "orange")
        own_media = set(loans.filtered(lambda item: item.state == "issue").media_id.ids)
        counts = {}
        for unit in copies:
            count = counts.setdefault(unit.media_id.id, [0, 0])
            count[0] += 1
            count[1] += unit.state == "available"
        for index, media in enumerate(copies.media_id.sorted("name")):
            total, available = counts[media.id]
            categories = media.subject_ids.mapped("name") or [media.media_type_id.name or "General"]
            books.append({"id": media.id, "name": media.name, "code": media.internal_code or "Not assigned",
                "authors": ", ".join(media.author_ids.mapped("name")) or "Not recorded",
                "edition": media.edition or "Not recorded", "isbn": media.isbn or "Not recorded",
                "subject": ", ".join(media.subject_ids.mapped("name")) or media.media_type_id.name or "General",
                "categories": categories, "category_keys": json.dumps(categories), "publishers": ", ".join(media.publisher_ids.mapped("name")) or "Not recorded",
                "description": media.description or "No description has been recorded.", "copies": total, "available": available,
                "tone": palette[index % len(palette)], "status": "available" if available else "issued",
                "availability": "%s available of %s copies" % (available, total) if available else "Currently issued",
                "own": media.id in own_media})
        states = dict(self.env["op.media.movement"]._fields["state"].selection)
        rows = []
        for loan in loans:
            overdue = loan.state == "issue" and bool(loan.return_date and loan.return_date < today)
            due_soon = loan.state == "issue" and bool(loan.return_date and today <= loan.return_date <= today + timedelta(days=3))
            rows.append({"id": loan.id, "name": loan.media_id.name, "code": loan.media_id.internal_code or "Not assigned",
                "issued": self._dates(loan.issued_date), "due": self._dates(loan.return_date), "returned": self._dates(loan.actual_return_date),
                "penalty": loan.penalty, "active": loan.state == "issue", "overdue": overdue, "attention": overdue or due_soon,
                "status": "Overdue" if overdue else "Due soon" if due_soon else states.get(loan.state, loan.state),
                "tone": "overdue" if overdue else "due" if due_soon else "issued" if loan.state in {"issue", "reserve"} else "available"})
        # Native reservation records expose only this account's own queue entries.
        queues = self._records("op.media.queue", [("user_id", "=", self.env.uid), ("partner_id", "=", student.partner_id.id),
            ("media_id", "in", copies.media_id.ids)], limit=500, order="id desc")
        queue_states = dict(self.env["op.media.queue"]._fields["state"].selection)
        types = self._types(student).filtered(lambda item: item.code == "library")
        enquiries = [row for row in data["requests"] if row["type_id"] in types.ids]
        active = next((row for row in enquiries if row["state"] not in {"done", "rejected", "cancelled"}), None)
        data["library_ui"] = {"books": books, "featured": books[:3], "categories": sorted({category for row in books for category in row["categories"]}),
            "loans": rows, "current": [row for row in rows if row["active"]], "issued": sum(row["active"] for row in rows),
            "attention": sum(row["attention"] for row in rows), "overdue": sum(row["overdue"] for row in rows),
            "fine": sum(row["penalty"] for row in rows), "enquiries": enquiries, "active_enquiry": active,
            "request_enabled": bool(types), "file_required": bool(types and types.require_file), "upload_limit": types.max_upload_mb if types else 2,
            "reservations": [{"reference": row.name, "name": row.media_id.name,
                "from": self._dates(row.date_from), "to": self._dates(row.date_to), "status": queue_states[row.state],
                "tone": "available" if row.state == "accept" else "overdue" if row.state == "reject" else "due"} for row in queues],
            # Accepted queue entries do not carry a confirmed pickup-ready status.
            "ready": sum(loan.state == "reserve" for loan in loans),
            "resources": [{"id": row.id, "name": row.name, "author": row.author or "Not recorded", "description": row.description or "",
                "kind": dict(row._fields["resource_type"].selection)[row.resource_type], "filename": row.filename,
                "subject": row.subject_id.name or "General resource"} for row in self._materials(student)]}
        return data

    @api.model
    def act(self, operation, payload=None):
        if operation != "library_enquiry":
            return super().act(operation, payload)
        student = self._identity()
        if not isinstance(payload, dict):
            raise ValidationError(_("Invalid library enquiry."))
        intent = payload.get("intent")
        intents = {"reserve": "Reservation enquiry", "request": "Book request", "missing": "Missing title enquiry", "renew": "Renewal enquiry"}
        if not isinstance(intent, str) or intent not in intents:
            raise ValidationError(_("Choose a library request type."))
        title, note = str(payload.get("book_title") or "").strip(), str(payload.get("note") or "").strip()
        if not title or len(title) > 150 or len(note) > 4000:
            raise ValidationError(_("Enter a book title (150 characters maximum) and a note within 4,000 characters."))
        detail = ""
        if intent == "renew":
            loan = self._records("op.media.movement", [("id", "=", int(payload.get("loan_id") or 0)),
                ("student_id", "=", student.id), ("company_id", "=", student.company_id.id), ("state", "=", "issue")])
            if not loan:
                raise AccessError(_("Select an active loan belonging to your account."))
            title = loan.media_id.name[:150]
            detail = "\nLoan reference: %s\nCurrent due date: %s" % (loan.id, self._dates(loan.return_date))
        kind = self._types(student).filtered(lambda row: row.code == "library")
        if not kind:
            raise AccessError(_("Library enquiries are not currently enabled. Contact the library desk."))
        # This is the established service request workflow, never a circulation change.
        return self._create_request(student, {"type_id": kind.id, "key": payload.get("key"),
            "title": "%s: %s" % (intents[intent], title),
            "description": "%s\nBook title: %s%s\nStudent note: %s" % (intents[intent], title, detail, note or "No additional note."),
            "file": payload.get("file"), "filename": payload.get("filename")})
