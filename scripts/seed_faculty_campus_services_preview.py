"""Seed only the isolated faculty campus services preview database via Odoo shell."""

import os

assert env.cr.dbname == "faculty_campus_services_preview"  # noqa: F821
user = env["res.users"].sudo().search([("login", "=", "faculty.home.preview")], limit=1)  # noqa: F821
assert user
user.password = os.environ["FACULTY_SERVICES_PREVIEW_PASSWORD"]
ui = env["campus.faculty.services.ui"].with_user(user).with_company(user.company_id)  # noqa: F821

samples = [
    ("service", {"subject": "Projector display issue – Room 204", "category": "it", "priority": "high", "location": "Main Block · Room 204", "needed_by": "2026-10-30", "description": "Projector powers on but does not display the classroom computer."}),
    ("service", {"subject": "Wi-Fi access in ECE lab", "category": "it", "priority": "urgent", "location": "ECE Block · Lab 2", "needed_by": "2026-10-31", "description": "Lab devices cannot connect to the campus wireless network."}),
    ("maintenance", {"subject": "Electrical point repair", "category": "electrical", "priority": "high", "location": "ECE Block · Lab 2", "needed_by": "2026-10-30", "description": "One electrical socket is not working and needs inspection."}),
    ("maintenance", {"subject": "Door lock replacement", "category": "facilities", "priority": "normal", "location": "Main Block · Room 105", "needed_by": "2026-11-02", "description": "The classroom door lock is jammed."}),
]
for page, payload in samples:
    if not env["campus.service.request"].sudo().search_count([("requester_id", "=", user.id), ("name", "=", payload["subject"])], limit=1):  # noqa: F821
        print(ui.submit_request(page, payload))

manager = env.ref("base.user_admin")  # noqa: F821
for subject, team, complete in [("Projector display issue – Room 204", "IT Support", True),
                                ("Wi-Fi access in ECE lab", "IT Support", False),
                                ("Electrical point repair", "Facilities", False)]:
    record = env["campus.service.request"].with_user(manager).with_company(user.company_id).search([  # noqa: F821
        ("requester_id", "=", user.id), ("name", "=", subject),
    ], limit=1)
    if record and record.state == "submitted":
        record.write({"service_team": team})
        record.action_approve()
    if record and complete and record.state == "approved":
        record.write({"resolution": "Resolved in the isolated preview database."})
        record.action_done()

student = env["op.student"].sudo().search([("company_id", "=", user.company_id.id)], limit=1)  # noqa: F821
if student and not env["campus.service.request"].sudo().search_count([("requester_id", "=", user.id), ("name", "=", "Classroom conduct concern")], limit=1):  # noqa: F821
    print(ui.submit_request("complaint", {"subject": "Classroom conduct concern", "student_number": student.gr_no,
                                          "complaint_category": "Classroom conduct", "description": "Sample concern for the isolated preview. Faculty review requested."}))

route_model = env["campus.student.leave.routing"].sudo()  # noqa: F821
route = route_model.search([("student_id", "=", student.id), ("company_id", "=", user.company_id.id)], limit=1)
if student and not route:
    other = env["res.users"].sudo().search([("id", "!=", user.id), ("active", "=", True),  # noqa: F821
                                             ("company_ids", "in", user.company_id.id),
                                             ("groups_id", "in", env.ref("openeducat_core.group_op_faculty").id)], limit=1)  # noqa: F821
    if other:
        route = route_model.create({"name": "Preview student leave routing", "company_id": user.company_id.id,
                                    "student_id": student.id, "advisor_id": user.id, "hod_id": other.id})
if route and not env["campus.student.leave"].sudo().search_count([("routing_id", "=", route.id), ("name", "=", "Preview leave application")], limit=1):  # noqa: F821
    leave = env["campus.student.leave"].with_user(user).with_company(user.company_id).create({  # noqa: F821
        "name": "Preview leave application", "routing_id": route.id, "reason": "Sample family event for the isolated preview.",
        "date": "2026-10-30", "deadline": "2026-10-31", "kind": "mentoring",
    })
    leave.action_submit()

for page in ("service", "leave", "maintenance", "complaint"):
    print(page, ui.get_page_data(page)["rows"][:2])
env.cr.commit()  # noqa: F821
