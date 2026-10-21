from odoo import api, fields, models


class StudentRequestDetails(models.Model):
    _inherit = "campus.service.request"

    portal_requested_office = fields.Selection([
        ("auto", "Route automatically"), ("department", "Class advisor / department"),
        ("academic", "Academic office"), ("examinations", "Examination cell"),
        ("accounts", "Accounts office"), ("affairs", "Student affairs"),
        ("library", "Library"), ("it", "IT / ERP support"),
    ], default="auto", required=True, string="Student office preference")
    portal_priority = fields.Selection([
        ("normal", "Normal"), ("deadline", "Deadline approaching"), ("time_sensitive", "Time-sensitive"),
    ], default="normal", required=True, string="Student requested priority")


class StudentRequestsUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        student = self._identity()
        records = {record.id: record for record in self._requests(student)}
        request_model = self.env["campus.service.request"]
        offices = dict(request_model._fields["portal_requested_office"].selection)
        priorities = dict(request_model._fields["portal_priority"].selection)
        rows = []
        for source in data["requests"]:
            record = records[source["id"]]
            rows.append(dict(source, office=offices[record.portal_requested_office],
                             priority=priorities[record.portal_priority],
                             tone="review" if source["state"] == "information" else "rejected" if source["state"] == "rejected" else "" if source["state"] in {"approved", "ready", "done"} else "closed"))
        types = self._types(student)
        by_code = {record.code: record for record in types}
        support = by_code.get("support")
        aliases = {"course_completion": {"course completion", "course completion certificate"},
                   "transcript": {"transcript / marksheet", "transcript / marks memo", "transcript", "marksheet request"},
                   "id_replacement": {"id card replacement", "id card issue / replacement"}}
        cards = []
        for code, title, description, note, icon, tone in [
            ("bonafide", "Bonafide certificate", "For bank, scholarship, travel, internship or other official purposes. Mention the purpose and any format required by the receiving organisation.", "May require student identity and current enrolment verification.", "file-text-o", "blue"),
            ("conduct", "Conduct certificate", "An official conduct/character document issued by the authorised college office after verification.", "Eligibility and processing time are determined by the college.", "check", "green"),
            ("course_completion", "Course completion", "For students who have met the applicable academic and administrative requirements.", "Final eligibility must be confirmed by the academic office.", "graduation-cap", "violet"),
            ("transcript", "Transcript / marksheet", "Request an official transcript or guidance for duplicate marksheet procedures.", "The examination cell may require semester, register number and document type.", "list-alt", "amber"),
            ("transfer", "Transfer certificate", "Ask about eligibility, clearance and the forms required by the college.", "The college office confirms the applicable procedure.", "exchange", "blue"),
            ("id_replacement", "ID card / record update", "Report a lost or damaged ID card. Choose Profile correction in the request form for changes to a student record.", "Attach evidence when required by the relevant office.", "id-card-o", "red"),
        ]:
            names = aliases.get(code, {title.casefold()})
            kind = by_code.get(code) or next((record for record in types if record.name.strip().casefold() in names), None)
            target = kind or support
            cards.append({"name": title, "description": description, "note": note, "icon": icon, "tone": tone,
                          "type_id": target.id if target else False, "enquiry": not bool(kind),
                          "button": "Request certificate" if code in {"bonafide", "conduct", "course_completion"} else "Start request" if code == "id_replacement" else "Request document",
                          "title": ("Request for " if kind else "Enquiry about ") + title})
        data["request_ui"] = {"rows": rows, "recent": rows[:3], "total": len(rows),
            "review": sum(row["state"] in {"draft", "submitted", "information"} for row in rows),
            "completed": sum(row["state"] == "done" for row in rows),
            "certificate_count": len(types.filtered(lambda item: item.kind == "certificate")),
            "cards": cards, "offices": list(offices.items()), "priorities": list(priorities.items()),
            "states": list(request_model._fields["state"].selection),
            "categories": sorted({(row["type_id"], row["type"]) for row in rows}, key=lambda item: item[1])}
        return data
