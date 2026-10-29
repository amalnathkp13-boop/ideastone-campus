from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class ServiceRequest(models.Model):
    _name = "campus.service.request"
    _description = "Staff and student service requests"
    _inherit = "campus.approval"
    _order = "date desc"

    requester_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="restrict")
    kind = fields.Selection([
        ("grievance", "Grievance"), ("certificate", "TC / conduct certificate"),
        ("transfer", "Programme transfer"), ("alternate", "Alternate teaching hour"),
        ("room", "Room request"), ("travel", "Travel proposal"), ("training", "Training request"),
        ("work", "Work / service order"), ("advance", "Payment / salary advance proposal"),
        ("student_complaint", "Complaint on a student"),
    ], required=True, default="grievance")
    student_id = fields.Many2one("op.student", ondelete="restrict")
    faculty_id = fields.Many2one("op.faculty", ondelete="restrict")
    replacement_id = fields.Many2one("op.faculty", string="Replacement faculty", ondelete="restrict")
    department_id = fields.Many2one("op.department", ondelete="restrict")
    requested_course_id = fields.Many2one("op.course", string="Requested programme", ondelete="restrict")
    date = fields.Date(required=True, default=fields.Date.today)
    date_from = fields.Date()
    date_to = fields.Date()
    amount = fields.Monetary()
    description = fields.Text(required=True)
    resolution = fields.Text()
    complaint_category = fields.Char()
    grievance_category = fields.Selection([
        ("facilities", "Facilities"), ("it", "IT Support"),
        ("payroll", "Payroll"), ("academic", "Academic Administration"),
    ], string="Grievance category")
    grievance_priority = fields.Selection([
        ("low", "Low"), ("medium", "Medium"), ("high", "High"),
    ], default="medium", string="Grievance priority")
    grievance_incident_date = fields.Date(string="Date of incident")
    grievance_contact = fields.Char(string="Preferred contact / extension")
    document = fields.Binary(attachment=True)
    filename = fields.Char()

    def _faculty_self_service(self):
        return not self.env.su and self.env.user.has_group("openeducat_core.group_op_faculty") and not (
            self.env.user.has_group("ideastone_erp.group_services") or self.env.user.has_group("ideastone_erp.group_manager")
        )

    @api.model_create_multi
    def create(self, vals_list):
        if self._faculty_self_service():
            if any(v.get("requester_id", self.env.uid) != self.env.uid for v in vals_list):
                raise AccessError(_("Submit service requests under your own account."))
        return super().create(vals_list)

    def write(self, vals):
        if "requester_id" in vals and self._faculty_self_service():
            raise AccessError(_("A service operator must reassign a faculty service request."))
        return super().write(vals)

    @api.constrains("date_from", "date_to", "amount", "kind", "requested_course_id", "student_id", "complaint_category", "company_id")
    def _check_values(self):
        for rec in self:
            if rec.amount < 0 or rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Check the amount and request date range."))
            if rec.kind == "transfer" and (not rec.student_id or not rec.requested_course_id):
                raise ValidationError(_("Programme transfer requires a student and destination programme."))
            if rec.kind == "student_complaint" and (not rec.student_id or not rec.complaint_category):
                raise ValidationError(_("A student complaint requires the student, complaint type and description."))
            if rec.student_id.company_id and rec.student_id.company_id != rec.company_id:
                raise ValidationError(_("The student and service request must belong to the same college."))

    def _validate_transition(self, target):
        if target == "done" and not self.resolution:
            raise ValidationError(_("Record the resolution before completing a service request."))

    def _check_grievance_faculty(self):
        if not self.env.user.has_group("openeducat_core.group_op_faculty") or not self.env["op.faculty"].search_count([
            ("user_id", "=", self.env.uid), "|", ("company_id", "=", False),
            ("company_id", "=", self.env.company.id),
        ]):
            raise AccessError(_("A linked faculty account is required."))

    @api.model
    def faculty_grievance_snapshot(self):
        self._check_grievance_faculty()
        self.check_access_rights("read")
        records = self.search([("kind", "=", "grievance"), ("requester_id", "=", self.env.uid),
                               ("company_id", "=", self.env.company.id)], order="create_date desc, id desc")
        categories = dict(self._fields["grievance_category"].selection)
        priorities = dict(self._fields["grievance_priority"].selection)
        states = {"draft": ("Open", "open"), "submitted": ("Open", "open"),
                  "approved": ("In progress", "progress"), "done": ("Resolved", "resolved"),
                  "cancelled": ("Closed", "closed")}
        rows = []
        for record in records:
            status, tone = states[record.state]
            rows.append({"id": record.id, "reference": f"GRV-{record.date.year}-{record.id:03d}",
                         "subject": record.name, "category": categories.get(record.grievance_category, "General"),
                         "date": fields.Date.to_string(record.date),
                         "incident_date": fields.Date.to_string(record.grievance_incident_date) if record.grievance_incident_date else "",
                         "priority": priorities.get(record.grievance_priority, "Medium"),
                         "status": status, "tone": tone, "description": record.description,
                         "resolution": record.resolution or "", "contact": record.grievance_contact or ""})
        return {"rows": rows, "today": fields.Date.to_string(fields.Date.context_today(self)),
                "company": self.env.company.name}

    @api.model
    def faculty_grievance_submit(self, values):
        self._check_grievance_faculty()
        self.check_access_rights("create")
        if not isinstance(values, dict):
            raise ValidationError(_("Enter the grievance details."))
        subject = str(values.get("subject") or "").strip()
        description = str(values.get("description") or "").strip()
        category = values.get("category")
        priority = values.get("priority")
        contact = str(values.get("contact") or "").strip()
        if not subject or len(subject) > 200 or not description or len(description) > 5000 or len(contact) > 200:
            raise ValidationError(_("Enter a subject and description within the allowed lengths."))
        if category not in dict(self._fields["grievance_category"].selection) or priority not in dict(self._fields["grievance_priority"].selection):
            raise ValidationError(_("Choose a valid category and priority."))
        incident = values.get("incident_date")
        incident_date = fields.Date.to_date(incident) if incident else False
        if incident_date and incident_date > fields.Date.context_today(self):
            raise ValidationError(_("The incident date cannot be in the future."))
        record = self.create({"name": subject, "description": description, "kind": "grievance",
                              "requester_id": self.env.uid, "date": fields.Date.context_today(self),
                              "grievance_category": category, "grievance_priority": priority,
                              "grievance_incident_date": incident_date, "grievance_contact": contact})
        record.action_submit()
        return record.id
