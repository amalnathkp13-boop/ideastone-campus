"""Synthetic communication records for the isolated faculty_communication_preview database."""

import os

assert env.cr.dbname == "faculty_communication_preview", "Preview database only"
user = env["res.users"].search([("login", "=", "faculty.home.preview")], limit=1)
assert user and env["op.faculty"].search([("user_id", "=", user.id)], limit=1), "Faculty preview account missing"
user.password = os.environ["FACULTY_COMMUNICATION_PREVIEW_PASSWORD"]
company = user.company_id
service = env["campus.faculty.communication"].with_user(user).with_company(company)
model = env["campus.faculty.communication.record"].sudo()

samples = {
    "surveys": [
        ("MyCompany Vendor Certification", "Published", {"owner": "Mitchell Admin", "date": "2026-10-20", "registered": 4, "success_ratio": 50, "average_score": 69.44, "average_duration": "00:33"}),
        ("Feedback Form", "Open", {"owner": "Mitchell Admin", "date": "2026-10-22", "registered": 4}),
        ("Quiz about our Company", "Published", {"owner": "Mitchell Admin", "date": "2026-10-24", "registered": 5, "success_ratio": 20, "average_score": 33.33, "average_duration": "01:00"}),
        ("Burger Quiz", "Draft", {"owner": "Marc Demo", "date": "2026-10-25"}),
        ("Food Preferences", "Draft", {"owner": "Marc Demo", "date": "2026-10-26"}),
    ],
    "events": [
        ("Business workshops", "Ended", {"owner": "Mitchell Admin", "date": "2026-10-10", "start_time": "23:30", "end_date": "2026-10-11", "end_time": "04:00", "venue": "Los Angeles Convention Center", "registered": 3, "attended": 2}),
        ("OpenWood Collection Online Reveal", "Ended", {"owner": "Marc Demo", "date": "2026-10-14", "start_time": "10:30", "end_date": "2026-10-16", "end_time": "20:30", "venue": "Online", "registered": 4}),
        ("Conference for Architects", "Ended", {"owner": "Mitchell Admin", "date": "2026-10-20", "start_time": "12:30", "end_date": "2026-10-20", "end_time": "22:00", "venue": "Los Angeles Convention Center", "registered": 5}),
        ("Design Fair Los Angeles", "Booked", {"owner": "Marc Demo", "date": "2026-10-25", "start_time": "13:30", "end_date": "2026-10-29", "end_time": "23:30", "venue": "Los Angeles Convention Center", "registered": 3}),
        ("An unpublished event", "New", {"owner": "Mitchell Admin", "date": "2026-11-14", "start_time": "15:00", "end_date": "2026-11-14", "end_time": "23:00", "venue": "Wembley Stadium"}),
        ("Great Reno Balloon Race", "Booked", {"owner": "Mitchell Admin", "date": "2027-01-24", "start_time": "01:45", "end_date": "2027-01-24", "end_time": "06:00", "venue": "Reno Airfield", "registered": 6}),
        ("Live Music Festival", "Announced", {"owner": "Marc Demo", "date": "2027-02-23", "start_time": "01:45", "end_date": "2027-02-25", "end_time": "06:00", "venue": "Wembley Stadium", "registered": 6}),
        ("Hockey Tournament", "New", {"owner": "Marc Demo", "date": "2027-10-20", "start_time": "14:30", "end_date": "2027-10-21", "end_time": "22:30", "venue": "Wembley Stadium", "registered": 2}),
    ],
    "alumni": [("Help", "Active", {"owner": "Faculty moderator", "date": "2026-10-28", "website": "Internal forum", "posts": 2, "views": 11})],
}
for kind, entries in samples.items():
    for name, status, metrics in entries:
        record = model.search([("company_id", "=", company.id), ("kind", "=", kind), ("name", "=", name)], limit=1)
        if not record:
            record = model.browse(service.create_record(kind, {"name": name, "owner": user.name, "date": "2026-10-29", "status": status,
                                                         "description": "Synthetic preview record matching the supplied layout."}))
        record.write(metrics)
env.cr.commit()
print("PREVIEW_ACTION", env.ref("ideastone_erp.action_dashboard").id, "PREVIEW_COMPANY", company.id,
      "RECORDS", {kind: len(service.get_data()["rows"][kind]) for kind in samples})
