import base64
from urllib.parse import urlencode

from markupsafe import Markup
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request
from odoo.tools.misc import format_amount

from odoo import http

from .portal import CampusPortal


class StudentWorkspace(CampusPortal):
    def _student_login(self):
        user = request.env.user
        return user.has_group("base.group_portal") and not user.has_group("base.group_user") and not user.child_ids

    def _private(self, response):
        response.headers.update({"Cache-Control": "private, no-store, max-age=0", "Pragma": "no-cache", "Expires": "0", "Vary": "Cookie", "X-Content-Type-Options": "nosniff"})
        return response

    @http.route()
    def campus(self, student=None, page=1, **kw):
        if self._student_login():
            return self.student_page("dashboard", **kw)
        return super().campus(student, page, **kw)

    @http.route("/my/campus/student/<string:section>", type="http", auth="user", website=True, methods=["GET"])
    def student_page(self, section="dashboard", **kw):
        service = request.env["campus.student.portal"]
        data, error = None, ""
        status = 200
        try:
            data = service.snapshot(kw.get("enrolment"), kw.get("date_from"), kw.get("date_to"))
            if section not in {item[0] for item in data["navigation"]}:
                return request.not_found()
        except AccessError as exc:
            error, status = str(exc), 403 if request.httprequest.path != "/my/campus" else 200
        except UserError as exc:
            error, status = str(exc), 400
        filters = data["filters"] if data else {}
        suffix = "?" + urlencode(filters) if filters else ""
        company = service._identity().company_id if data else request.env.company
        response = request.render("ideastone_erp.student_workspace", {
            "portal_data": data, "portal_error": error, "section": section,
            "saved": bool(kw.get("saved")), "form_error": str(kw.get("form_error") or "")[:500],
            "url_for": lambda page: "/my/campus/student/" + page + suffix,
            "money": lambda amount: format_amount(request.env, amount, company.currency_id),
            "notice_body": lambda text: Markup(text), "enrolment_value": kw.get("enrolment", ""),
        }, status=status)
        return self._private(response)

    @http.route("/my/campus/student/action", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def student_action(self, operation="", return_to="dashboard", **kw):
        allowed = {"dashboard", "profile", "academics", "timetable", "attendance", "exams", "fees", "notices", "requests", "library", "help", "account"}
        return_to = return_to if return_to in allowed else "dashboard"
        service = request.env["campus.student.portal"]
        try:
            student = service._identity()
            if operation == "profile":
                ignored = {"csrf_token", "enrolment", "date_from", "date_to"}
                payload = {key: value for key, value in kw.items() if key not in ignored}
            elif operation == "preferences":
                payload = {"notice_badge": kw.get("notice_badge") == "on"}
            else:
                payload = {key: value for key, value in kw.items() if key not in {"csrf_token", "enrolment", "date_from", "date_to", "file"}}
                if operation == "notice":
                    payload["read"] = kw.get("read") != "false"
            upload = request.httprequest.files.get("file")
            if upload and upload.filename:
                # Bound before allocating/encoding untrusted multipart data.
                raw = upload.read(10 * 1024 * 1024 + 1)
                payload.update(file=base64.b64encode(raw), filename=upload.filename)
            service.with_company(student.company_id).act(operation, payload)
            query = {"saved": "1"}
        except (UserError, ValueError, TypeError) as exc:
            query = {"form_error": str(exc)}
        query.update({key: kw[key] for key in ["enrolment", "date_from", "date_to"] if kw.get(key)})
        return self._private(request.redirect("/my/campus/student/" + return_to + "?" + urlencode(query)))

    @http.route("/my/campus/student/download/<string:kind>/<int:record_id>", type="http", auth="user", methods=["GET"])
    def student_download(self, kind, record_id, **kw):
        try:
            data, name, mimetype = request.env["campus.student.portal"]._download(kind, record_id)
        except (AccessError, UserError):
            return self._private(request.not_found())
        return self._private(request.make_response(data, headers=[("Content-Type", mimetype), ("Content-Disposition", content_disposition(name))]))

    @http.route()
    def service_request(self, student=None, kind="grievance", title="", description="", **kw):
        if self._student_login():
            return self._private(request.redirect("/my/campus/student/requests"))
        return super().service_request(student, kind, title, description, **kw)

    @http.route()
    def feedback(self, student=None, period="", score=None, comments="", **kw):
        if self._student_login():
            return self.student_action("feedback", "help", period=period, score=score, comments=comments, **kw)
        return super().feedback(student, period, score, comments, **kw)

    @http.route()
    def resource(self, resource_id, **kw):
        if self._student_login():
            return self.student_download("resource", resource_id)
        return super().resource(resource_id, **kw)

    @http.route()
    def library(self, search="", page=1, **kw):
        if self._student_login():
            try:
                request.env["campus.student.portal"]._identity()
            except AccessError:
                return self._private(request.render("ideastone_erp.portal_library", {
                    "books": request.env["op.media"].browse(), "resources": request.env["campus.digital.resource"].browse(),
                    "search": "", "page": 1, "next_page": None}))
            return self.student_page("library", **kw)
        return super().library(search, page, **kw)
