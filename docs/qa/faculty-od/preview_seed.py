"""Synthetic preview only: native student submission, mentor review and HOD approval."""
# ruff: noqa: F821
import json
import os
import uuid
from datetime import timedelta

from odoo.exceptions import AccessError
from odoo.tests import new_test_user

from odoo import fields

assert env.cr.dbname == 'campus_faculty_od_preview', 'Isolated OD preview database required'
company = env['res.company'].create({'name': 'VCET · OD Preview', 'currency_id': env.ref('base.INR').id})
env = env(context=dict(env.context, allowed_company_ids=[company.id], tz='Asia/Kolkata', no_reset_password=True,
                       mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True))
today = fields.Date.context_today(env['res.users'].with_context(tz='Asia/Kolkata'))

def account(login, name, groups, password=None):
    values = {'login': login, 'name': name, 'groups': groups,
              'company_id': company.id, 'company_ids': [(6, 0, [company.id])], 'tz': 'Asia/Kolkata'}
    if password:
        values['password'] = password
    return new_test_user(env, **values)

mentor = account('faculty.od.preview', 'Dr. Julie Wilson', 'openeducat_core.group_op_faculty', os.environ['OD_FACULTY_PASSWORD'])
hod = account('hod.od.preview', 'Dr. Priya Raman', 'ideastone_erp.group_od_hod_approver', os.environ['OD_HOD_PASSWORD'])
other_mentor = account('other.faculty.od.preview', 'OD Preview Other Mentor', 'openeducat_core.group_op_faculty')
department = env['op.department'].create({'name': 'Electronics & Communication Engineering', 'code': 'ODREF'})
hod.dept_id = department
course = env['op.course'].create({'name': 'B.E. Electronics & Communication Engineering', 'code': 'ODREF', 'department_id': department.id})
year = env['op.academic.year'].create({'name': '2026–2027 · OD Preview', 'code': 'ODREF',
    'start_date': today - timedelta(days=100), 'end_date': today + timedelta(days=250), 'campus_current': True})
term = env['op.academic.term'].create({'name': 'Semester V', 'academic_year_id': year.id, 'campus_course_id': course.id,
    'term_start_date': year.start_date, 'term_end_date': year.end_date})
batch = env['op.batch'].create({'name': 'ECE · III A', 'code': 'ODREFA', 'course_id': course.id,
    'campus_year_id': year.id, 'campus_term_id': term.id, 'start_date': year.start_date, 'end_date': year.end_date})
second_batch = batch.copy({'name': 'ECE · III B', 'code': 'ODREFB'})
faculty_partner = env['res.partner'].create({'name': mentor.name, 'user_id': mentor.id, 'company_id': company.id})
env['op.faculty'].create({'first_name': 'Julie', 'last_name': 'Wilson', 'gender': 'female', 'birth_date': '1985-06-12',
                          'partner_id': faculty_partner.id, 'main_department_id': department.id})
names = ['Kavya R.', 'Arun S.', 'Meena P.', 'Nithin K.', 'Divya M.', 'Rahul V.', 'Ananya S.', 'Sanjay R.',
         'Priya K.', 'Aditya N.', 'Harini V.', 'Vignesh S.', 'Sneha R.', 'Karthik P.', 'Pooja M.', 'Bharath K.',
         'Lakshmi S.', 'Surya N.', 'Swathi P.', 'Ajay R.', 'Deepa K.', 'Vivek M.', 'Keerthi S.', 'Ashwin P.',
         'Section B Sample', 'Other Mentor Sample']
students = []
for index, name in enumerate(names):
    partner = env['res.partner'].create({'name': name, 'company_id': company.id, 'email': f'od.student.{index}@example.test'})
    student = env['op.student'].create({'first_name': name.split(' ', 1)[0], 'last_name': name.split(' ', 1)[1],
        'gender': 'o', 'birth_date': '2005-01-01', 'partner_id': partner.id, 'gr_no': f'ODREF{index:03d}'})
    portal = account(f'od.student.{index}@example.test', name, 'base.group_portal')
    # The portal identity must be the student's own contact.
    portal.partner_id = partner
    student.user_id = portal
    chosen_batch = second_batch if index == 24 else batch
    env['op.student.course'].create({'student_id': student.id, 'course_id': course.id, 'batch_id': chosen_batch.id,
        'academic_years_id': year.id, 'academic_term_id': term.id, 'campus_date_from': year.start_date,
        'campus_date_to': year.end_date, 'state': 'running'})
    env['campus.student.leave.routing'].create({'name': f'OD reference · {name}', 'student_id': student.id,
        'advisor_id': (other_mentor if index == 25 else mentor).id, 'hod_id': hod.id})
    students.append((student, portal))

mentor_ui = env['campus.staff.od.ui'].with_user(mentor)
hod_ui = env['campus.hod.od.ui'].with_user(hod)
created = []
def submit(index, offset, title, outcome='pending'):
    student, user = students[index]
    day = today + timedelta(days=offset)
    key = uuid.uuid4().hex
    env['campus.student.portal'].with_user(user).act('od_submit', {'key': key, 'name': title,
        'purpose': f'Sample application: {title.lower()} and departmental participation.', 'venue': 'Partner College Auditorium',
        'od_date_from': str(day), 'od_date_to': str(day), 'od_from_session': 'forenoon', 'od_to_session': 'afternoon'})
    record = env['campus.student.od'].search([('submission_key', '=', key)])
    if outcome in {'approved', 'hod'}:
        mentor_ui.review_request(record.id, 'forward', 'Sample review: academic purpose verified.')
    if outcome == 'approved':
        hod_ui.decide(record.id, 'approve', category='general', note='Sample HOD approval.')
    if outcome == 'returned':
        mentor_ui.review_request(record.id, 'return', 'Sample review: please clarify the event invitation.')
    created.append(record.id)
    return record

# Historical and current approvals; two distinct students are on OD today.
for index in range(12):
    submit(2 + index % 10, 0 if index < 2 else -3 - index, ['Paper presentation', 'Industry visit', 'Workshop participation'][index % 3], 'approved')
submit(4, 2, 'Department project exhibition', 'hod')
submit(5, 4, 'Research seminar', 'returned')
submit(0, 3, 'Inter-college coding challenge')
submit(1, 1, 'Project review')
submit(0, 0, 'Technical symposium')
# Separate class and mentor data verifies scope without changing the primary 24-student class.
submit(24, 5, 'Section B technical visit')
other_student, other_user = students[25]
env['campus.student.portal'].with_user(other_user).act('od_submit', {'key': uuid.uuid4().hex, 'name': 'Other mentor event',
    'purpose': 'Sample scope isolation check', 'venue': 'Sample campus', 'od_date_from': str(today), 'od_date_to': str(today),
    'od_from_session': 'forenoon', 'od_to_session': 'afternoon'})
page = mentor_ui.get_page_data(f'{batch.id}:{term.id}')
assert (page['total_students'], page['pending'], page['approved'], page['students_on_od']) == (24, 3, 12, 2)
assert page['repeated_students'] > 0 and page['overlapping_students'] > 0 and page['urgent_reviews'] == 2
outside = env['campus.staff.od.ui'].with_user(other_mentor).get_page_data()
assert len(outside['rows']) == 1 and outside['rows'][0]['student_id'] == other_student.id
try:
    env['campus.staff.od.ui'].with_user(other_mentor).review_request(created[-2], 'forward')
except AccessError:
    pass
else:
    raise AssertionError('Unassigned mentor must not be able to review another class request')
result = {'company_id': company.id, 'faculty': mentor.login, 'hod': hod.login, 'class_key': page['class_key'],
          'action_id': env.ref('ideastone_erp.action_staff_od_management').id,
          'counts': {key: page[key] for key in ('total_students', 'pending', 'approved', 'students_on_od', 'repeated_students', 'overlapping_students', 'urgent_reviews')},
          'sample_request_ids': created}
env.cr.commit()
print('OD_PREVIEW ' + json.dumps(result))
