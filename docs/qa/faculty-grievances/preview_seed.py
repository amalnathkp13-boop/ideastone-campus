"""Run with `odoo shell -d campus_faculty_grievances_preview` only."""
# ruff: noqa: F821 - Odoo shell injects `env`.

if env.cr.dbname != "campus_faculty_grievances_preview":
    raise RuntimeError("This seed only targets the isolated faculty grievances preview.")

faculty = env["res.users"].search([("login", "=", "faculty.od.preview")], limit=1)
if not faculty:
    raise RuntimeError("The copied preview database has no faculty.od.preview account.")

manager = env["res.users"].search([("login", "=", "admin")], limit=1)
if not manager or not manager.has_group("ideastone_erp.group_manager"):
    manager = env["res.users"].search([("groups_id", "in", env.ref("ideastone_erp.group_manager").id)], limit=1)
if not manager:
    raise RuntimeError("No campus manager is available for sample approvals.")

request_model = env["campus.service.request"].with_user(faculty).with_company(faculty.company_id)
if not request_model.search_count([("name", "=", "Projector connection issue in Seminar Hall"), ("kind", "=", "grievance")]):
    examples = [
        ("Projector connection issue in Seminar Hall", "it", "high", "2026-10-24", "approved",
         "IT Support has been assigned to check the projector connection and room equipment."),
        ("Correction required in September payslip", "payroll", "medium", "2026-10-21", "submitted", ""),
        ("Request to repair staff-room lighting", "facilities", "low", "2026-10-17", "done",
         "Maintenance work was completed and the lighting was restored."),
        ("Clarification on internal assessment schedule", "academic", "medium", "2026-10-14", "approved",
         "Academic administration is reviewing the timetable clarification."),
    ]
    for subject, category, priority, date, target, resolution in examples:
        record = request_model.create({"name": subject, "kind": "grievance", "date": date,
            "description": f"Faculty concern: {subject}.", "grievance_category": category,
            "grievance_priority": priority, "grievance_incident_date": date,
            "grievance_contact": "Faculty office extension 42"})
        record.action_submit()
        if resolution:
            record.with_user(manager).sudo().with_company(faculty.company_id).write({"resolution": resolution})
        if target in {"approved", "done"}:
            record.with_user(manager).sudo().with_company(faculty.company_id).action_approve()
        if target == "done":
            record.with_user(manager).sudo().with_company(faculty.company_id).action_done()
    env.cr.commit()

print("Faculty grievance preview records:", request_model.search_count([("kind", "=", "grievance")]))
