from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class FacultyCampusServices(models.AbstractModel):
    _name = "campus.faculty.services.ui"
    _description = "Faculty campus services workspace"

    def _check_faculty(self):
        if not self.env.user.has_group("openeducat_core.group_op_faculty") or not self.env.user.active:
            raise AccessError(_("An active faculty account is required."))

    @api.model
    def get_page_data(self, page="service"):
        self._check_faculty()
        if page not in {"service", "leave", "maintenance", "complaint"}:
            raise ValidationError(_("Unknown campus services page."))
        rows = []
        if page == "leave":
            records = self.env["campus.student.leave"].search([
                ("company_id", "=", self.env.company.id),
                "|", "|", ("advisor_id", "=", self.env.uid), ("hod_id", "=", self.env.uid),
                ("principal_id", "=", self.env.uid),
            ], order="create_date desc, id desc", limit=150)
            for rec in records:
                placement = rec.student_id.course_detail_ids.filtered(lambda row: row.company_id == self.env.company and row.state == "running")[:1]
                rows.append({"id": rec.id, "code": f"LVA-{rec.id:05d}", "subject": rec.student_id.name,
                             "category": placement.course_id.name or "—", "date": str(rec.date),
                             "due": str(rec.deadline), "team": rec.advisor_id.name,
                             "status": dict(rec._fields["state"].selection).get(rec.state, rec.state),
                             "state": rec.state, "priority": "Normal", "can_decide": rec.can_decide,
                             "reason": rec.reason or ""})
        else:
            domain = [("company_id", "=", self.env.company.id), ("requester_id", "=", self.env.uid)]
            if page == "complaint":
                domain.append(("kind", "=", "student_complaint"))
            elif page == "maintenance":
                domain += [("kind", "=", "work"), ("service_area", "=", "maintenance")]
            else:
                domain += [("kind", "=", "work"), ("service_area", "!=", "maintenance")]
            records = self.env["campus.service.request"].search(domain, order="create_date desc, id desc", limit=150)
            categories = dict(records._fields["service_category"].selection)
            priorities = dict(records._fields["service_priority"].selection)
            statuses = {"draft": "Submitted", "submitted": "Pending approval", "approved": "In progress",
                        "done": "Resolved", "cancelled": "Cancelled"}
            for rec in records:
                rows.append({"id": rec.id, "code": f"{'STC' if page == 'complaint' else 'MWO' if page == 'maintenance' else 'CSR'}-{rec.id:05d}",
                             "subject": rec.name, "category": rec.complaint_category if page == "complaint" else categories.get(rec.service_category, "—"),
                             "date": str(rec.date), "due": str(rec.date_to) if rec.date_to else "—",
                             "team": rec.service_team or "Awaiting assignment", "priority": priorities.get(rec.service_priority, "Normal"),
                             "status": statuses.get(rec.state, rec.state), "state": rec.state,
                             "location": rec.service_location or "", "requester": rec.requester_id.name,
                             "student": rec.student_id.name or ""})
        return {"rows": rows, "today": str(fields.Date.context_today(self)), "company": self.env.company.name}

    @api.model
    def submit_request(self, page, payload):
        self._check_faculty()
        if page not in {"service", "maintenance", "complaint"}:
            raise ValidationError(_("Choose a request type."))
        name = (payload.get("subject") or "").strip()
        description = (payload.get("description") or "").strip()
        if not name or not description or len(name) > 200:
            raise ValidationError(_("Enter a subject and a description."))
        vals = {"name": name, "description": description, "company_id": self.env.company.id,
                "requester_id": self.env.uid, "kind": "student_complaint" if page == "complaint" else "work",
                "service_area": "maintenance" if page == "maintenance" else "service"}
        if page == "complaint":
            student_number = (payload.get("student_number") or "").strip()
            category = (payload.get("complaint_category") or "").strip()
            student = self.env["op.student"].search([
                ("company_id", "=", self.env.company.id), ("gr_no", "=", student_number),
            ], limit=1)
            if not student or not category:
                raise ValidationError(_("Enter a valid student register number and concern category."))
            vals.update(student_id=student.id, complaint_category=category)
        else:
            category = payload.get("category")
            priority = payload.get("priority") or "normal"
            location = (payload.get("location") or "").strip()
            if category not in dict(self.env["campus.service.request"]._fields["service_category"].selection) or priority not in {"low", "normal", "high", "urgent"} or not location:
                raise ValidationError(_("Enter a category, priority, and location."))
            vals.update(service_category=category, service_priority=priority, service_location=location,
                        service_contact=(payload.get("contact") or "").strip()[:100])
            if payload.get("needed_by"):
                vals["date_to"] = fields.Date.to_date(payload["needed_by"])
        request = self.env["campus.service.request"].create(vals)
        request.action_submit()
        return {"id": request.id, "code": f"{'STC' if page == 'complaint' else 'MWO' if page == 'maintenance' else 'CSR'}-{request.id:05d}"}

    @api.model
    def decide_leave(self, record_id, decision, reason=""):
        self._check_faculty()
        if decision not in {"approve", "reject"}:
            raise ValidationError(_("Choose approve or reject."))
        record = self.env["campus.student.leave"].browse(int(record_id)).exists()
        record.check_access_rights("write")
        record.check_access_rule("write")
        if not record or record.company_id != self.env.company or not record.can_decide:
            raise AccessError(_("This leave request is not assigned to you for review."))
        if reason.strip():
            record.write({"decision_reason": reason.strip()})
        if decision == "approve":
            record.action_approve()
        else:
            record.action_reject()
        return True
