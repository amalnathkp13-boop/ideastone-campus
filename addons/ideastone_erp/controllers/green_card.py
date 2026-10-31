import base64
import mimetypes

from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request

from odoo import http


class GreenCardDocuments(http.Controller):
    def _private(self, response):
        response.headers.update({"Cache-Control": "private, no-store, max-age=0", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff", "Vary": "Cookie"})
        return response

    @http.route("/my/campus/green-card/file/<int:record_id>", type="http", auth="user", methods=["GET"])
    def green_file(self, record_id, kind="support", **kw):
        try:
            record = request.env["campus.green.card.ui"]._record(record_id)
            if kind not in {"support", "proof"}:
                raise AccessError("Invalid file")
            content = record.document if kind == "support" else record.green_proof
            name = record.filename if kind == "support" else record.green_proof_name
            if not content or not name:
                return self._private(request.not_found())
            return self._private(request.make_response(base64.b64decode(content), headers=[
                ("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream"),
                ("Content-Disposition", content_disposition(name))]))
        except (AccessError, UserError):
            return self._private(request.not_found())

    @http.route("/my/campus/green-card/sheet/<int:record_id>", type="http", auth="user", methods=["GET"])
    def green_sheet(self, record_id, **kw):
        try:
            service = request.env["campus.green.card.ui"]
            record = service._record(record_id)
            if record.state != "approved" or not record.green_mentor_at or not record.green_hod_at:
                return self._private(request.not_found())
            return self._private(request.render("ideastone_erp.green_card_sheet", {"row": service._row(record), "company": record.company_id.name}))
        except (AccessError, UserError):
            return self._private(request.not_found())
