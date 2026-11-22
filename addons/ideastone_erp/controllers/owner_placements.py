import hashlib
import json
import secrets

from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo import http, tools

from ..models.owner_placements_navigation import PLACEMENT_SCREENS


class OwnerPlacementsWorkspace(http.Controller):
    @http.route("/campus/owner/placements/workspace", type="http", auth="user", methods=["GET"])
    def workspace(self, company_id=None, screen="overview", year=None, department="All", **kw):
        headers = [("Cache-Control", "private, no-store"), ("X-Content-Type-Options", "nosniff"),
                   ("X-Frame-Options", "SAMEORIGIN")]
        try:
            company_id = int(company_id or request.env.company.id)
            if company_id not in request.env.user.company_ids.ids:
                raise AccessError("Select a college available to your account.")
            env = request.env(context=dict(request.env.context, allowed_company_ids=[company_id]))
            data = env["campus.owner.placements.ui"].get_data()
        except (AccessError, UserError, ValueError, TypeError) as exc:
            return request.make_response(str(exc), status=403, headers=headers + [("Content-Type", "text/plain; charset=utf-8")])
        bootstrap = {
            "data": data, "companyId": company_id,
            "preview": env.cr.dbname == "owner_placements_preview" and bool(env.company.campus_demo),
            "screen": screen if screen in dict(PLACEMENT_SCREENS) else "overview",
            "year": year, "department": department,
        }
        directory = "ideastone_erp/static/src/owner_placements/"
        with tools.file_open(directory + "workspace.html", "r") as source:
            html = source.read()
        for filename in ("workspace.css", "workspace.js"):
            asset = directory + filename
            with tools.file_open(asset, "rb") as source:
                version = hashlib.sha256(source.read()).hexdigest()[:16]
            html = html.replace('"/' + asset + '"', '"/' + asset + '?v=' + version + '"')
        nonce = secrets.token_urlsafe(24)
        serialized = json.dumps(bootstrap, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        html = html.replace("</head>", f'<script nonce="{nonce}">window.OWNER_PLACEMENTS_BOOTSTRAP={serialized};</script></head>')
        headers.extend([
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Security-Policy", f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; "
             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; "
             "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'"),
        ])
        return request.make_response(html, headers=headers)
