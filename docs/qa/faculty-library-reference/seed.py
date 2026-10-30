"""Load the supplied library examples into an isolated local preview college."""
import base64
import json
import os
from datetime import timedelta
from pathlib import Path

from odoo import fields

assert env.cr.dbname in {"campus", "faculty_library_reference_preview"}, "Use the named local preview database only"
assert env["ir.config_parameter"].sudo().get_param("web.base.url", "").startswith("http://localhost"), "Localhost preview only"
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))


def record(model, key, values):
    existing = env.ref("faculty_library_preview." + key, raise_if_not_found=False)
    if existing:
        return existing
    result = env[model].create(values)
    env["ir.model.data"].create({"module": "faculty_library_preview", "name": key, "model": model, "res_id": result.id, "noupdate": True})
    return result


company = record("res.company", "college", {"name": "VCET Question Paper Preview College", "campus_demo": True,
    "currency_id": env.ref("base.INR").id, "country_id": env.ref("base.in").id})
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
department = record("op.department", "department", {"name": "Electronics & Communication (ECE)", "code": "FL-ECE", "company_id": company.id})
existing = env.ref("faculty_library_preview.user", raise_if_not_found=False)
user = existing or record("res.users", "user", {"name": "Andre Santos", "login": "faculty.library.preview",
    "password": os.environ["FACULTY_LIBRARY_PREVIEW_PASSWORD"], "email": "andre.santos@vcet.example", "tz": "Asia/Kolkata",
    "company_id": company.id, "company_ids": [(6, 0, [company.id])],
    "groups_id": [(6, 0, [env.ref("openeducat_core.group_op_faculty").id, env.ref("openeducat_attendance.group_op_attendance_user").id,
                         env.ref("openeducat_exam.group_op_exam_user").id])]})
partner = record("res.partner", "partner", {"name": "Andre Santos", "user_id": user.id, "company_id": company.id, "email": "andre.santos@vcet.example"})
faculty = record("op.faculty", "faculty", {"first_name": "Andre", "last_name": "Santos", "gender": "male", "birth_date": "1988-01-01",
    "partner_id": partner.id, "main_department_id": department.id, "company_id": company.id, "campus_staff_code": "VCET-F-042"})
policy = record("op.library.card.type", "policy", {"name": "Faculty standard borrowing", "allow_media": 5, "duration": 14, "penalty_amt_per_day": 1})
card = record("op.library.card", "card", {"type": "faculty", "faculty_id": faculty.id, "partner_id": partner.id, "library_card_type_id": policy.id})
collection = record("op.media.type", "collection", {"name": "Main Library", "code": "FAC-LIB"})
books = json.loads(Path("/tmp/faculty-library-books.json").read_text())
units = {}
for index, book in enumerate(books):
    author = record("op.author", "author_%s" % index, {"name": book["author"]})
    publisher = record("op.publisher", "publisher_%s" % index, {"name": book["publisher"]})
    media = record("op.media", "media_%s" % index, {"name": book["title"], "internal_code": "FAC-PREVIEW-" + book["code"],
        "author_ids": [(6, 0, author.ids)], "publisher_ids": [(6, 0, publisher.ids)], "edition": book["edition"],
        "media_type_id": collection.id, "campus_publication_year": int(book["year"]), "campus_department": book["dept"], "campus_call_number": book["call"]})
    units[book["code"]] = record("op.media.unit", "unit_%s" % index, {"name": book["title"] + " · " + book["code"], "media_id": media.id,
        "campus_company_id": company.id, "campus_accession_number": book["code"], "campus_location": book["location"], "campus_rack": book["rack"]})
today = fields.Date.context_today(env["campus.faculty.library"].with_user(user).with_context(tz=user.tz))
for index, (code, issued, due, returned) in enumerate([
    ("B00456", today - timedelta(days=13), today + timedelta(days=1), False),
    ("B01234", today - timedelta(days=6), today + timedelta(days=8), False),
    ("B01890", today - timedelta(days=56), today - timedelta(days=42), today - timedelta(days=43)),
]):
    unit = units[code]
    loan = record("op.media.movement", "loan_%s" % index, {"media_id": unit.media_id.id, "media_unit_id": unit.id,
        "type": "faculty", "faculty_id": faculty.id, "library_card_id": card.id, "partner_id": partner.id,
        "user_id": user.id, "issued_date": issued, "return_date": due, "company_id": company.id})
    loan.write({"issued_date": issued, "return_date": due, "actual_return_date": returned or False})
    if loan.state == "available":
        loan.issue_media()
        if returned:
            loan.return_media(returned)
other_partner = record("res.partner", "other_partner", {"name": "Sample other library member", "company_id": company.id})
other_faculty = record("op.faculty", "other_faculty", {"first_name": "Sample", "last_name": "Library Member", "gender": "male",
    "birth_date": "1990-01-01", "partner_id": other_partner.id, "company_id": company.id})
other_card = record("op.library.card", "other_card", {"type": "faculty", "faculty_id": other_faculty.id,
    "partner_id": other_partner.id, "library_card_type_id": policy.id})
unit = units["B01987"]
other_loan = record("op.media.movement", "other_loan", {"media_id": unit.media_id.id, "media_unit_id": unit.id,
    "type": "faculty", "faculty_id": other_faculty.id, "library_card_id": other_card.id, "partner_id": other_partner.id,
    "issued_date": today - timedelta(days=2), "return_date": today + timedelta(days=12), "company_id": company.id})
if other_loan.state == "available":
    other_loan.issue_media()
for index, (title, kind) in enumerate([("Faculty development handbook", "notes"), ("Research and journal guidance", "journal"), ("Digital learning reference", "book")]):
    text = title + "\n\nIllustrative college-approved learning material for this local preview.\n"
    resource = record("campus.digital.resource", "resource_%s" % index, {"name": title, "resource_type": kind,
        "author": "Faculty Development Cell", "filename": "faculty-learning-%s.txt" % index,
        "document": base64.b64encode(text.encode()), "description": "Sample faculty development and research support material.", "company_id": company.id})
    if resource.state == "draft":
        # Import preapproved synthetic material, never approve a real pending request.
        resource._set_system_values({"state": "approved"})
env.cr.commit()
snapshot = env["campus.faculty.library"].with_user(user).get_workspace()
Path("/tmp/faculty-library-preview.json").write_text(json.dumps({"login": user.login, "company_id": company.id,
    "counts": snapshot["counts"], "staff": snapshot["staff"]}, indent=2))
print("Faculty Library preview seeded: %s catalogue records; %s own loans; %s approved resources." %
      (len(snapshot["books"]), len(snapshot["loans"]), len(snapshot["resources"])))
