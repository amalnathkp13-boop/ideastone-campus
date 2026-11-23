"""Run in Odoo shell against the isolated owner_placements_preview database only."""
import base64
import json
import os
from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path

from odoo.tests.common import new_test_user
from PyPDF2 import PdfFileWriter

from odoo import fields

if env.cr.dbname != "owner_placements_preview":
    raise RuntimeError("This fixture may only run in owner_placements_preview.")
password = os.environ["OWNER_PLACEMENTS_PREVIEW_PASSWORD"]
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True))
parameters = env["ir.config_parameter"].sudo()
source = next(path for path in (Path("/mnt/qa/owner-placements/reference_data.json"), Path("/mnt/qa/qa/owner-placements/reference_data.json")) if path.exists())
fixture = json.loads(source.read_text())
if parameters.get_param("owner_placements.preview_seeded"):
    print("Owner placements preview already seeded.")
else:
    company = env["res.company"].search([("name", "=", "Ideastone Demo Engineering College")], limit=1)
    company_values = {"name": "Ideastone Demo Engineering College", "campus_demo": True,
                      "currency_id": env.ref("base.INR").id, "campus_student_portal_enabled": True}
    if company:
        company.write(company_values)
    else:
        company = company.create(company_values)
    env = env(context=dict(env.context, allowed_company_ids=[company.id]))
    owner = new_test_user(env, login="owner.placements.preview", name="College Owner", password=password,
        groups="ideastone_erp.group_mvp_owner", company_id=company.id, company_ids=[(6, 0, [company.id])], tz="Asia/Kolkata")
    new_test_user(env, login="placements.readonly.preview", name="Placements read-only preview", password=password,
        groups="ideastone_erp.group_mvp_readonly", company_id=company.id, company_ids=[(6, 0, [company.id])], tz="Asia/Kolkata")
    departments, courses, subjects, batches, years = {}, {}, {}, {}, {}
    for info in fixture["departments"]:
        key = info["id"]
        department = env["op.department"].search([("code", "=", key), ("company_id", "=", company.id)], limit=1)
        department_values = {"name": info["name"], "code": key, "company_id": company.id}
        if department:
            department.write(department_values)
        else:
            department = department.create(department_values)
        departments[key] = department
        courses[key] = env["op.course"].create({"name": info["name"], "code": "OPP-" + key,
            "department_id": departments[key].id, "company_id": company.id, "campus_duration": 8})
        subjects[key] = env["op.subject"].create({"name": "Placement foundation · " + key, "code": "OPP-" + key,
            "department_id": departments[key].id, "company_id": company.id})
        courses[key].subject_ids = subjects[key]
    for year in (2027, 2026, 2025):
        first, last = date(year - 1, 7, 1), date(year, 6, 30)
        years[year] = env["op.academic.year"].create({"name": f"{year - 1}–{year}", "code": f"OPP{year}",
            "start_date": first, "end_date": last, "campus_current": year == 2027, "company_id": company.id})
        for key, course in courses.items():
            term = env["op.academic.term"].create({"name": f"Final year · {key} · {year}", "academic_year_id": years[year].id,
                "campus_course_id": course.id, "term_start_date": first, "term_end_date": last, "campus_sequence": 7, "company_id": company.id})
            batches[year, key] = env["op.batch"].create({"name": f"{key} · Class of {year}", "code": f"OPP{year}{key}",
                "course_id": course.id, "campus_year_id": years[year].id, "campus_term_id": term.id,
                "start_date": first, "end_date": last, "company_id": company.id})
    data = fixture["students"]
    student_records = env["op.student"].create([{"first_name": row["name"].rsplit(" ", 1)[0], "last_name": row["name"].rsplit(" ", 1)[-1],
        "name": row["name"], "gender": "o", "birth_date": "2005-01-01", "gr_no": row["id"], "company_id": company.id,
        "email": row["id"].lower() + "@example.test", "phone": "9000000000",
        "partner_id": env["res.partner"].create({"name": row["name"], "company_id": company.id}).id} for row in data])
    students = {row["id"]: student for row, student in zip(data, student_records, strict=True)}
    enrolment_records = env["op.student.course"].create([{"student_id": students[row["id"]].id,
        "course_id": courses[row["dept"]].id, "batch_id": batches[row["year"], row["dept"]].id,
        "academic_years_id": years[row["year"]].id, "academic_term_id": batches[row["year"], row["dept"]].campus_term_id.id,
        "subject_ids": [(6, 0, subjects[row["dept"]].ids)], "company_id": company.id,
        "campus_date_from": years[row["year"]].start_date, "campus_date_to": years[row["year"]].end_date,
        "state": "running" if row["year"] == 2027 else "finished", "campus_reason": "Synthetic graduating cohort for preview"} for row in data])
    enrolments = {row["id"]: enrolment for row, enrolment in zip(data, enrolment_records, strict=True)}
    pdf = PdfFileWriter()
    pdf.addBlankPage(width=595, height=842)
    output = BytesIO()
    pdf.write(output)
    resume = base64.b64encode(output.getvalue())
    profile_records = env["campus.placement.profile"].create([{"student_id": students[row["id"]].id,
        "placement_enrolment_id": enrolments[row["id"]].id, "graduation_year": row["year"], "cgpa_recorded": True, "cgpa": row["cgpa"],
        "consent": "willing" if row["willing"] else "declined", "non_willing_reason": row["reason"],
        "skills": "Problem solving, teamwork, technical fundamentals", "preferred_roles": "Graduate Engineer",
        "preferred_locations": "Chennai, Bengaluru", "experience": "Synthetic placement preparation project",
        "readiness_recorded": True, "quantitative": row["aptitude"], "reasoning": row["aptitude"], "verbal": row["communication"],
        "technical_recorded": True, "technical": row["coding"], "resume": resume if row["resume"] else False,
        "resume_filename": "sample-resume.pdf" if row["resume"] else False, "resume_uploaded": fields.Date.today() if row["resume"] else False,
        "resume_verified": row["resume"]} for row in data])
    profiles = {row["id"]: profile for row, profile in zip(data, profile_records, strict=True)}
    exam_type = env["op.exam.type"].create({"name": "Placement preview academics", "code": "OPP", "company_id": company.id})
    exams = {}
    for (year, key), batch in batches.items():
        day = date(year - 1, 9, 15)
        session = env["op.exam.session"].create({"name": f"Preview academic results {key} {year}", "exam_code": f"OPP{year}{key}",
            "course_id": courses[key].id, "batch_id": batch.id, "exam_type": exam_type.id, "start_date": day,
            "end_date": day, "company_id": company.id})
        exams[year, key] = env["op.exam"].create({"name": f"Published preview results · {key} {year}", "exam_code": f"OPP{year}{key}",
            "session_id": session.id, "subject_id": subjects[key].id, "total_marks": 100, "min_marks": 40,
            "start_time": datetime.combine(day, time(9)), "end_time": datetime.combine(day, time(10)), "state": "result_updated"})
    env["op.result.line"].create([{"exam_id": exams[row["year"], row["dept"]].id, "student_id": students[row["id"]].id,
        "marks": round(row["cgpa"] * 10), "campus_entered": True} for row in data])
    recruiters = {}
    for name in {row["company"] for row in data if row["placed"]} | {row["company"] for row in fixture["baseDrives"]}:
        recruiters[name] = env["res.partner"].create({"name": name, "is_company": True, "company_id": company.id})
    historic = {}
    for year in (2027, 2026, 2025):
        for name, recruiter in recruiters.items():
            drive = env["campus.placement.drive"].with_user(owner).create({"name": "Graduate role", "recruiter_id": recruiter.id,
                "company_id": company.id, "graduation_year": year, "minimum_cgpa": 6.5,
                "interview_on": datetime(year - 1, 10, 15, 4, 30), "location": "Campus Career Development Cell",
                "job_description": "Synthetic historical placement outcome", "course_ids": [(6, 0, [course.id for course in courses.values()])],
                "coordinator_name": "Career Development Cell", "portal_published": False})
            drive.action_submit()
            drive.action_approve()
            historic[year, name] = drive
    offer_records = env["campus.placement.candidate"].create([{"name": row["name"] + " · " + row["company"],
        "student_id": students[row["id"]].id, "profile_id": profiles[row["id"]].id, "portal_enrolment_id": enrolments[row["id"]].id,
        "drive_id": historic[row["year"], row["company"]].id, "company_id": company.id, "state": "selected",
        "offer_reference": "OPP-OFFER-" + row["id"], "offered_salary": row["salary"] * 100000,
        "offer_decision": "accepted" if row["accepted"] else "pending", "offer_accepted_on": date(row["year"] - 1, 10, 20) if row["accepted"] else False,
        "joined_on": date(row["year"], 7, 1) if row["joined"] else False,
        "portal_applied_on": date(row["year"] - 1, 10, 1)} for row in data if row["placed"]])
    for source in fixture["baseDrives"]:
        codes = source["dept"].split(",")
        drive = env["campus.placement.drive"].with_user(owner).create({"name": source["role"], "recruiter_id": recruiters[source["company"]].id,
            "company_id": company.id, "graduation_year": source["year"], "minimum_cgpa": source["cgpa"],
            "expected_ctc_lpa": source["salary"], "interview_on": source["date"] + " 04:30:00", "application_deadline": source["deadline"],
            "location": source["location"], "placement_mode": "virtual" if source["mode"] == "Virtual" else "campus",
            "coordinator_name": source["coordinator"], "job_description": source["role"], "portal_published": source["status"] == "Registration open",
            "recruitment_process": "Registration → aptitude assessment → technical interview → HR interview → offer decision",
            "course_ids": [(6, 0, [courses[code].id for code in codes])]})
        drive.action_submit()
        drive.action_approve()
    # One additional genuine offer demonstrates offer counts versus unique placed students.
    source = next(row for row in data if row["year"] == 2027 and row["placed"] and row["accepted"])
    second_company = next(name for name in recruiters if name != source["company"])
    env["campus.placement.candidate"].create({"name": "Additional sample offer", "company_id": company.id,
        "student_id": students[source["id"]].id, "profile_id": profiles[source["id"]].id,
        "portal_enrolment_id": enrolments[source["id"]].id, "drive_id": historic[2027, second_company].id,
        "state": "selected", "offer_reference": "OPP-SECOND-OFFER", "offered_salary": 350000})
    learner = students[next(row["id"] for row in data if row["year"] == 2027 and row["dept"] == "CSE" and row["eligible"] and not row["placed"])]
    student_user = new_test_user(env, login="student.placements.owner.preview", name=learner.name, password=password,
        groups="base.group_portal", partner_id=learner.partner_id.id, company_id=company.id, company_ids=[(6, 0, [company.id])], tz="Asia/Kolkata")
    learner.user_id = student_user
    env["campus.placement.milestone"].create({"name": "Offer issued", "candidate_id": offer_records[0].id,
        "detail": "Synthetic placement offer for the preview", "status": "done", "event_at": datetime(2026, 10, 20, 9)})
    parameters.set_param("owner_placements.preview_company_id", company.id)
    parameters.set_param("owner_placements.preview_seeded", True)
    snapshot = env["campus.owner.placements.ui"].with_user(owner).with_company(company).get_data()
    current = [row for row in snapshot["students"] if row["year"] == 2027]
    assert len(current) == 720
    assert sum(row["willing"] for row in current) == 616
    assert sum(row["eligible"] and row["willing"] for row in current) == 556
    assert sum(row["placed"] for row in current) == 414
    assert len(snapshot["drives"]) == 3
    env.cr.commit()
    print(json.dumps({"company_id": company.id, "owner_login": owner.login, "students": len(snapshot["students"]),
                      "offers": len(snapshot["offers"]), "upcoming_drives": len(snapshot["drives"])}))

# Fresh installs include a few unused baseline departments outside this reference.
preview_company = env["res.company"].browse(int(parameters.get_param("owner_placements.preview_company_id")))
assert preview_company.campus_demo
for index, info in enumerate(fixture["departments"], start=1):
    department = env["op.department"].search([("company_id", "=", preview_company.id), ("code", "=", info["id"])], limit=1)
    assert department
    department.write({"placement_sequence": index * 10,
                      "placement_coordinator": "R. Kumar" if info["id"] in {"CSE", "IT"} else "S. Priya"})
extras = env["op.department"].search([("company_id", "=", preview_company.id), ("active", "=", True),
                                     ("code", "not in", [row["id"] for row in fixture["departments"]])])
for department in extras:
    if (env["op.student.course"].search_count([("course_id.department_id", "=", department.id)])
            or env["op.faculty"].search_count([("main_department_id", "=", department.id)])):
        raise RuntimeError("Refusing to archive a baseline department that has students or faculty.")
extras.write({"active": False})
env.cr.commit()
print(json.dumps({"unused_preview_departments_archived": extras.mapped("code")}))
