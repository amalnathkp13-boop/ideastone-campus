"""Authenticated integration smoke test; use only a disposable QA database.

Usage: set ERP_QA_PASSWORD then run with --url and --database. The script creates
documented test fixtures, checks persistence, self-service isolation and assets.
"""

import argparse
import base64
import os
import re
import time
from urllib.parse import urljoin

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:18069")
    parser.add_argument("--database", default="erp_qa")
    parser.add_argument("--login", default="admin")
    args = parser.parse_args()
    if not any(token in args.database.lower() for token in ("qa", "ci", "test")):
        raise ValueError("Use a disposable QA database")
    password = os.environ["ERP_QA_PASSWORD"]
    admin = requests.Session()

    def authenticate(session, login, password):
        response = session.post(
            args.url + "/web/session/authenticate",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "params": {"db": args.database, "login": login, "password": password},
                "id": 1,
            },
            timeout=60,
        )
        data = response.json()
        assert data.get("result", {}).get("uid"), data.get("error", {}).get("message")
        return data["result"]["uid"]

    authenticate(admin, args.login, password)

    def rpc(model, method, argv, kwargs=None, session=admin):
        response = session.post(
            args.url + "/web/dataset/call_kw",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {"model": model, "method": method, "args": argv, "kwargs": kwargs or {}},
            },
            timeout=120,
        )
        body = response.json()
        assert "error" not in body, body.get("error", {}).get("data", {}).get("message")
        return body["result"]

    for route in ("/web", "/my/campus", "/my/campus/library"):
        response = admin.get(args.url + route, timeout=90)
        assert response.status_code == 200, (route, response.status_code)
        assert "Traceback" not in response.text
    html = admin.get(args.url + "/web", timeout=60).text
    assets = set(re.findall(r'(?:src|href)="([^"]*/web/assets/[^"]+)"', html))
    assert assets, "No backend assets found"
    for asset in assets:
        response = admin.get(urljoin(args.url, asset), timeout=120)
        assert response.status_code == 200, asset
        assert "Could not get content" not in response.text and "Error: Undefined" not in response.text, asset
    print("Backend, portal, catalogue and compiled assets: passed")

    suffix = str(int(time.time()))
    portal_group = rpc(
        "ir.model.data",
        "search_read",
        [[("module", "=", "base"), ("name", "=", "group_portal")]],
        {"fields": ["res_id"]},
    )[0]["res_id"]
    fixture_login = "http_qa_" + suffix
    fixture_password = "QA-only-" + suffix
    user = rpc(
        "res.users",
        "create",
        [
            {
                "name": "HTTP QA Student",
                "login": fixture_login,
                "password": fixture_password,
                "groups_id": [(6, 0, [portal_group])],
            }
        ],
        {"context": {"no_reset_password": True, "mail_create_nosubscribe": True}},
    )
    partner = rpc("res.users", "read", [[user], ["partner_id"]])[0]["partner_id"][0]
    student = rpc(
        "op.student",
        "create",
        [{"first_name": "HTTP QA", "last_name": "Student", "gender": "o", "partner_id": partner, "user_id": user}],
    )
    other_partner = rpc("res.partner", "create", [{"name": "HTTP QA Private Student " + suffix}])
    other_student = rpc(
        "op.student",
        "create",
        [{"first_name": "Private QA", "last_name": "Student", "gender": "o", "partner_id": other_partner}],
    )
    session = requests.Session()
    authenticate(session, fixture_login, fixture_password)
    response = session.get(args.url + "/my/campus", timeout=60)
    assert response.status_code == 200, response.text[:100]
    assert "HTTP QA" in response.text
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)
    response = session.post(
        args.url + "/my/campus/request",
        data={
            "csrf_token": csrf,
            "student": student,
            "kind": "certificate",
            "title": "HTTP QA certificate " + suffix,
            "description": "Disposable integration fixture",
        },
        timeout=60,
    )
    assert response.status_code == 200 and "Your submission was saved" in response.text
    saved = rpc(
        "campus.service.request",
        "search_read",
        [[("name", "=", "HTTP QA certificate " + suffix)]],
        {"fields": ["student_id", "requester_id", "state"]},
    )
    assert (
        len(saved) == 1
        and saved[0]["state"] == "submitted"
        and saved[0]["student_id"][0] == student
        and saved[0]["requester_id"][0] == user
    )
    response = session.post(
        args.url + "/my/campus/request",
        data={
            "csrf_token": csrf,
            "student": other_student,
            "kind": "grievance",
            "title": "FORGED QA " + suffix,
            "description": "Unauthorized student",
        },
        timeout=60,
    )
    assert "Your submission was saved" not in response.text
    assert not rpc("campus.service.request", "search_count", [[("name", "=", "FORGED QA " + suffix)]])
    response = session.post(
        args.url + "/my/campus/feedback",
        data={"csrf_token": csrf, "student": student, "period": suffix, "score": 4, "comments": "HTTP fixture"},
        timeout=60,
    )
    assert "Your submission was saved" in response.text, response.status_code
    response = session.post(
        args.url + "/my/campus/feedback",
        data={"csrf_token": csrf, "student": student, "period": suffix, "score": 4},
        timeout=60,
    )
    assert "already been submitted" in response.text
    private = session.get(args.url + "/my/campus?student=" + str(other_student), timeout=60)
    assert "Your account has no linked student" in private.text
    resource = rpc(
        "campus.digital.resource",
        "create",
        [
            {
                "name": "HTTP QA resource " + suffix,
                "filename": "qa.txt",
                "document": base64.b64encode(b"QA download fixture").decode(),
            }
        ],
    )
    rpc("campus.digital.resource", "action_submit", [[resource]])
    rpc("campus.digital.resource", "action_approve", [[resource]])
    download = session.get(args.url + "/my/campus/resource/" + str(resource), timeout=60)
    assert download.status_code == 200 and download.content == b"QA download fixture"
    unauthenticated = requests.get(args.url + "/my/campus/resource/" + str(resource), allow_redirects=False, timeout=60)
    assert unauthenticated.status_code in (302, 303)
    print(
        "Student identity isolation, CSRF forms, saved requests, feedback deduplication and authenticated downloads: passed"
    )


if __name__ == "__main__":
    main()
