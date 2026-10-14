import base64
from urllib.parse import urlencode

from odoo.http import content_disposition, request

from odoo import fields, http


class CampusPortal(http.Controller):
    def _students(self):
        user = request.env.user
        # The parent-child relationship is an existing OpenEduCat identity mapping.
        return request.env["op.student"].sudo().search([
            ("user_id", "in", [user.id] + user.child_ids.ids),
            "|", ("company_id", "=", False), ("company_id", "=", request.env.company.id),
        ])

    def _student(self, value):
        students = self._students()
        try:
            selected = students.filtered(lambda s: s.id == int(value)) if value else students[:1]
        except (TypeError, ValueError):
            selected = students.browse()
        return selected[:1]

    @http.route("/my/campus", type="http", auth="user", website=True, methods=["GET"])
    def campus(self, student=None, page=1, **kw):
        selected = self._student(student)
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        offset = (page - 1) * 20
        company = request.env.company
        today = fields.Date.today()
        values = {"students": self._students(), "selected": selected, "page": page,
                  "success": kw.get("success"), "error": kw.get("error"), "attendance_count": 0,
                  "attendance_present": 0, "marks": [], "invoices": [], "mentoring": [],
                  "requests": [], "lessons": [], "next_page": None}
        audiences = ["all"]
        if selected:
            audiences.append("student" if selected.user_id == request.env.user else "parent")
        faculty = request.env["op.faculty"].sudo().search([("user_id", "=", request.env.uid)], limit=1)
        if faculty:
            audiences.append("faculty")
        values["circulars"] = request.env["campus.circular"].sudo().search([
            ("company_id", "=", company.id), ("state", "=", "approved"),
            ("audience", "in", audiences), ("date_from", "<=", today),
            "|", ("date_to", "=", False), ("date_to", ">=", today),
        ], limit=20)
        if selected:
            lines = request.env["op.attendance.line"].sudo()
            own = [("student_id", "=", selected.id)]
            values["attendance_count"] = lines.search_count(own)
            values["attendance_present"] = lines.search_count(own + [("present", "=", True)])
            result_model = request.env["op.result.line"].sudo()
            # Publish only finalized exam results; raw evaluator marks stay private.
            result_domain = own + [("exam_id.state", "=", "done")]
            values["marks"] = result_model.search(result_domain, offset=offset, limit=20, order="id desc")
            invoices = request.env["account.move"].sudo().search([
                ("company_id", "=", company.id), ("partner_id", "=", selected.partner_id.id),
                ("move_type", "in", ["out_invoice", "out_refund"]), ("state", "=", "posted"),
            ], limit=20, order="invoice_date desc, id desc")
            values["invoices"] = invoices
            values["mentoring"] = request.env["campus.counseling"].sudo().search(own + [("company_id", "=", company.id)], limit=20)
            values["requests"] = request.env["campus.service.request"].sudo().search([
                ("requester_id", "=", request.env.uid), ("company_id", "=", company.id),
            ], limit=20, order="id desc")
            batches = selected.course_detail_ids.batch_id.ids
            values["lessons"] = request.env["campus.teaching.plan"].sudo().search([
                ("company_id", "=", company.id), ("batch_id", "in", batches),
            ], limit=20)
            if result_model.search_count(result_domain) > offset + 20:
                values["next_page"] = "/my/campus?" + urlencode({"student": selected.id, "page": page + 1})
        return request.render("ideastone_erp.portal_campus", values)

    @http.route("/my/campus/feedback", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def feedback(self, student=None, period="", score=None, comments="", **kw):
        selected = self._student(student)
        try:
            score = int(score)
            if not selected or not period.strip() or len(period) > 80 or not 1 <= score <= 5 or len(comments) > 5000:
                raise ValueError()
        except (TypeError, ValueError):
            return request.redirect("/my/campus?error=invalid_feedback")
        domain = [("respondent_id", "=", request.env.uid), ("company_id", "=", request.env.company.id),
                  ("period", "=", period.strip()), ("faculty_id", "=", False)]
        kind = "student" if selected.user_id == request.env.user else "parent"
        if request.env["campus.feedback"].sudo().search_count(domain + [("kind", "=", kind)]):
            return request.redirect("/my/campus?error=duplicate_feedback")
        request.env["campus.feedback"].sudo().create({
            "name": f"Institutional feedback — {period.strip()}", "respondent_id": request.env.uid,
            "company_id": request.env.company.id, "student_id": selected.id, "kind": kind,
            "period": period.strip(), "score": score, "comments": comments,
        })
        return request.redirect("/my/campus?success=feedback")

    @http.route("/my/campus/request", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def service_request(self, student=None, kind="grievance", title="", description="", **kw):
        selected = self._student(student)
        if not selected or kind not in {"grievance", "certificate", "training"} or not title.strip() or not description.strip() or len(title) > 200 or len(description) > 5000:
            return request.redirect("/my/campus?error=invalid_request")
        rec = request.env["campus.service.request"].sudo().create({
            "name": title.strip(), "requester_id": request.env.uid, "student_id": selected.id,
            "company_id": request.env.company.id, "kind": kind, "description": description.strip(),
        })
        rec.action_submit()
        return request.redirect("/my/campus?success=request")

    def _resources(self):
        students = self._students()
        batches = students.course_detail_ids.batch_id.ids
        faculty = request.env["op.faculty"].sudo().search_count([("user_id", "=", request.env.uid)])
        if not students and not faculty:
            return request.env["campus.digital.resource"].sudo().browse()
        domain = [("company_id", "=", request.env.company.id), ("state", "=", "approved")]
        if not faculty:
            domain += ["|", ("batch_ids", "=", False), ("batch_ids", "in", batches)]
        return request.env["campus.digital.resource"].sudo().search(domain)

    @http.route("/my/campus/library", type="http", auth="user", website=True, methods=["GET"])
    def library(self, search="", page=1, **kw):
        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1
        domain = [("name", "ilike", search[:200])] if search else []
        catalogue = request.env["op.media"].sudo()
        total = catalogue.search_count(domain)
        resources = self._resources()
        return request.render("ideastone_erp.portal_library", {
            "books": catalogue.search(domain, offset=(page - 1) * 20, limit=20, order="name"),
            "resources": resources, "search": search, "page": page,
            "next_page": "/my/campus/library?" + urlencode({"search": search, "page": page + 1}) if total > page * 20 else None,
        })

    @http.route("/my/campus/resource/<int:resource_id>", type="http", auth="user", methods=["GET"])
    def resource(self, resource_id, **kw):
        resource = self._resources().filtered(lambda r: r.id == resource_id)[:1]
        if not resource or not resource.document:
            return request.not_found()
        return request.make_response(base64.b64decode(resource.document), headers=[
            ("Content-Type", "application/octet-stream"), ("Content-Disposition", content_disposition(resource.filename)),
            ("X-Content-Type-Options", "nosniff"), ("Cache-Control", "private, no-store"),
        ])
