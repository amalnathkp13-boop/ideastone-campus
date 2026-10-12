"""Thin client for the OpenOlat REST API (https://<lms>/restapi).

Endpoints used (verified against OpenOlat source, org.olat.user.restapi.UserWebService and
org.olat.restapi.repository.course.CourseWebService):
  GET  /restapi/users?login="<login>"                       exact-match search
  PUT  /restapi/users                                       create user (UserVO JSON)
  GET  /restapi/repo/courses                                list courses
  PUT  /restapi/repo/courses/{courseKey}/participants/{identityKey}
"""

import logging

import requests
from odoo.exceptions import UserError
from requests.auth import HTTPBasicAuth

from odoo import _

_logger = logging.getLogger(__name__)


class LmsClient:
    def __init__(self, base_url, user, password, timeout=20):
        if not base_url or not user:
            raise UserError(_("LMS integration is not configured. Set the OpenOlat URL and API user in Settings → Ideastone Campus."))
        self.base = base_url.rstrip("/") + "/restapi"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(user, password or "")
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        self.timeout = timeout

    # ---- low level ---------------------------------------------------
    def _req(self, method, path, **kw):
        url = f"{self.base}{path}"
        try:
            r = self.session.request(method, url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise UserError(_("Could not reach the LMS at %s: %s", url, e)) from e
        if r.status_code >= 400:
            raise UserError(_("LMS returned %s for %s %s: %s", r.status_code, method, path, r.text[:300]))
        return r

    # ---- users -------------------------------------------------------
    def find_user(self, login):
        r = self._req("GET", "/users", params={"login": f'"{login}"'})
        data = r.json() if r.content else []
        for u in data if isinstance(data, list) else data.get("users", []):
            if u.get("login", "").lower() == login.lower():
                return u
        return None

    def create_user(self, login, first_name, last_name, email, password=None, external_id=None):
        payload = {
            "login": login,
            "firstName": first_name or login,
            "lastName": last_name or "",
            "email": email or f"{login}@campus.invalid",
        }
        if password:
            payload["password"] = password
        if external_id:
            payload["externalId"] = external_id
        return self._req("PUT", "/users", json=payload).json()

    def ensure_user(self, login, first_name, last_name, email, password=None, external_id=None):
        """Return (user_dict, created_bool)."""
        existing = self.find_user(login)
        if existing:
            return existing, False
        return self.create_user(login, first_name, last_name, email, password, external_id), True

    # ---- courses -----------------------------------------------------
    def list_courses(self):
        r = self._req("GET", "/repo/courses")
        data = r.json() if r.content else []
        return data if isinstance(data, list) else data.get("courses", [])

    def add_participant(self, course_key, identity_key):
        self._req("PUT", f"/repo/courses/{course_key}/participants/{identity_key}")
        return True
