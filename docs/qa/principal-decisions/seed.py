"""Synthetic Principal preview data. Run only against a disposable principal_* database."""
import base64
import os
from datetime import timedelta

from odoo import fields

assert env.cr.dbname.startswith('principal_'), 'A disposable Principal database is required'  # noqa: F821
env = env(context=dict(env.context, mail_create_nosubscribe=True, mail_notrack=True, no_reset_password=True))  # noqa: F821
company = env.company
env.ref('base.INR').active = True
company.write({'name': 'Ideastone Demo Engineering College', 'campus_demo': True, 'currency_id': env.ref('base.INR').id})


def fixture(key, model, vals, actor=None):
    external = 'principal_preview.' + key
    record = env.ref(external, raise_if_not_found=False)
    if not record:
        record = env[model].with_user(actor or env.user).create(vals)
        env['ir.model.data'].create({'module': 'principal_preview', 'name': key, 'model': model, 'res_id': record.id, 'noupdate': True})
    return record


def user(key, name, group):
    return fixture(key, 'res.users', {'name': name, 'login': 'principal@campus.local' if key == 'principal' else f'{key}@principal-preview.invalid',
        'email': f'{key}@example.invalid', 'tz': 'Asia/Kolkata', 'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
        'groups_id': [(6, 0, [env.ref(group).id])]})


reviewer = user('principal', 'Principal Preview', 'ideastone_principal.group_principal')
reviewer.write({'password': os.environ['PRINCIPAL_PREVIEW_PASSWORD'], 'action_id': env.ref('ideastone_principal.action_principal_overview').id})
coordinator = user('coordinator', 'Dr. Priya · Event Coordinator', 'base.group_user')
organizer = user('organizer', 'Sample Department Office', 'base.group_user')
advisor = user('advisor', 'Dr. S. Ramesh · Advisor', 'openeducat_core.group_op_faculty')
hod = user('hod', 'Dr. Anitha · HoD', 'base.group_user')
company.principal_leave_reviewer_id = reviewer
service = env['ideastone.principal.decisions'].with_user(reviewer)
today = fields.Date.context_today(reviewer)
start = today + timedelta(days=(7 - today.weekday()) % 7)
if start == today:
    start += timedelta(days=7)

staff_data = [
    ('Dr. Meera Srinivasan', 'FAC-014', 'Computer Science', 'Associate Professor', 'Casual leave', 2, 8, 'Family commitment', 'Lab session assigned to Ms. Kavitha.'),
    ('Arun Kumar', 'STA-022', 'Administration', 'Office Assistant', 'Medical leave', 4, 6, 'Medical rest advised', 'Front desk coverage arranged.'),
    ('Kavitha R.', 'FAC-009', 'Electronics & Communication', 'Assistant Professor', 'Earned leave', 3, 12, 'Personal travel', 'Class adjustment plan supplied.'),
    ('S. Prakash', 'FAC-031', 'Mechanical Engineering', 'Professor', 'On duty', 1, None, 'External academic meeting', 'Department timetable reviewed.'),
    ('Nandhini M.', 'STA-017', 'Library', 'Assistant Librarian', 'Casual leave', 1, 5, 'Personal work', 'Library shift covered.'),
    ('Vijay B.', 'FAC-006', 'Civil Engineering', 'Assistant Professor', 'Medical leave', 2, 3, 'Additional supporting information required', 'Substitute plan supplied.'),
]
for index, (name, code, department, job, category, days, balance, reason, coverage) in enumerate(staff_data):
    dept = fixture(f'department_{index}', 'hr.department', {'name': department, 'company_id': company.id})
    employee = fixture(f'employee_{index}', 'hr.employee', {'name': name, 'barcode': code, 'department_id': dept.id, 'job_title': job, 'company_id': company.id})
    leave_type = fixture(f'type_{category.replace(" ", "_")}', 'hr.leave.type', {'name': category, 'company_id': company.id,
        'requires_allocation': 'yes' if balance is not None else 'no', 'leave_validation_type': 'both'})
    if balance is not None:
        allocation = fixture(f'allocation_{index}', 'hr.leave.allocation', {'name': 'Preview annual leave allocation',
            'employee_id': employee.id, 'holiday_status_id': leave_type.id, 'number_of_days': balance + days,
            'date_from': today.replace(month=1, day=1)})
        if allocation.state == 'draft':
            allocation.action_confirm()
        if allocation.state in ('confirm', 'validate1'):
            allocation.action_validate()
    leave = fixture(f'staff_leave_{index}', 'hr.leave', {'employee_id': employee.id, 'holiday_status_id': leave_type.id,
        'request_date_from': start + timedelta(days=index * 7), 'request_date_to': start + timedelta(days=index * 7 + days - 1),
        'private_name': reason, 'principal_reviewer_id': reviewer.id, 'principal_coverage': coverage, 'principal_recommendation': 'HoD recommended'})
    if leave.state == 'confirm':
        leave.action_approve()
    if index in (4, 5) and leave.state == 'validate1':
        service.decide('staff', leave.id, 'approved' if index == 4 else 'rejected', 'Preview decision: coverage and supporting details reviewed.')
    fixture(f'staff_document_{index}', 'ir.attachment', {'name': 'Preview coverage plan.txt', 'res_model': 'hr.leave', 'res_id': leave.id,
        'datas': base64.b64encode(b'Synthetic preview document. Department coverage and leave dates supplied.'), 'mimetype': 'text/plain'})
    fixture(f'faculty_{index}', 'op.faculty', {'first_name': name.split()[0], 'last_name': ' '.join(name.split()[1:]), 'gender': 'male',
        'birth_date': '1985-01-01', 'partner_id': env['res.partner'].create({'name': name, 'company_id': company.id}).id})

for index, (name, code, days) in enumerate([('Aarav R.', '23ECE041', 30), ('Nisha K.', '22CSE018', 45), ('Hari S.', '24EEE027', 60), ('Divya P.', '23IT011', 30), ('Rohit M.', '22ME032', 61)]):
    student = fixture(f'student_{index}', 'op.student', {'first_name': name.split()[0], 'last_name': ' '.join(name.split()[1:]),
        'gender': 'o', 'gr_no': code, 'company_id': company.id, 'partner_id': env['res.partner'].create({'name': name, 'company_id': company.id}).id})
    route = fixture(f'route_{index}', 'campus.student.leave.routing', {'name': f'Principal preview route {code}', 'company_id': company.id,
        'student_id': student.id, 'advisor_id': advisor.id, 'hod_id': hod.id, 'principal_id': reviewer.id})
    leave = fixture(f'student_leave_{index}', 'campus.student.leave', {'name': 'Long-term medical leave' if index != 2 else 'Semester interruption request',
        'routing_id': route.id, 'reason': 'Synthetic extended treatment and recovery request', 'date': start, 'deadline': start + timedelta(days=days-1),
        'principal_leave_category': 'medical', 'principal_supporting_details': 'Supporting medical statement and an academic continuity plan supplied.'}, advisor)
    if leave.state == 'draft':
        leave.with_user(advisor).action_submit()
    if leave.state == 'advisor':
        leave.with_user(advisor).action_approve()
    if leave.state == 'hod':
        leave.with_user(hod).action_approve()
    if index in (3, 4) and leave.state == 'principal':
        service.decide('student', leave.id, 'approved' if index == 3 else 'rejected', 'Preview decision: academic continuity and evidence reviewed.')

for index, (kind, title, description) in enumerate([
    ('admission', 'Late admission exception · B.E. ECE', 'Application documents verified. Admissions office recommends consideration after the published deadline.'),
    ('academic', 'Special examination sitting · 3 students', 'Medical absence documented. Exam cell scheduling and faculty recommendations supplied.'),
    ('discipline', 'Inter-collegiate technical event participation', 'Faculty in-charge, student list, travel plan and invitation supplied.'),
    ('finance', 'Department laboratory equipment purchase', 'Vendor quotation, budget head and department recommendation supplied.'),
    ('other', 'Temporary duty / workload adjustment', 'Affected classes, substitute coverage and HoD recommendation supplied.'),
]):
    request = fixture(f'request_{index}', 'ideastone.principal.request', {'name': title, 'request_type': kind,
        'description': description, 'company_id': company.id, 'due_date': today + timedelta(days=2)}, organizer)
    if request.state == 'draft':
        request.with_user(organizer).action_submit()

for index, (name, unit, offset, attendees, budget, checked) in enumerate([
    ('Annual Cultural Fest — Varnam', 'Student Affairs · Dr. Meena', 10, 1200, 185000, False),
    ('Industry Connect & Placement Forum', 'Placement Cell · Prof. Karthik', 16, 450, 125000, False),
    ('National Technical Symposium', 'ECE Department · Dr. Priya', 22, 380, 95000, True),
    ('Alumni Homecoming', 'Alumni Relations · Mr. Arun', 33, 700, 75000, True),
    ('Campus Wellness Week', 'Student Welfare · Ms. Divya', 42, 500, 0, True),
]):
    proposal = fixture(f'event_{index}', 'ideastone.principal.event.proposal', {'name': name, 'company_id': company.id,
        'coordinator_id': coordinator.id, 'principal_id': reviewer.id, 'date_start': today + timedelta(days=offset),
        'date_end': today + timedelta(days=offset), 'venue': ['Main Auditorium & Quadrangle', 'Convention Hall', 'ECE Seminar Hall', 'Open Air Theatre', 'Sports Complex'][index],
        'organizer': unit, 'purpose': 'Synthetic campus event proposal for planning and Principal review.', 'attendees': attendees, 'budget': budget,
        'funding': 'Department allocation / sponsor contribution', 'safety_plan': 'First-aid, access routes and facilities coordination supplied.'}, organizer)
    if proposal.state == 'draft':
        proposal.with_user(organizer).action_submit()
    if proposal.state == 'coordinator':
        proposal.with_user(coordinator).write({'venue_checked': True, 'budget_checked': checked, 'safety_checked': checked,
            'recommendation': 'Department review complete; planning checks recorded.'})
        proposal.with_user(coordinator).action_forward()
    if index >= 3 and proposal.state == 'review':
        service.decide('event', proposal.id, 'approved', 'Preview signature: budget, venue and safety confirmed.')

env.cr.commit()
print('Principal preview saved: 6 staff leaves, 5 student leaves, 5 requests, 5 event proposals. No production database modified.')
