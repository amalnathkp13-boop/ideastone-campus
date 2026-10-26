"""Add examples to both existing staff logins in the local examinations preview.

Run in Odoo shell. Rerunning preserves existing submissions and review history.
"""
import base64
import io
from datetime import timedelta

from reportlab.pdfgen import canvas
from odoo import fields

assert env.cr.dbname == 'question_papers_preview', 'Preview database only'
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
route = env['campus.question.paper.routing'].search([('department_id.code', '=', 'QP-ECE')])
assert len(route) == 1, 'Run the initial question-paper preview seed first'
env = env(context=dict(env.context, allowed_company_ids=route.company_id.ids))
route._check_reviewers()
subjects = env['op.subject'].search([('department_id', '=', route.department_id.id)], order='code')
assert len(subjects) >= 5
questions = {
    'QP-EC3402': ['Design a full adder and explain its truth table.', 'Compare synchronous and asynchronous counters.'],
    'QP-EC3501': ['Explain amplitude modulation using a labelled block diagram.', 'Compare FM and AM noise performance.'],
    'QP-EC3601': ['Explain the 8086 architecture with a labelled diagram.', 'Write an algorithm for sorting an array using assembly instructions.'],
    'QP-EC3303': ['Determine the convolution of two finite duration signals.', 'Explain sampling and the conditions needed to avoid aliasing.'],
    'QP-MA3401': ['Solve a second order linear differential equation with constant coefficients.', 'Explain how a Fourier series represents a periodic function.'],
}


def pdf(subject, level, code):
    out = io.BytesIO()
    page = canvas.Canvas(out, pagesize=(595, 842))
    page.setTitle('SAMPLE ONLY - ' + code + ' - ' + level)
    page.setFont('Helvetica-Bold', 15)
    page.drawString(42, 792, 'VCET - SAMPLE QUESTION PAPER')
    page.setFont('Helvetica', 11)
    lines = [subject.name, code + ' | ' + level.title() + ' set',
             'Duration: 3 hours | Total marks: 100', '', 'SECTION A - Answer all questions (2 x 10 = 20 marks)',
             '1. Define two fundamental concepts from Units I and II.',
             '2. State the assumptions used in a standard application.', '',
             'SECTION B - Answer both questions (2 x 20 = 40 marks)']
    lines += [str(i + 3) + '. ' + question for i, question in enumerate(questions[subject.code])]
    lines += ['', 'SECTION C - Application (1 x 40 = 40 marks)',
              '5. Apply the methods above to a practical case and justify your solution.', '',
              'Difficulty guidance: ' + {'balanced': 'Mix recall, application and analysis.',
                                       'moderate': 'Emphasise standard applications with clear working.',
                                       'advanced': 'Require deeper analysis and independent justification.'}[level],
              '', 'Synthetic demonstration data. Not an official examination paper.']
    for index, line in enumerate(lines):
        page.drawString(42, 756 - index * 29, line)
    page.save()
    return {'level': level, 'filename': code + '-' + level + '.pdf',
            'content': base64.b64encode(out.getvalue()).decode()}


created = []
for login in ('faculty@openeducat.com', 'exam.faculty.preview'):
    account = env['res.users'].search([('login', '=', login)])
    assert len(account) == 1 and route.company_id in account.company_ids
    api = env['campus.question.paper'].with_user(account)
    faculty = api._faculty()
    # Add only the synthetic preview subjects; retain all existing assignments.
    faculty.write({'faculty_subject_ids': [(4, subject.id) for subject in subjects]})
    for index, target in enumerate(('draft', 'returned', 'approved', 'forwarded', 'submitted', 'submitted')):
        subject = subjects[index % len(subjects)]
        code = 'DEMO-' + subject.code.removeprefix('QP-') + '-' + str(index + 1).zfill(2)
        existing = env['campus.question.paper'].search([
            ('faculty_id', '=', faculty.id), ('company_id', '=', route.company_id.id), ('paper_code', '=', code)])
        if existing:
            continue
        values = {'department_id': route.department_id.id, 'subject_id': subject.id,
                  'exam_type': 'Model Examination' if index % 2 else 'Internal Assessment — CAT II',
                  'exam_date': str(fields.Date.context_today(api) + timedelta(days=10 + index * 2)),
                  'paper_code': code, 'duration': '3 hours',
                  'notes': 'SAMPLE ONLY. Units I–V; 100 marks. Compare the three sets before approving.'}
        record_id = api.save_submission(values, [pdf(subject, level, code) for level in ('balanced', 'moderate', 'advanced')],
                                        submit=target != 'draft')
        reviewer = api.with_user(route.hod_id)
        if target == 'returned':
            reviewer.decide(record_id, 'return', note='Sample feedback: clarify Unit IV coverage and show the marks for each subquestion.')
        if target in ('approved', 'forwarded'):
            paper = env['campus.question.paper'].browse(record_id)
            selected = paper.set_ids.filtered(lambda item: item.level == 'balanced')
            reviewer.decide(record_id, 'approve', selected.id, 'Sample review: syllabus coverage and the 100-mark blueprint checked.')
            if target == 'forwarded':
                reviewer.decide(record_id, 'forward', note='Sample official set delivered to Exam Control.')
        assert env['campus.question.paper'].browse(record_id).state == target
        created.append(record_id)
    rows = api.get_workspace()['rows']
    assert sum(row['paper_code'].startswith('DEMO-') for row in rows) >= 6

hod_rows = env['campus.question.paper'].with_user(route.hod_id).get_workspace('hod')['rows']
assert all(any(row['id'] == record_id for row in hod_rows)
           for record_id in created if env['campus.question.paper'].browse(record_id).state != 'draft')
env.cr.commit()
print({'created': created, 'staff_logins': ['faculty@openeducat.com', 'exam.faculty.preview'],
       'hod_login': route.hod_id.login, 'hod_visible_submissions': len(hod_rows)})
