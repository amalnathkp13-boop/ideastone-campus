import json

from odoo import http
from odoo.addons.web.controllers.webmanifest import WebManifest


class VcetWebManifest(WebManifest):
    @http.route()
    def webmanifest(self):
        response = super().webmanifest()
        manifest = json.loads(response.get_data(as_text=True))
        manifest["name"] = "VCET Campus ERP"
        manifest["icons"] = [
            {"src": f"/ideastone_campus/static/src/img/icons/android-chrome-{size}.png", "sizes": size, "type": "image/png"}
            for size in ("192x192", "512x512")
        ] + [{
            "src": "/ideastone_campus/static/src/img/icons/android-chrome-maskable-512x512.png",
            "sizes": "512x512", "type": "image/png", "purpose": "maskable",
        }]
        response.set_data(json.dumps(manifest))
        return response

    def _icon_path(self):
        return "ideastone_campus/static/src/img/icons/android-chrome-192x192.png"
