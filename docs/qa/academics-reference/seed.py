"""Synthetic localhost data only. Run in an Odoo shell on the named preview DB."""
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

assert env.cr.dbname == "academics_reference_preview", "Preview database only"
assert not env["res.users"].search_count([("login", "=", "academics.admin.preview")]), "Preview already seeded"
password = os.environ["ACADEMICS_PREVIEW_PASSWORD"]
sample = json.loads(Path("/tmp/academics-sample-records.json").read_text())
company = env.company
company.write({"name": "VCET Academic Reference Preview", "campus_demo": True})
owner = env["res.users"].create({"name": "Academic Preview Admin", "login": "academics.admin.preview", "password": password,
    "company_id": company.id, "company_ids": [(6, 0, [company.id])],
    "groups_id": [(6, 0, [env.ref("ideastone_erp.group_mvp_owner").id, env.ref("ideastone_erp.group_manager").id])], "tz": "Asia/Kolkata"})
ui = env["campus.academics.ui"].with_user(owner)


def save(view, model, values, domain):
    existing = env[model].search(domain + [("company_id", "=", company.id)], limit=1)
    return env[model].browse(ui.save_record(view, values, existing.id or False))


years = {}
for code, name, start, end in [("2020-2021", "2020–21", "2020-02-01", "2021-01-31"),
        ("2021-2022", "2021–22", "2021-11-20", "2022-10-20"),
        ("2022-2023", "2022–23", "2022-11-20", "2023-10-20"),
        ("2026-27", "2026–27", "2026-07-01", "2027-06-30")]:
    years[code] = save("years", "op.academic.year", {"name": name, "code": code,
        "start_date": start, "end_date": end, "campus_current": code == "2026-27"}, ["|", ("code", "=", code), ("name", "=", code)])
departments = {}
for row in sample["departments"]:
    departments[row["data-name"]] = save("departments", "op.department", {
        "name": row["data-name"], "code": row["data-code"], "campus_academic_area": row["data-area"], "active": True}, [("code", "=", row["data-code"])])
programmes = {}
for row in sample["programmes"]:
    programmes[row["data-name"]] = save("programmes", "op.course", {"name": row["data-name"],
        "code": row["data-code"], "department_id": departments[row["data-department"]].id,
        "campus_level": row["data-level"], "campus_duration": int(row["data-duration"]) * 2}, [("code", "=", row["data-code"])])
terms = []
for index, row in enumerate(sample["semesters"]):
    year = years[row["data-year"]]
    start = max(year.start_date, date(2027, 1, 1)) if index == 11 else year.start_date
    end = min(year.end_date, date(2026, 12, 31)) if index == 10 else year.end_date
    term = env["op.academic.term"].browse(ui.save_record("semesters", {"name": row["data-name"],
        "academic_year_id": year.id, "campus_sequence": index % 4 + 1,
        "term_start_date": str(start), "term_end_date": str(end)}))
    if row["data-type"] == "quarter":
        term.parent_term = next(t for t in terms if t.academic_year_id == year and not t.parent_term)
    terms.append(term)
current_term = terms[-2]
sections = []
for index, row in enumerate(sample["sections"]):
    programme_name = row["data-course"].split(" · ")[-1]
    if programme_name not in programmes:
        programmes[programme_name] = env["op.course"].browse(ui.save_record("programmes", {"name": programme_name,
            "code": "SAMPLE-" + str(index), "department_id": departments["Department of Science"].id,
            "campus_level": "undergraduate", "campus_duration": 8}))
    course = programmes[programme_name]
    vals = {"name": row["data-name"], "code": row["data-code"], "course_id": course.id,
        "start_date": "2026-07-01", "end_date": "2030-06-30"}
    if row["data-year"] != "not-set":
        vals.update(campus_year_id=years["2026-27"].id, campus_term_id=current_term.id)
    sections.append(save("sections", "op.batch", vals, [("code", "=", row["data-code"])]))
subjects = []
for row in sample["subjects"]:
    subjects.append(env["op.subject"].browse(ui.save_record("curriculum", {"name": row["data-name"],
        "code": row["data-code"], "department_id": departments["Department of Accounts"].id, "campus_credits": 0})))
course = programmes["B.E. Computer Science and Engineering"]
subject = save("curriculum", "op.subject", {"name": "Data Structures and Algorithms", "code": "CS3301",
    "department_id": course.department_id.id, "campus_term_id": current_term.id, "campus_credits": 4}, [("code", "=", "CS3301")])
course.subject_ids = subject
cohort = next(s for s in sections if s.course_id == course)
faculty = env["op.faculty"].create({"first_name": "Sample", "last_name": "Academic Coordinator", "gender": "male",
    "birth_date": "1988-01-01", "main_department_id": course.department_id.id,
    "partner_id": env["res.partner"].create({"name": "Sample Academic Coordinator", "company_id": company.id}).id})
for index in range(24):
    student = env["op.student"].create({"first_name": "Sample", "last_name": "Student %02d" % (index + 1),
        "gender": "m" if index % 2 else "f", "birth_date": "2008-01-01", "gr_no": "ACADEMIC-%03d" % index,
        "company_id": company.id, "partner_id": env["res.partner"].create({"name": "Sample Student %02d" % (index + 1), "company_id": company.id}).id})
    env["op.student.course"].create({"student_id": student.id, "course_id": course.id, "batch_id": cohort.id,
        "academic_years_id": years["2026-27"].id, "academic_term_id": current_term.id, "state": "running", "campus_date_from": "2026-07-01"})
product = env["product.product"].create({"name": "Sample academic intake", "detailed_type": "service"})
for row in sample["departments"]:
    dept = departments[row["data-name"]]
    dept_course = next((p for p in programmes.values() if p.department_id == dept), None)
    if dept_course:
        env["op.admission.register"].create({"name": "Sample " + dept.code + " intake", "academic_years_id": years["2026-27"].id,
            "course_id": dept_course.id, "product_id": product.id, "start_date": "2026-07-01", "end_date": "2027-06-30", "max_count": int(row["data-capacity"])})
for index in range(10):
    when = date(2026, 7, 8) + timedelta(days=index * 8)
    env["campus.teaching.plan"].create({"name": "Sample lesson %02d" % index, "faculty_id": faculty.id,
        "subject_id": subject.id, "batch_id": cohort.id, "term_id": current_term.id, "planned_date": when,
        "unit": str(index + 1), "topic": "Sample curriculum delivery", "planned_hours": 10,
        "execution_date": when if index < 9 else False, "actual_hours": 10 if index < 8 else 6 if index == 8 else 0,
        "notes": "Synthetic teaching execution" if index < 9 else False})
    env["op.session"].create({"course_id": course.id, "batch_id": cohort.id, "subject_id": subject.id,
        "faculty_id": faculty.id, "start_datetime": datetime.combine(when, time(4, 0)),
        "end_datetime": datetime.combine(when, time(5, 0)), "state": "done" if index < 8 else "confirm"})
# A future semester milestone exercises the calendar without inventing chart data.
ui.save_record("semesters", {"name": "Curriculum review period", "academic_year_id": years["2026-27"].id,
    "campus_course_id": course.id, "campus_sequence": 2, "term_start_date": "2026-11-04", "term_end_date": "2026-11-20"})
env.cr.commit()
print("Seeded synthetic academic records:", {key: len(value) for key, value in ui.get_workspace()["rows"].items()})
print("Academic overview action:", env.ref("ideastone_erp.action_academics_overview").id)
