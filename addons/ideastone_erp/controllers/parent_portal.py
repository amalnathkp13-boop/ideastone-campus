import base64
from urllib.parse import urlencode

from markupsafe import Markup
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request
from odoo.tools.misc import format_amount

from odoo import http

from .student_portal import StudentWorkspace


class ParentWorkspace(StudentWorkspace):
    def _parent_login(self):
        user = request.env.user
        return user.has_group("base.group_portal") and not user.has_group("base.group_user") and (
            user.is_parent or user.child_ids or request.env["op.parent"].sudo().with_context(active_test=False).search_count([("user_id", "=", user.id)]))

    @http.route()
    def campus(self, student=None, page=1, **kw):
        if self._parent_login():
            if student and not kw.get("child"):
                kw["child"] = student
            return self.parent_page("dashboard", **kw)
        return super().campus(student, page, **kw)

    @http.route("/my/campus/parent/<string:section>", type="http", auth="user", website=True, methods=["GET"])
    def parent_page(self, section="dashboard", **kw):
        service = request.env["campus.parent.portal"]
        data, error, status = None, "", 200
        try:
            data = service.snapshot(kw.get("child"), kw.get("enrolment"), kw.get("date_from"), kw.get("date_to"))
            if section not in {item[0] for item in data["navigation"]}:
                return self._private(request.make_response("Page not available.", status=404))
        except (AccessError, UserError) as exc:
            error, status = str(exc), 403 if isinstance(exc, AccessError) else 400
        suffix = "?" + urlencode(data["filters"]) if data else ""
        company = service.with_context(parent_child=data["student_id"])._identity().company_id if data else request.env.company
        return self._private(request.render("ideastone_erp.parent_workspace", {
            "portal_data": data, "portal_error": error, "section": section,
            "saved": bool(kw.get("saved")), "form_error": str(kw.get("form_error") or "")[:500],
            "student_url_for": lambda page: "/my/campus/parent/" + page + suffix,
            "money": lambda amount: format_amount(request.env, amount, company.currency_id),
            "notice_body": lambda text: Markup(text),
        }, status=status))

    @http.route("/my/campus/parent/action", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def parent_action(self, operation="", return_to="dashboard", **kw):
        allowed = {"dashboard", "profile", "attendance", "learning", "timetable", "exams", "fees", "notices", "requests", "documents", "account"}
        return_to = return_to if return_to in allowed else "dashboard"
        try:
            if not kw.get("child"):
                raise AccessError("Choose a linked child before submitting.")
            payload = {k: v for k, v in kw.items() if k not in {"child", "csrf_token", "enrolment", "date_from", "date_to", "file"}}
            if operation == "notice":
                payload["read"] = kw.get("read") != "false"
            elif operation == "preferences":
                payload = {"notice_badge": kw.get("notice_badge") == "on"}
            upload = request.httprequest.files.get("file")
            if upload and upload.filename:
                payload.update(file=base64.b64encode(upload.read(10 * 1024 * 1024 + 1)), filename=upload.filename)
            request.env["campus.parent.portal"].act(operation, kw["child"], payload)
            query = {"saved": "1"}
        except (UserError, ValueError, TypeError) as exc:
            query = {"form_error": str(exc)}
        query.update({key: kw[key] for key in ["child", "enrolment", "date_from", "date_to"] if kw.get(key)})
        return self._private(request.redirect("/my/campus/parent/" + return_to + "?" + urlencode(query)))

    @http.route("/my/campus/parent/download/<string:kind>/<int:record_id>", type="http", auth="user", methods=["GET"])
    def parent_download(self, kind, record_id, child=None, **kw):
        try:
            if not child:
                raise AccessError("Choose a child.")
            content, name, mimetype = request.env["campus.parent.portal"].with_context(parent_child=child)._download(kind, record_id)
        except (AccessError, UserError):
            return self._private(request.make_response("This document is not available.", status=404))
        return self._private(request.make_response(content, headers=[("Content-Type", mimetype), ("Content-Disposition", content_disposition(name))]))

    @http.route()
    def service_request(self, student=None, kind="grievance", title="", description="", **kw):
        if self._parent_login():
            return self._private(request.redirect("/my/campus/parent/requests"))
        return super().service_request(student, kind, title, description, **kw)

    @http.route()
    def feedback(self, student=None, period="", score=None, comments="", **kw):
        if self._parent_login():
            return self._private(request.redirect("/my/campus/parent/requests"))
        return super().feedback(student, period, score, comments, **kw)

    @http.route()
    def library(self, search="", page=1, **kw):
        if self._parent_login():
            return self._private(request.redirect("/my/campus/parent/learning"))
        return super().library(search, page, **kw)

    @http.route()
    def resource(self, resource_id, **kw):
        if self._parent_login():
            return self._private(request.redirect("/my/campus/parent/learning"))
        return super().resource(resource_id, **kw)
