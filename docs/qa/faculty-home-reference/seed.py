"""Synthetic faculty Home preview; execute through Odoo shell on this DB only."""
import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path

import pytz

from odoo import fields

assert env.cr.dbname == "faculty_home_reference_preview", "Preview database only"
assert not env["res.users"].search_count([("login", "=", "faculty.home.preview")]), "Preview already seeded"
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
company = env.company
company.write({"name": "VCET Faculty Home Preview", "campus_demo": True})
teacher = env["res.users"].create({"name": "Andre Santos", "login": "faculty.home.preview",
    "password": os.environ["FACULTY_HOME_PREVIEW_PASSWORD"], "tz": "Asia/Kolkata", "company_id": company.id,
    "company_ids": [(6, 0, [company.id])], "groups_id": [(6, 0, [env.ref(key).id for key in [
        "openeducat_core.group_op_faculty", "openeducat_attendance.group_op_attendance_user", "openeducat_exam.group_op_exam_user"]])]})
partner = env["res.partner"].create({"name": "Andre Santos", "user_id": teacher.id, "company_id": company.id})
faculty = env["op.faculty"].create({"first_name": "Andre", "last_name": "Santos", "gender": "male",
    "birth_date": "1988-01-01", "partner_id": partner.id, "company_id": company.id})
today = fields.Date.context_today(env["campus.faculty.home"].with_user(teacher))
year = env["op.academic.year"].search([("company_id", "=", company.id), ("campus_current", "=", True)], limit=1)
year = year or env["op.academic.year"].search([("company_id", "=", company.id), ("start_date", "<=", today), ("end_date", ">=", today)], order="start_date desc", limit=1)
assert year and year.start_date <= today <= year.end_date, "Current preview academic year must include today"
year.campus_current = True
reference = json.loads(Path("/tmp/faculty-home-students.json").read_text())
zone = pytz.timezone("Asia/Kolkata")


def utc(day, hour, minute=0):
    return zone.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.utc).replace(tzinfo=None)


subjects = env["op.subject"]
for index, name in enumerate(["Digital Electronics", "Communication Systems", "Digital Electronics Lab"]):
    subjects |= env["op.subject"].create({"name": name, "code": "HOME-SUB-%s" % index, "company_id": company.id})
faculty.faculty_subject_ids = subjects
batches, cohorts = [], []
for code, department_data in reference.items():
    department = env["op.department"].search([("company_id", "=", company.id), ("code", "=", code)], limit=1)
    if not department:
        department = env["op.department"].create({"name": department_data["name"], "code": code, "company_id": company.id})
    else:
        department.name = department_data["name"]
    if code == "ECE":
        faculty.main_department_id = department
        subjects.department_id = department
    course = env["op.course"].create({"name": "B.E. " + code, "code": "HOME-" + code,
        "department_id": department.id, "company_id": company.id, "subject_ids": [(6, 0, subjects.ids)]})
    for level in department_data["years"]:
        study = int(level["label"].split()[-1])
        term = env["op.academic.term"].create({"name": "Semester %s" % (study * 2 - 1), "academic_year_id": year.id,
            "campus_course_id": course.id, "campus_sequence": study * 2 - 1,
            "term_start_date": year.start_date, "term_end_date": min(year.end_date, today + timedelta(days=60))})
        for section in level["sections"]:
            letter = section["label"].split()[-1]
            batch = env["op.batch"].create({"name": "%s Sem %s-%s" % (code, study * 2 - 1, letter),
                "code": "HOME-%s-%s-%s" % (code, study, letter), "course_id": course.id, "company_id": company.id,
                "campus_year_id": year.id, "campus_term_id": term.id, "start_date": year.start_date, "end_date": year.end_date})
            batches.append(batch)
            cohorts.append(section["students"])
registers = {batch.id: env["op.attendance.register"].create({"name": batch.name, "code": batch.code,
    "course_id": batch.course_id.id, "batch_id": batch.id, "company_id": company.id}) for batch in batches}
rooms = env["op.classroom"]
for index, name in enumerate(["R003", "R004", "Lab 2"]):
    rooms |= env["op.classroom"].search([("name", "=", name), ("company_id", "=", company.id)], limit=1) or env["op.classroom"].create(
        {"name": name, "code": "HOME-R%s" % index, "capacity": 60, "company_id": company.id})
# Three teaching cohorts have ten students each for exact 100-session attendance samples.
targets = [10, 10, 14, 10, 14, 14, 14, 14, 13, 13]
assert sum(targets) == 126
for batch_index, batch in enumerate(batches):
    records = list(cohorts[batch_index])
    while len(records) < targets[batch_index]:
        number = len(records) + 1
        records.append(["Sample Learner %s-%02d" % (batch_index + 1, number), "HOME%02d%03d" % (batch_index, number),
            batch.course_id.name, "sample.%s.%s@example.test" % (batch_index, number)])
    for name, register, programme, email in records:
        words = name.split(" ", 1)
        student_partner = env["res.partner"].create({"name": name, "email": email, "company_id": company.id})
        student = env["op.student"].create({"first_name": words[0], "last_name": words[-1], "gender": "o",
            "birth_date": "2006-01-01", "gr_no": register, "partner_id": student_partner.id, "company_id": company.id})
        env["op.student.course"].create({"student_id": student.id, "course_id": batch.course_id.id, "batch_id": batch.id,
            "academic_years_id": year.id, "academic_term_id": batch.campus_term_id.id, "campus_date_from": year.start_date, "state": "running"})


def session(batch, subject, day, hour, minute=0, done=False, room=None):
    start = utc(day, hour, minute)
    return env["op.session"].create({"faculty_id": faculty.id, "company_id": company.id, "course_id": batch.course_id.id,
        "batch_id": batch.id, "subject_id": subject.id, "start_datetime": start, "end_datetime": start + timedelta(hours=1),
        "state": "done" if done else "confirm", "classroom_id": (room or rooms[:1]).id})


for subject_index, (batch_index, absences) in enumerate([(0, 18), (3, 24), (1, 9)]):
    batch = batches[batch_index]
    remaining_absent = absences
    for day_index in range(10):
        day = today - timedelta(days=12 - day_index)
        item = session(batch, subjects[subject_index], day, 9 + subject_index, done=True, room=rooms[subject_index])
        sheet = env["op.attendance.sheet"].with_user(teacher).create({"register_id": registers[batch.id].id,
            "session_id": item.id, "faculty_id": faculty.id, "attendance_date": day})
        sheet.action_campus_roster()
        for line in sheet.attendance_line:
            if remaining_absent:
                line.present = False
                remaining_absent -= 1
        sheet.attendance_done()
for index, batch in enumerate(batches):
    # Each directory cohort has a confirmed allocation, even when not taught today.
    session(batch, subjects[index % 3], today + timedelta(days=index + 1), 9)
session(batches[0], subjects[0], today, 9, done=True)
session(batches[3], subjects[1], today, 10, done=True, room=rooms[1])
session(batches[1], subjects[2], today, 16, 15, room=rooms[2])
session(batches[0], subjects[0], today, 17, 30)
exam_type = env["op.exam.type"].create({"name": "Home sample internal", "code": "HOME-CAT"})
grades = env["op.grade.configuration"].create([{"min_per": 0, "max_per": 39, "result": "F"}, {"min_per": 40, "max_per": 100, "result": "P"}])
for index, average in enumerate([78, 72, 86]):
    batch = batches[[0, 3, 1][index]]
    exam_session = env["op.exam.session"].create({"name": "Sample CAT 1", "exam_code": "HOME-CAT-%s" % index,
        "exam_type": exam_type.id, "course_id": batch.course_id.id, "batch_id": batch.id, "campus_year_id": year.id,
        "start_date": today - timedelta(days=3), "end_date": today - timedelta(days=3)})
    exam = env["op.exam"].create({"name": subjects[index].name + " CAT 1", "exam_code": "HOME-EXAM-%s" % index,
        "session_id": exam_session.id, "subject_id": subjects[index].id, "responsible_id": [(6, 0, faculty.ids)],
        "start_time": utc(today - timedelta(days=3), 14 + index), "end_time": utc(today - timedelta(days=3), 15 + index),
        "total_marks": 100, "min_marks": 40, "campus_grade_ids": [(6, 0, grades.ids)]})
    exam.action_campus_roster()
    exam.campus_result_ids.write({"marks": average, "campus_entered": True})
    exam.action_campus_submit()
    exam.action_campus_lock()
    exam.action_campus_publish()
for index, title in enumerate(["Submit class attendance", "Upload examination question sets", "Finish assessment marks", "Prepare next lesson", "Review student support"]):
    env["campus.faculty.task"].with_user(teacher).create({"name": title, "deadline": today if index < 2 else today + timedelta(days=index),
        "kind": "exam" if index in {1, 2} else "teaching", "priority": "1" if index < 2 else "0"})
for index, subject in enumerate(subjects[:2]):
    env["campus.question.paper"].with_user(teacher).save_submission({"subject_id": subject.id, "department_id": subject.department_id.id,
        "exam_type": "Internal Assessment 2", "exam_date": str(today + timedelta(days=2 + index)), "paper_code": "HOME-QP-%s" % index,
        "study_year": "2" if index == 0 else "3", "semester": "III" if index == 0 else "V", "duration": "3 hours", "notes": "Synthetic faculty Home preview"})
notice = env["campus.circular"].create({"name": "Department timetable revised for Room R004", "reference": "HOME-NOTICE",
    "campus_managed": True, "audience": "faculty", "date_from": today, "body": "<p>Sample timetable update for faculty preview.</p>"})
notice.action_campus_publish()
env.cr.commit()
data = env["campus.faculty.home"].with_user(teacher).get_home()
print("Sample faculty Home:", data["counts"])
print("Subject attendance:", [(row["name"], row["rate"]) for row in data["attendance"]])
print("Dashboard action:", env.ref("ideastone_erp.action_dashboard").id)
