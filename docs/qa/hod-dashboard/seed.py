"""Add overview fixtures to a disposable copy of question_papers_preview."""

import os
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError


def seed(env):
    assert env.cr.dbname == "hod_dashboard_reference", "Disposable dashboard database only"
    env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
    hod = env["res.users"].search([("login", "=", "exam.hod.preview")], limit=1)
    mentor = env["res.users"].search([("login", "=", "exam.faculty.preview")], limit=1)
    assert hod and mentor
    company, dept = hod.company_id, hod.dept_id
    env = env["res.users"].with_company(company).env
    today = fields.Date.context_today(hod.with_context(tz=hod.tz))
    env["ir.cron"].search([]).write({"active": False})
    env["ir.mail_server"].search([]).write({"active": False})
    env["auth.oauth.provider"].search([]).write({"enabled": False})
    env["ir.config_parameter"].set_param("web.base.url", "http://127.0.0.1:8076")
    env["ir.config_parameter"].set_param("web.base.url.freeze", "True")
    company.write({"name": "Ideastone Demo Engineering College", "campus_demo": True})
    hod.write({"password": os.environ["HOD_PREVIEW_PASSWORD"], "groups_id": [(4, env.ref("ideastone_erp.group_od_hod_approver").id)]})

    def ensure(model, domain, values):
        return env[model].search(domain, limit=1) or env[model].create(values)

    batches = env["op.batch"].search([("name", "=like", "Sample ECE Year %"),
        ("course_id.department_id", "=", dept.id)], order="name")
    assert len(batches) == 4 and len(batches.campus_year_id) == 1
    year = batches.campus_year_id
    env["op.academic.year"].search([("company_id", "=", company.id), ("campus_current", "=", True),
        ("id", "!=", year.id)]).write({"campus_current": False})
    year.campus_current = True
    teacher = env["op.faculty"].search([("user_id", "=", mentor.id)], limit=1)
    subject = env["op.subject"].search([("department_id", "=", dept.id)], limit=1)
    before = env["campus.hod.dashboard"].with_user(hod).get_overview()["students"]
    for number, batch in enumerate(batches, 1):
        term = ensure("op.academic.term", [("name", "=", f"HOD sample semester {number}"), ("academic_year_id", "=", year.id)], {
            "name": f"HOD sample semester {number}", "academic_year_id": year.id,
            "term_start_date": year.start_date, "term_end_date": year.end_date,
            "company_id": company.id, "campus_course_id": batch.course_id.id, "campus_sequence": number * 2 - 1,
        })
        batch.campus_term_id = term
        register = ensure("op.attendance.register", [("code", "=", f"HOD-QA-{number}")], {
            "code": f"HOD-QA-{number}", "name": f"HOD sample {number}", "course_id": batch.course_id.id, "batch_id": batch.id,
            "company_id": company.id,
        })
        for offset, status in [(0, "confirm"), (1, "confirm"), (3, "draft")]:
            start = datetime.combine(today + timedelta(days=offset), time(3 + number))
            period = ensure("op.session", [("batch_id", "=", batch.id), ("start_datetime", "=", start), ("faculty_id", "=", teacher.id)], {
                "batch_id": batch.id, "course_id": batch.course_id.id, "faculty_id": teacher.id, "company_id": company.id,
                "subject_id": subject.id, "start_datetime": start, "end_datetime": start + timedelta(minutes=45), "state": status,
            })
            if not offset and not env["op.attendance.sheet"].search_count([("session_id", "=", period.id)]):
                sheet = env["op.attendance.sheet"].create({"name": f"HOD sample attendance {number}", "register_id": register.id,
                    "session_id": period.id, "faculty_id": teacher.id, "attendance_date": today})
                sheet.action_campus_roster()
                if number in (2, 3) and sheet.attendance_line:
                    sheet.attendance_line[0].write({"present": False, "absent": True})
                sheet.attendance_done()
    batch = batches[0]
    student = ensure("op.student", [("gr_no", "=", "HOD-QA-FRESH")], {
        "name": "Sample ECE New enrolment", "first_name": "Sample ECE", "last_name": "New enrolment", "gender": "o",
        "gr_no": "HOD-QA-FRESH", "birth_date": "2008-03-14", "company_id": company.id,
    })
    ensure("op.student.course", [("student_id", "=", student.id), ("batch_id", "=", batch.id)], {
        "student_id": student.id, "course_id": batch.course_id.id, "batch_id": batch.id,
        "state": "running", "academic_years_id": year.id, "academic_term_id": batch.campus_term_id.id,
        "campus_date_from": today, "campus_date_to": year.end_date, "roll_number": student.gr_no,
    })
    student_user = ensure("res.users", [("login", "=", "hod.sample.student")], {
        "login": "hod.sample.student", "name": student.name, "partner_id": student.partner_id.id,
        "company_id": company.id, "company_ids": [(6, 0, company.ids)], "tz": "Asia/Kolkata",
        "groups_id": [(6, 0, [env.ref("base.group_portal").id])],
    })
    student.user_id = student_user
    route = ensure("campus.student.leave.routing", [("student_id", "=", student.id), ("company_id", "=", company.id)], {
        "name": "HOD sample student route", "student_id": student.id, "advisor_id": mentor.id, "hod_id": hod.id,
        "company_id": company.id,
    })
    portal = env["campus.student.portal"].with_user(student_user)
    od = env["campus.student.od"].search([("submission_key", "=", "d874651bba774ae3886f44554740b6a5")], limit=1)
    if not od:
        portal.act("od_submit", {"key": "d874651bba774ae3886f44554740b6a5", "name": "Sample inter-college symposium",
            "purpose": "Sample paper presentation", "venue": "College seminar hall",
            "od_date_from": str(today + timedelta(days=2)), "od_date_to": str(today + timedelta(days=2)),
            "od_from_session": "forenoon", "od_to_session": "afternoon"})
        od = env["campus.student.od"].search([("submission_key", "=", "d874651bba774ae3886f44554740b6a5")], limit=1)
        env["campus.staff.od.ui"].with_user(mentor).review_request(od.id, "forward")
    leave = env["campus.student.leave"].with_user(mentor)
    if not leave.search_count([("routing_id", "=", route.id), ("name", "=", "Sample student leave request")]):
        request = leave.create({"name": "Sample student leave request", "routing_id": route.id,
            "reason": "Synthetic preview request", "date": today, "deadline": today + timedelta(days=2)})
        request.action_submit()
        request.action_approve()

    coursework_subject = batch.course_id.subject_ids.filtered(lambda row: row.department_id == dept)[:1]
    if coursework_subject:
        assignment_type = ensure("grading.assignment.type", [("name", "=", "HOD sample coursework")],
            {"name": "HOD sample coursework", "assign_type": "sub"})
        assignment = ensure("op.assignment", [("name", "=", "Sample circuit analysis"), ("batch_id", "=", batch.id)], {
            "name": "Sample circuit analysis", "description": "Synthetic preview coursework", "course_id": batch.course_id.id,
            "subject_id": coursework_subject.id, "batch_id": batch.id, "faculty_id": teacher.id,
            "issued_date": fields.Datetime.now(), "submission_date": fields.Datetime.now() + timedelta(days=5),
            "assignment_type": assignment_type.id, "campus_learning": True, "state": "publish",
            "allocation_ids": [(6, 0, env["op.student.course"].search([("batch_id", "=", batch.id)]).student_id.ids)],
        })
        portal.act("assignment", {"assignment_id": assignment.id, "description": "Sample circuit analysis submitted."})
    employee = ensure("hr.employee", [("user_id", "=", mentor.id), ("company_id", "=", company.id)], {
        "name": mentor.name, "user_id": mentor.id, "company_id": company.id,
    })
    start = datetime.combine(today, time(3, 30))
    ensure("hr.attendance", [("employee_id", "=", employee.id), ("check_in", "=", start)], {
        "employee_id": employee.id, "check_in": start, "check_out": start + timedelta(hours=7),
    })
    task = env["campus.faculty.task"].with_user(mentor).sudo()
    if not task.search_count([("name", "=", "Sample appraisal preparation"), ("user_id", "=", mentor.id)]):
        task.create({"name": "Sample appraisal preparation", "kind": "other", "date": today, "deadline": today + timedelta(days=2)})
    for label, offset in [("Internal assessment – CAT II", 4), ("Department review meeting", 2), ("University exam registration close", 12)]:
        ensure("campus.calendar.event", [("name", "=", label), ("company_id", "=", company.id)], {
            "name": label, "company_id": company.id, "date_start": today + timedelta(days=offset), "status": "upcoming",
            "category": "academic", "audience": "All campus", "is_sample": True,
        })

    # Exercise the actual department scope, filters and role isolation.
    api = env["campus.hod.dashboard"].with_user(hod).with_context(tz=hod.tz)
    overview = api.get_overview()
    assert overview["students"] in (before, before + 1)
    assert any(row[1] == "HOD-QA-FRESH" for row in overview["student_rows"])
    assert len(overview["years"]) == 4 and overview["students"] >= 12 and overview["attendance"] is not None
    assert overview["attendance_today"] is not None
    assert api.get_overview({"section": str(batches[0].id)})["students"] < overview["students"]
    assert api.get_overview({"year": "3"})["years"][0]["year"] == "Year 3"
    for filters in ({"section": "999999"}, {"from": "2026-11-10", "to": "2026-11-01"}):
        try:
            api.get_overview(filters)
        except ValidationError:
            pass
        else:
            raise AssertionError("Invalid dashboard scope was accepted")
    try:
        api.with_user(mentor).get_overview()
    except AccessError:
        pass
    else:
        raise AssertionError("Faculty login could read HOD dashboard")
    home = next(module for module in env["campus.dashboard"].with_user(hod).get_overview()["faculty_modules"] if module["key"] == "home")
    assert home["items"] == [{"label": "Department overview", "page": "overview"}]
    env.cr.commit()
    print("HOD overview fixtures and checks passed", {key: overview[key] for key in ("students", "faculty", "attendance", "pending", "pass_rate")})


seed(env)  # noqa: F821
