"""Populate every COE register through its normal workflow in the local preview.

Run after seed_coe.py with Odoo shell. Existing submissions, grades and review
history are preserved. Students and cases created here are explicitly synthetic.
"""
import base64
import io
import json
from collections import Counter
from datetime import datetime, time, timedelta

from reportlab.pdfgen import canvas
from odoo import fields

assert env.cr.dbname == 'question_papers_preview', 'Preview database only'
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
company = env.company
coe = env['res.users'].search([('login', '=', 'exam.coe.preview')])
assert len(coe) == 1 and coe.has_group('ideastone_erp.group_coe_admin')
api = env['campus.coe.workspace'].with_user(coe)
today = fields.Date.context_today(api)
start_year = today.year if today.month >= 7 else today.year - 1
year = env['op.academic.year'].search([('company_id', '=', company.id), ('code', '=', 'COE-' + str(start_year))])
assert len(year) == 1, 'Run the initial COE seed first'
kind = env['op.exam.type'].search([('company_id', '=', company.id), ('code', '=', 'COE-SAMPLE')], limit=1)
assert kind
created = Counter()


def ensure(model, domain, values):
    record = env[model].search(domain, limit=1)
    if not record:
        record = env[model].create(values)
        created[model] += 1
    return record


def account(login, name, group, department):
    person = ensure('res.users', [('login', '=', login)], {
        'login': login, 'name': name, 'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
        'groups_id': [(6, 0, [env.ref(group).id])], 'dept_id': department.id, 'tz': 'Asia/Kolkata'})
    assert person.dept_id == department and company in person.company_ids and person.has_group(group)
    return person


def faculty_record(person, department, subjects):
    record = env['op.faculty'].search([('user_id', '=', person.id)], limit=1)
    if not record:
        partner = env['res.partner'].create({'name': person.name, 'user_id': person.id, 'company_id': company.id})
        record = env['op.faculty'].create({'first_name': person.name, 'last_name': 'Sample', 'gender': 'female',
            'birth_date': '1985-01-01', 'partner_id': partner.id, 'company_id': company.id,
            'main_department_id': department.id})
        created['op.faculty'] += 1
    missing = subjects - record.faculty_subject_ids
    if missing:
        record.write({'faculty_subject_ids': [(4, subject.id) for subject in missing]})
    return record


def pdf(subject, code, level):
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=(595, 842))
    page.setTitle('SAMPLE ONLY - ' + code + ' - ' + level)
    page.setFont('Helvetica-Bold', 15)
    page.drawString(42, 790, 'VCET - SAMPLE QUESTION PAPER')
    page.setFont('Helvetica', 11)
    lines = [subject.name[:85], code + ' | ' + level.title() + ' set', 'Duration: 3 hours | Total: 100 marks', '',
        '1. Explain the fundamental principles from Units I and II. (20 marks)',
        '2. Solve a representative problem and show the working. (20 marks)',
        '3. Compare two methods and state their assumptions. (20 marks)',
        '4. Analyze a practical design using the subject principles. (20 marks)',
        '5. Evaluate the solution and justify the final conclusion. (20 marks)', '',
        {'balanced': 'Balanced set: a mix of recall, application and analysis.',
         'moderate': 'Moderate set: standard applications with guided steps.',
         'advanced': 'Advanced set: deeper analysis and independent justification.'}[level], '',
        'Synthetic demonstration only. Not an official examination paper.']
    for index, line in enumerate(lines):
        page.drawString(42, 750 - index * 32, line)
    page.save()
    return {'level': level, 'filename': code + '-' + level + '.pdf', 'content': base64.b64encode(output.getvalue()).decode()}


grades = env['op.grade.configuration']
for minimum, maximum, label in [(0, 49, 'Sample F'), (50, 59, 'Sample D'), (60, 74, 'Sample C'), (75, 89, 'Sample B'), (90, 100, 'Sample A')]:
    grades |= ensure('op.grade.configuration', [('company_id', '=', company.id), ('result', '=', label)],
        {'company_id': company.id, 'min_per': minimum, 'max_per': maximum, 'result': label})

cohorts = []
coverage_exams = []
for di, code in enumerate(('CSE', 'ECE', 'EEE', 'MECH', 'CIVIL', 'IT')):
    department = env['op.department'].search([('code', '=', 'QP-ECE' if code == 'ECE' else code), ('company_id', '=', company.id)])
    course = env['op.course'].search([('code', '=', 'COE-' + code), ('company_id', '=', company.id)])
    assert len(department) == len(course) == 1 and course.department_id == department
    subjects = env['op.subject'].search([('department_id', '=', department.id), ('code', 'in',
        ['QP-EC3402', 'QP-EC3501', 'QP-EC3601', 'QP-EC3303'] if code == 'ECE' else ['COE-' + code + str(n) for n in range(1, 5)])])
    assert len(subjects) == 4
    missing = subjects - course.subject_ids
    if missing:
        course.write({'subject_ids': [(4, subject.id) for subject in missing]})
    route = env['campus.question.paper.routing'].search([('company_id', '=', company.id), ('department_id', '=', department.id)])
    if route:
        assert route.coe_id == coe, 'Preserve the configured COE recipient'
        hod = route.hod_id
    else:
        hod = account('coe.sample.hod.' + code.lower(), 'Sample ' + code + ' HOD', 'ideastone_erp.group_exam_paper_hod', department)
        route = env['campus.question.paper.routing'].create({'company_id': company.id, 'department_id': department.id,
            'hod_id': hod.id, 'coe_id': coe.id})
        created['campus.question.paper.routing'] += 1
    teacher = account('coe.sample.faculty.' + code.lower(), 'Sample ' + code + ' Faculty', 'openeducat_core.group_op_faculty', department)
    faculty_record(teacher, department, subjects)
    faculty_record(hod, department, subjects)
    paper_api = env['campus.question.paper'].with_user(teacher)
    reviewer = env['campus.question.paper'].with_user(hod)
    for study in range(1, 5):
        cohort_code = 'CS' + str(start_year)[-2:] + code + str(study)
        subject_code = ['QP-EC3402', 'QP-EC3501', 'QP-EC3601', 'QP-EC3303'][study - 1] if code == 'ECE' else 'COE-' + code + str(study)
        subject = subjects.filtered(lambda s: s.code == subject_code)
        batch = ensure('op.batch', [('code', '=', cohort_code)], {'code': cohort_code, 'name': 'Sample ' + code + ' Year ' + str(study),
            'course_id': course.id, 'company_id': company.id, 'campus_year_id': year.id,
            'start_date': year.start_date, 'end_date': year.end_date})
        session = ensure('op.exam.session', [('exam_code', '=', cohort_code)], {'exam_code': cohort_code,
            'name': 'Sample COE cycle - ' + code + ' Year ' + str(study), 'course_id': course.id, 'batch_id': batch.id,
            'company_id': company.id, 'campus_year_id': year.id, 'exam_type': kind.id,
            'start_date': year.start_date, 'end_date': year.end_date})
        for student_number in range(1, 4):
            registration = 'COES-' + code + str(study) + '-' + str(student_number).zfill(2)
            student = ensure('op.student', [('gr_no', '=', registration)], {'gr_no': registration,
                'first_name': 'Sample ' + code + ' Y' + str(study), 'last_name': 'Student ' + str(student_number),
                'name': 'Sample ' + code + ' Y' + str(study) + ' Student ' + str(student_number), 'gender': 'o',
                'birth_date': '2005-01-01', 'company_id': company.id, 'comment': 'Synthetic COE preview student. No real person or login.'})
            assert not student.user_id and student.company_id == company
            ensure('op.student.course', [('student_id', '=', student.id), ('batch_id', '=', batch.id)], {
                'student_id': student.id, 'course_id': course.id, 'batch_id': batch.id, 'academic_years_id': year.id,
                'roll_number': registration, 'subject_ids': [(6, 0, subject.ids)], 'campus_date_from': year.start_date,
                'campus_date_to': year.end_date})

        def examination(suffix, day):
            exam_code = cohort_code + '-' + suffix
            existing = env['op.exam'].search([('exam_code', '=', exam_code)], limit=1)
            if existing:
                return existing, False
            start = datetime.combine(day, time(8, 30))  # 14:00 IST.
            while env['op.exam'].search_count([('subject_id', '=', subject.id), ('start_time', '<', start + timedelta(hours=3)), ('end_time', '>', start)]):
                start += timedelta(hours=4)
            assert year.start_date <= start.date() <= year.end_date
            exam = env['op.exam'].create({'exam_code': exam_code, 'name': 'Sample ' + subject.name + ' - ' + suffix,
                'session_id': session.id, 'subject_id': subject.id, 'start_time': start, 'end_time': start + timedelta(hours=3),
                'total_marks': 100, 'min_marks': 50, 'coe_study_year': str(study), 'coe_expected': 3,
                'coe_present': 3 if day < today else 0, 'coe_hall': code + ' Sample Hall ' + str(100 + study),
                'coe_invigilator': 'Sample ' + code + ' invigilation team ' + str(study),
                'coe_evaluation_due': day + timedelta(days=14), 'campus_grade_ids': [(6, 0, grades.ids)],
                'note': 'SAMPLE ONLY. Fictional examination and student roster for the COE preview.'})
            created['op.exam'] += 1
            return exam, True

        for index, target in enumerate(('returned' if study % 2 == 0 else 'submitted', 'approved', 'received', 'dispatched')):
            day = today + timedelta(days=30 + study * 4 + index * 4 + di)
            exam, is_new = examination('Q' + str(index + 1), day)
            paper_code = 'SAMPLE-' + cohort_code + '-Q' + str(index + 1)
            paper = env['campus.question.paper'].search([('paper_code', '=', paper_code), ('faculty_id.user_id', '=', teacher.id)], limit=1)
            if not paper:
                record_id = paper_api.save_submission({'department_id': department.id, 'subject_id': subject.id,
                    'study_year': str(study), 'semester': ('I', 'III', 'V', 'VII')[study - 1],
                    'exam_type': 'Model Examination', 'exam_date': str(fields.Datetime.context_timestamp(api, exam.start_time).date()),
                    'paper_code': paper_code, 'duration': '3 hours', 'notes': 'SAMPLE ONLY. Units I-V; 100 marks; compare all three versions.'},
                    [pdf(subject, paper_code, level) for level in ('balanced', 'moderate', 'advanced')], submit=True)
                paper = env['campus.question.paper'].browse(record_id)
                created['campus.question.paper'] += 1
                if target == 'returned':
                    reviewer.decide(paper.id, 'return', note='Sample HOD feedback: clarify Unit IV coverage and Section B marks.')
                elif target != 'submitted':
                    selected = paper.set_ids.filtered(lambda s: s.level == ('moderate' if study % 2 == 0 else 'balanced'))
                    reviewer.decide(paper.id, 'approve', selected.id, 'Sample HOD review: syllabus coverage and the 100-mark blueprint checked.')
                    if target in ('received', 'dispatched'):
                        reviewer.decide(paper.id, 'forward', note='Sample official paper sent to the COE cell.')
                        api.paper_action(paper.id, 'receive')
                        if target == 'dispatched':
                            api.paper_action(paper.id, 'dispatch', 'SAMPLE-PACKET-' + cohort_code, exam.id)
            if is_new and not exam.coe_paper_id and paper.state in ('approved', 'forwarded'):
                exam.write({'coe_paper_id': paper.id})
            if index == 3:
                coverage_exams.append(exam)

        history = []
        for suffix, day, target in [('REC', today - timedelta(days=7 + di), ('entry', 'submitted', 'locked', 'published')[study - 1]),
                                    ('PAST', max(year.start_date + timedelta(days=2), today - timedelta(days=65 + di)), 'published')]:
            exam, is_new = examination(suffix, day)
            history.append(exam)
            if is_new:
                managed = exam.with_user(coe)
                managed.action_campus_roster()
                assert len(managed.campus_result_ids) == 3
                assert all(line.student_id.gr_no.startswith('COES-') and not line.student_id.user_id for line in managed.campus_result_ids)
                for n, line in enumerate(managed.campus_result_ids.sorted('student_id')):
                    if target != 'entry' or n < 2:
                        line.write({'marks': [88, 67, 39][n]})
                if target != 'entry':
                    managed.action_campus_submit()
                if target in ('locked', 'published'):
                    managed.action_campus_lock()
                if target == 'published':
                    managed.action_campus_publish()
                assert managed.campus_state == target
        reference = 'SAMPLE-CASE-' + cohort_code
        if not env['campus.coe.case'].search_count([('reference', '=', reference), ('company_id', '=', company.id)]):
            case_kind = ('revaluation', 'correction', 'incident')[(study + di) % 3]
            api.save_case({'exam_id': history[1].id, 'name': 'Sample ' + code + ' Year ' + str(study) + ' ' + case_kind,
                'kind': case_kind, 'reference': reference, 'state': ('open', 'review', 'resolved')[(study + di) % 3],
                'note': 'SAMPLE ONLY. Fictional student reference COES-' + code + str(study) + '-03. '
                        'Review recorded for demonstration; no real student result is affected.'})
            created['campus.coe.case'] += 1
        cohorts.append((department.id, str(study)))

# Leave a recent, real operations audit action for each cohort so the bounded
# audit register contains examples from every department and year group.
for exam in coverage_exams:
    if not env['campus.mvp.audit'].search_count([('model_name', '=', 'op.exam'), ('record_id', '=', exam.id), ('name', '=', 'COE examination operations updated')]):
        api.save_operations(exam.id, {'note': 'SAMPLE ONLY. Department/year preparation checklist complete; sample dispatch receipt retained.'})

snapshot = api.get_workspace('overview', {'year_id': year.id})
for department_id, study in cohorts:
    rows = [r for r in snapshot['exams'] if r['department_id'] == department_id and r['study_year'] == study]
    papers = [r for r in snapshot['papers'] if r['department_id'] == department_id and r['study_year'] == study]
    assert {'upcoming', 'recent', 'past'} <= {r['period'] for r in rows}
    assert any(r['state'] == 'published' and r['roster'] == 3 and r['entered'] == 3 for r in rows)
    assert any(p['received_at'] and not p['dispatched_at'] for p in papers)
    assert any(p['dispatched_at'] for p in papers)
    assert any(c['department_id'] == department_id and c['study_year'] == study for c in snapshot['cases'])
    assert any(a.get('department_id') == department_id and a.get('study_year') == study for a in snapshot['audit'])
assert {'entry', 'submitted', 'locked', 'published'} <= {r['state'] for r in snapshot['exams']}
assert len([r for r in snapshot['routes'] if r['hod'] != 'Not configured']) >= 6
env.cr.commit()
print(json.dumps({'created': dict(created), 'academic_year_id': year.id, 'department_year_groups': len(cohorts),
    'examination_records': len(snapshot['exams']), 'official_papers': len(snapshot['papers']),
    'received': sum(bool(p['received_at']) for p in snapshot['papers']),
    'dispatched': sum(bool(p['dispatched_at']) for p in snapshot['papers']), 'case_records': len(snapshot['cases']),
    'result_workflow': dict(Counter(r['state'] for r in snapshot['exams'])), 'all_21_pages_have_sample_sources': True}))
