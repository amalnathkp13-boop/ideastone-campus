"""Run once in Odoo shell against the shared, isolated localhost preview."""
from datetime import date, datetime, time, timedelta
from odoo import fields

assert env.cr.dbname == 'question_papers_preview', 'Preview database only'
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
company = env.company
coe = env['res.users'].search([('login', '=', 'exam.coe.preview')])
assert len(coe) == 1, 'The question-paper preview accounts must already exist'
coe.write({'groups_id': [(4, env.ref('ideastone_erp.group_coe_admin').id)],
           'action_id': env.ref('ideastone_erp.action_coe_overview').id})
today = fields.Date.context_today(env['op.exam'])
start_year = today.year if today.month >= 7 else today.year - 1


def ensure(model, domain, values):
    return env[model].search(domain, limit=1) or env[model].create(values)


year = ensure('op.academic.year', [('company_id', '=', company.id), ('code', '=', 'COE-' + str(start_year))],
              {'name': str(start_year) + '–' + str(start_year + 1)[-2:] + ' · COE sample', 'code': 'COE-' + str(start_year),
               'start_date': date(start_year, 7, 1), 'end_date': date(start_year + 1, 6, 30), 'company_id': company.id})
previous = ensure('op.academic.year', [('company_id', '=', company.id), ('code', '=', 'COE-' + str(start_year - 1))],
              {'name': str(start_year - 1) + '–' + str(start_year)[-2:] + ' · COE sample', 'code': 'COE-' + str(start_year - 1),
               'start_date': date(start_year - 1, 7, 1), 'end_date': date(start_year, 6, 30), 'company_id': company.id})
exam_type = ensure('op.exam.type', [('name', '=', 'COE sample assessment'), ('company_id', '=', company.id)],
                   {'name': 'COE sample assessment', 'code': 'COE-SAMPLE', 'company_id': company.id})
created = []
for di, (code, name) in enumerate([('CSE', 'Computer Science & Engineering'), ('ECE', 'Electronics & Communication Engineering'),
    ('EEE', 'Electrical & Electronics Engineering'), ('MECH', 'Mechanical Engineering'), ('CIVIL', 'Civil Engineering'), ('IT', 'Information Technology')]):
    dept_code = 'QP-ECE' if code == 'ECE' else code
    dept = ensure('op.department', [('code', '=', dept_code), ('company_id', '=', company.id)],
                  {'name': name, 'code': dept_code, 'company_id': company.id})
    course = ensure('op.course', [('code', '=', 'COE-' + code)],
                    {'name': 'B.E. ' + name + ' · Sample', 'code': 'COE-' + code, 'department_id': dept.id, 'company_id': company.id})
    if course.department_id != dept:
        old_department = course.department_id
        course.department_id = dept
        env['op.subject'].search([('code', '=like', 'COE-' + code + '%'), ('department_id', '=', old_department.id)]).write({'department_id': dept.id})
        if old_department.code == 'COE-' + code:
            old_department.active = False
    for academic in (year, previous):
        for study in range(1, 5):
            if academic == previous and study > 2:
                continue
            key = 'C' + str(academic.start_date.year)[-2:] + code + str(study)
            batch = ensure('op.batch', [('code', '=', key)], {'name': code + ' · Year ' + str(study), 'code': key,
                'course_id': course.id, 'start_date': academic.start_date, 'end_date': academic.end_date,
                'campus_year_id': academic.id, 'company_id': company.id})
            session = ensure('op.exam.session', [('exam_code', '=', key)], {'name': 'Sample semester assessments · ' + code + ' · Year ' + str(study),
                'exam_code': key, 'course_id': course.id, 'batch_id': batch.id, 'campus_year_id': academic.id,
                'company_id': company.id, 'exam_type': exam_type.id, 'start_date': academic.start_date, 'end_date': academic.end_date})
            ece_codes = ['QP-EC3402', 'QP-EC3501', 'QP-EC3601', 'QP-EC3303']
            subject_code = ece_codes[study - 1] if code == 'ECE' else 'COE-' + code + str(study)
            subject = ensure('op.subject', [('code', '=', subject_code), ('department_id', '=', dept.id)],
                 {'name': ['Engineering Foundations', name + ' Fundamentals', name + ' Applications', name + ' Design'][study - 1],
                  'code': subject_code, 'department_id': dept.id, 'company_id': company.id})
            dates = [today + timedelta(days=5 + study * 3 + di)] if academic == year else [academic.end_date - timedelta(days=20 + di)]
            if academic == year and study == 3:
                dates += [today - timedelta(days=5 + di)]
            if academic == year and study == 4:
                dates += [max(academic.start_date + timedelta(days=1), today - timedelta(days=55 + di))]
            for index, day in enumerate(dates):
                exam_code = key + '-' + str(index)
                if env['op.exam'].search_count([('exam_code', '=', exam_code)]):
                    continue
                start = datetime.combine(day, time(4, 0))  # 09:30 IST, stored in UTC.
                exam = env['op.exam'].create({'name': subject.name + ' · Sample assessment', 'exam_code': exam_code,
                    'session_id': session.id, 'subject_id': subject.id, 'start_time': start, 'end_time': start + timedelta(hours=3),
                    'total_marks': 100, 'min_marks': 50, 'coe_study_year': str(study), 'coe_expected': 60 + di * 6,
                    'coe_present': 58 + di * 6 if day < today else 0,
                    'coe_hall': '' if (di + study) % 5 == 0 else code + ' Block · ' + str(100 + study),
                    'coe_invigilator': '' if (di + study) % 4 == 0 else 'Sample invigilation team ' + code,
                    'coe_evaluation_due': day + timedelta(days=14), 'note': 'SAMPLE ONLY. Examination-cell planning example; no student results have been published.'})
                created.append(exam.id)

api = env['campus.coe.workspace'].with_user(coe)
paper = env['campus.question.paper'].search([('coe_id', '=', coe.id), ('state', '=', 'forwarded'),
    ('paper_code', '=', 'DEMO-EC3601-04'), ('exam_date', '>', today)], limit=1)
if paper:
    matching = env['op.exam'].search([('exam_code', '=', 'COE-PACKET-01')], limit=1)
    if not matching:
        session = env['op.exam.session'].search([('exam_code', '=', 'C' + str(start_year)[-2:] + 'ECE3')], limit=1)
        start = datetime.combine(paper.exam_date, time(4))
        matching = env['op.exam'].create({'name': 'Microprocessors · Official paper handover sample', 'exam_code': 'COE-PACKET-01',
            'session_id': session.id, 'subject_id': paper.subject_id.id, 'start_time': start, 'end_time': start + timedelta(hours=3),
            'total_marks': 100, 'min_marks': 50, 'coe_study_year': '3', 'coe_expected': 72,
            'coe_hall': 'ECE Block · 303', 'coe_invigilator': 'Sample ECE invigilation team',
            'note': 'SAMPLE ONLY. Matching schedule for the HOD-approved official paper receipt and dispatch workflow.'})
past = env['op.exam'].search([('exam_code', 'like', 'C' + str(start_year)[-2:]), ('end_time', '<', fields.Datetime.now())], limit=3)
for index, exam in enumerate(past):
    ref = 'DEMO-COE-' + str(index + 1)
    if not env['campus.coe.case'].search_count([('reference', '=', ref)]):
        api.save_case({'exam_id': exam.id, 'name': ['Sample revaluation request', 'Sample name correction', 'Sample examination incident'][index],
            'kind': ['revaluation', 'correction', 'incident'][index], 'reference': ref,
            'note': 'Synthetic case for reviewing the COE workflow. No real student record is affected.', 'state': 'review' if index == 0 else 'open'})

snapshot = api.get_workspace('overview', {'year_id': year.id})
assert all(any(r['study_year'] == str(n) for r in snapshot['exams']) for n in range(1, 5))
assert {'upcoming', 'recent', 'past'} <= {r['period'] for r in snapshot['exams']}
assert len(snapshot['papers']) >= 1
env.cr.commit()
print({'coe_login': coe.login, 'home_action': coe.action_id.id, 'academic_year_id': year.id,
       'new_examinations': len(created), 'current_year_records': len(snapshot['exams']), 'official_papers': len(snapshot['papers'])})
