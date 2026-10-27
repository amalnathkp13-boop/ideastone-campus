from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyLibraryNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _faculty_modules(self, visible, faculty, pages):
        modules = super()._faculty_modules(visible, faculty, pages)
        library = next((module for module in modules if module["key"] == "library"), None)
        if library:
            library["items"] = [{"label": label, "action": "ideastone_erp.action_faculty_library_" + view,
                "action_id": self.env.ref("ideastone_erp.action_faculty_library_" + view).id}
                for view, label in [("opac", "OPAC & digital library"), ("catalogue", "Library catalogue"),
                                    ("circulation", "Library circulation"), ("learning", "Learning platform")]]
        return modules


class FacultyLibrary(models.AbstractModel):
    _name = "campus.faculty.library"
    _description = "Faculty catalogue, personal circulation and learning resources"

    def _faculty(self):
        return self.env["campus.question.paper"]._faculty()

    def _records(self, model, domain, limit=10000, order="id"):
        # Caller identity and company/ownership domains are fixed by this service.
        source = self.env[model].sudo()
        if source.search_count(domain) > limit:
            raise ValidationError(_("This library scope is too large. Contact the library administrator to archive older records."))
        return source.search(domain, limit=limit, order=order)

    def _loan_domain(self, faculty):
        return [("faculty_id", "=", faculty.id), ("library_card_id.faculty_id", "=", faculty.id),
                ("type", "=", "faculty"), ("company_id", "=", self.env.company.id)]

    @api.model
    def get_workspace(self):
        faculty = self._faculty()
        today = fields.Date.context_today(self)
        copies = self._records("op.media.unit", [("campus_company_id", "=", self.env.company.id), ("media_id.active", "=", True)])
        loans = self._records("op.media.movement", self._loan_domain(faculty), order="issued_date desc, id desc")
        cards = self._records("op.library.card", [("faculty_id", "=", faculty.id), ("type", "=", "faculty")])
        requests = self.env["campus.service.request"].search([("requester_id", "=", self.env.uid),
            ("company_id", "=", self.env.company.id), ("kind", "=", "library"),
            ("state", "in", ["submitted", "approved"]), ("campus_library_loan_id", "in", loans.ids)])
        pending = set(requests.campus_library_loan_id.ids)
        rows = []
        for copy in copies:
            media = copy.media_id
            department = media.campus_department or ", ".join(media.subject_ids.department_id.mapped("name")) or "General"
            rows.append({"id": copy.id, "media_id": media.id, "code": copy.campus_accession_number or media.internal_code or copy.barcode or "—",
                "title": media.name, "author": ", ".join(media.author_ids.mapped("name")) or "—",
                "publisher": ", ".join(media.publisher_ids.mapped("name")) or "—", "year": media.campus_publication_year or "—",
                "department": department, "subject": ", ".join(media.subject_ids.mapped("name")) or department,
                "edition": media.edition or "—", "call": media.campus_call_number or "—", "rack": copy.campus_rack or "—",
                "location": copy.campus_location or "—", "status": "Available" if copy.state == "available" else "Issued"})
        loan_rows = []
        for loan in loans:
            loan_rows.append({"id": loan.id, "code": loan.media_unit_id.campus_accession_number or loan.media_id.internal_code or loan.media_unit_id.barcode,
                "title": loan.media_id.name, "issue": str(loan.issued_date), "due": str(loan.return_date),
                "returned": str(loan.actual_return_date) if loan.actual_return_date else "",
                "status": "Renewal pending" if loan.id in pending and loan.state == "issue" else "Issued" if loan.state == "issue"
                    else "Returned" if loan.state in {"return", "return_done"} else dict(loan._fields["state"].selection)[loan.state],
                "can_renew": loan.state == "issue" and loan.id not in pending,
                "overdue": loan.state == "issue" and loan.return_date < today})
        current = loans.filtered(lambda row: row.state == "issue")
        due = current.filtered(lambda row: today <= row.return_date <= today + timedelta(days=7))
        fine = sum(loan.invoice_id.amount_residual if loan.invoice_id and loan.invoice_id.state == "posted"
                   else loan.penalty if not loan.invoice_id else 0 for loan in loans)
        materials = self._records("campus.digital.resource", [("company_id", "=", self.env.company.id), ("state", "=", "approved")])
        desk_allowed = False
        try:
            desk_allowed = bool(self.env["campus.responsibility"]._library_scope())
        except AccessError:
            pass
        lms = self.env["ideastone.lms.workspace"].configuration()
        return {"today": str(today), "company": self.env.company.name, "demo": self.env.company.campus_demo,
            "staff": {"name": faculty.name, "code": faculty.campus_staff_code or "Not assigned",
                "department": faculty.main_department_id.name or "Not assigned", "email": faculty.email or self.env.user.email or "Not recorded",
                "active": bool(cards), "limit": sum(cards.library_card_type_id.mapped("allow_media")),
                "duration": ", ".join(str(value) for value in sorted(set(cards.library_card_type_id.mapped("duration"))))},
            "books": rows, "loans": loan_rows,
            "counts": {"total": len(rows), "available": len({row["media_id"] for row in rows if row["status"] == "Available"}),
                "issued": sum(row["status"] == "Issued" for row in rows), "own": len(current), "due": len(due),
                "pending": len(pending.intersection(current.ids)), "eligible": sum(row["can_renew"] for row in loan_rows), "fine": fine},
            "resources": [{"id": resource.id, "name": resource.name, "author": resource.author or "",
                "description": resource.description or "", "filename": resource.filename,
                "type": dict(resource._fields["resource_type"].selection)[resource.resource_type],
                "url": "/my/campus/resource/%s" % resource.id} for resource in materials],
            "lms_url": lms["url"], "sso": bool(self.env.user.oauth_provider_id), "desk_allowed": desk_allowed}

    @api.model
    def request_renewal(self, loan_id):
        faculty = self._faculty()
        if type(loan_id) is not int or not 0 < loan_id <= 2147483647:
            raise ValidationError(_("Choose a valid loan."))
        loan = self.env["op.media.movement"].sudo().search(self._loan_domain(faculty) + [("id", "=", loan_id)], limit=1)
        if not loan:
            raise AccessError(_("Choose an active loan from your own library account in this college."))
        self.env.cr.execute("SELECT id FROM op_media_movement WHERE id=%s FOR UPDATE", [loan.id])
        loan.invalidate_recordset()
        if loan.state != "issue":
            raise ValidationError(_("Only an issued item can be renewed."))
        request = self.env["campus.service.request"].search([("requester_id", "=", self.env.uid),
            ("company_id", "=", self.env.company.id), ("kind", "=", "library"),
            ("campus_library_loan_id", "=", loan.id), ("state", "in", ["draft", "submitted", "approved"])], limit=1)
        if not request:
            request = self.env["campus.service.request"].create({"name": _("Library renewal: %s", loan.media_id.name),
                "kind": "library", "company_id": self.env.company.id, "requester_id": self.env.uid,
                "faculty_id": faculty.id, "campus_library_loan_id": loan.id,
                "description": _("Please review a renewal for %s. Current due date: %s. Loan reference: %s.", loan.media_id.name, loan.return_date, loan.id)})
        if request.state == "draft":
            request.action_submit()
        return True

    @api.model
    def request_assistance(self, note):
        faculty = self._faculty()
        if not isinstance(note, str) or not note.strip() or len(note) > 4000:
            raise ValidationError(_("Enter a library enquiry within 4,000 characters."))
        request = self.env["campus.service.request"].create({"name": _("Library desk assistance"), "kind": "library",
            "requester_id": self.env.uid, "company_id": self.env.company.id, "faculty_id": faculty.id, "description": note.strip()})
        request.action_submit()
        return True


class LibraryMediaMetadata(models.Model):
    _inherit = "op.media"

    campus_publication_year = fields.Integer(string="Publication year")
    campus_call_number = fields.Char(string="Call number")
    campus_department = fields.Char(string="Department / subject area")


class LibraryCopyMetadata(models.Model):
    _inherit = "op.media.unit"

    campus_accession_number = fields.Char(string="Accession number", index=True)
    campus_location = fields.Char(string="Library location")
    campus_rack = fields.Char(string="Rack / shelf")


class LibraryServiceRequest(models.Model):
    _inherit = "campus.service.request"

    kind = fields.Selection(selection_add=[("library", "Library assistance")], ondelete={"library": "set default"})
    campus_library_loan_id = fields.Many2one("op.media.movement", string="Library loan", readonly=True, ondelete="restrict", index=True)

    @api.constrains("campus_library_loan_id", "company_id", "requester_id", "faculty_id", "kind")
    def _check_library_loan(self):
        for request in self:
            loan = request.campus_library_loan_id.sudo()
            if loan and (request.kind != "library" or loan.company_id != request.company_id or loan.faculty_id != request.faculty_id
                         or loan.faculty_id.user_id != request.requester_id or loan.library_card_id.faculty_id != request.faculty_id):
                raise ValidationError(_("A renewal must reference the requester's own faculty loan in the same college."))
