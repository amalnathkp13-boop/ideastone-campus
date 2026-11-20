import hashlib
import json
import secrets

from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request

from odoo import http, tools

from ..models.student_learning_studio import LearningRevisionConflict
from .student_portal import StudentWorkspace


class StudentLearningStudio(StudentWorkspace):
    """Serve the reference's isolated learning theme within the existing portal shell."""

    def _learning_json(self, value, status=200):
        return self._private(request.make_response(
            json.dumps(value, ensure_ascii=False), status=status,
            headers=[("Content-Type", "application/json; charset=utf-8")]))

    def _learning_error(self, exc):
        status = 409 if isinstance(exc, LearningRevisionConflict) else 403 if isinstance(exc, AccessError) else 400
        return self._learning_json({"error": str(exc)}, status)

    @http.route("/my/campus/student/lms/workspace", type="http", auth="user", methods=["GET"])
    def learning_workspace(self, **kw):
        try:
            service = request.env["campus.student.portal"]
            bootstrap = service._learning_snapshot()
            bootstrap["csrfToken"] = request.csrf_token()
            bootstrap["preview"] = bool(service._identity().company_id.campus_demo)
        except (AccessError, UserError) as exc:
            return self._learning_error(exc)
        with tools.file_open("ideastone_erp/static/src/learning_studio/workspace.html", "r") as source:
            html = source.read()
        for filename in ("workspace.css", "workspace.js"):
            asset = "ideastone_erp/static/src/learning_studio/" + filename
            with tools.file_open(asset, "rb") as source:
                version = hashlib.sha256(source.read()).hexdigest()[:16]
            html = html.replace('"/' + asset + '"', '"/' + asset + '?v=' + version + '"')
        nonce = secrets.token_urlsafe(24)
        serialized = json.dumps(bootstrap, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        html = html.replace("<!-- LEARNING_STUDIO_BOOTSTRAP -->", f'<script nonce="{nonce}">window.LEARNING_STUDIO_BOOTSTRAP={serialized};</script>')
        response = self._private(request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")]))
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; media-src 'self' data: blob:; font-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'"
        )
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    @http.route("/my/campus/student/lms/state", type="http", auth="user", methods=["POST"], csrf=True)
    def learning_save(self, state="", revision="", **kw):
        try:
            if not isinstance(state, str) or len(state.encode()) > 1024 * 1024:
                raise UserError("Keep the learning record within 1 MB.")
            result = request.env["campus.student.portal"]._learning_save(json.loads(state), int(revision))
            return self._learning_json(result)
        except (AccessError, UserError, ValueError, TypeError) as exc:
            return self._learning_error(exc)

    @http.route("/my/campus/student/lms/files", type="http", auth="user", methods=["GET", "POST"], csrf=True)
    def learning_files(self, **kw):
        try:
            service = request.env["campus.student.portal"]
            if request.httprequest.method == "POST":
                upload = request.httprequest.files.get("file")
                if not upload or not upload.filename:
                    raise UserError("Choose a file to upload.")
                service._learning_add_file(upload.read(16 * 1024 * 1024 + 1), upload.filename)
            return self._learning_json({"files": service._learning_files()})
        except (AccessError, UserError, ValueError, TypeError) as exc:
            return self._learning_error(exc)

    @http.route("/my/campus/student/lms/files/<int:file_id>", type="http", auth="user", methods=["GET"])
    def learning_download(self, file_id, **kw):
        try:
            raw, name, mimetype = request.env["campus.student.portal"]._learning_download_file(file_id)
            return self._private(request.make_response(raw, headers=[
                ("Content-Type", mimetype), ("Content-Disposition", content_disposition(name)),
                ("Content-Security-Policy", "sandbox")]))
        except (AccessError, UserError):
            return self._private(request.make_response("This file is not available.", status=404))

    @http.route("/my/campus/student/lms/files/<int:file_id>/delete", type="http", auth="user", methods=["POST"], csrf=True)
    def learning_delete(self, file_id, **kw):
        try:
            service = request.env["campus.student.portal"]
            service._learning_delete_file(file_id)
            return self._learning_json({"files": service._learning_files()})
        except (AccessError, UserError):
            return self._learning_json({"error": "This file is not available."}, 404)
