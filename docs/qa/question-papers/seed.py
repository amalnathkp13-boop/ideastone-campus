"""Run with Odoo shell only against the dedicated question_papers_preview database."""
import base64
import io
import os
from datetime import timedelta

from reportlab.pdfgen import canvas
from odoo import fields

assert env.cr.dbname == 'question_papers_preview', 'Preview database only'
password = os.environ['QP_PREVIEW_PASSWORD']
env = env(context=dict(env.context, no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))
env['ir.cron'].search([]).write({'active': False})
env['ir.mail_server'].search([]).write({'active': False})
env['auth.oauth.provider'].search([]).write({'enabled': False})
env['ir.config_parameter'].sudo().set_param('web.base.url.freeze', 'True')
env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://localhost:18072')
company = env.company
company.name = 'VCET Question Paper Preview College'
if env['res.users'].search([('login', '=', 'exam.faculty.preview')]):
    raise RuntimeError('Preview already seeded; do not overwrite review history')
dept = env['op.department'].create({'name': 'Electronics & Communication Engineering', 'code': 'QP-ECE'})

def user(login, name, groups):
    return env['res.users'].with_context(no_reset_password=True).create({'login': login, 'name': name, 'password': password,
        'company_id': company.id, 'company_ids': [(6, 0, company.ids)], 'groups_id': [(6, 0, [env.ref(g).id for g in groups.split(',')])],
        'dept_id': dept.id, 'tz': 'Asia/Kolkata'})

faculty = user('exam.faculty.preview', 'Dr. Julie Wilson', 'openeducat_core.group_op_faculty')
hod = user('exam.hod.preview', 'Dr. S. Kumar · HOD', 'ideastone_erp.group_exam_paper_hod')
coe = user('exam.coe.preview', 'Exam Control · Preview', 'ideastone_erp.group_exam_paper_coe')
other = user('exam.other.preview', 'Maria C Daniel', 'openeducat_core.group_op_faculty')
subjects = env['op.subject'].create([{'name': name, 'code': code, 'department_id': dept.id} for name, code in [
    ('Digital Electronics', 'QP-EC3402'), ('Communication Systems', 'QP-EC3501'), ('Microprocessors', 'QP-EC3601'),
    ('Signals and Systems', 'QP-EC3303'), ('Engineering Mathematics', 'QP-MA3401')]])
for account in (faculty, hod, other):
    env['op.faculty'].create({'first_name': account.name, 'last_name': 'Preview', 'birth_date': '1980-01-01', 'gender': 'female',
        'partner_id': env['res.partner'].create({'name': account.name, 'user_id': account.id, 'company_id': company.id}).id,
        'company_id': company.id, 'main_department_id': dept.id, 'faculty_subject_ids': [(6, 0, subjects.ids)]})
env['campus.question.paper.routing'].create({'department_id': dept.id, 'hod_id': hod.id, 'coe_id': coe.id})

def pdf(subject, level):
    out = io.BytesIO()
    page = canvas.Canvas(out)
    page.setTitle('SYNTHETIC PREVIEW — ' + subject.name)
    for index, line in enumerate(['VCET — SYNTHETIC PREVIEW PAPER', subject.name + ' · ' + level.title(),
            'CAT II | Duration: 3 hours | Total: 100 marks', '1. Explain the core concepts of this subject. (20 marks)',
            '2. Solve a representative application problem. (20 marks)', '3. Compare two approaches with examples. (20 marks)',
            '4. Analyze a design scenario. (20 marks)', '5. Evaluate a practical case study. (20 marks)',
            'Sample questions only. Not an official examination paper.']):
        page.drawString(45, 790-index*32, line)
    page.save()
    return {'level': level, 'filename': subject.code+'-'+level+'.pdf', 'content': base64.b64encode(out.getvalue()).decode()}

for n, target in enumerate(['submitted','submitted','returned','approved','forwarded','draft',
                            'submitted','submitted','returned','approved','approved','forwarded','forwarded']):
    account = faculty if n < 6 else other
    subject = subjects[n % len(subjects)]
    values = {'department_id': dept.id, 'subject_id': subject.id, 'exam_type': ['Internal Assessment — CAT II','Model Examination','Internal Assessment — CAT I'][n%3],
        'study_year': str(n % 4 + 1), 'semester': ('I', 'III', 'V', 'VII')[n % 4],
        'exam_date': str(fields.Date.today()+timedelta(days=17+n)), 'paper_code': subject.code.replace('QP-',''), 'duration': '3 hours',
        'notes': 'Syllabus units I–V. Review the 100-mark blueprint. Synthetic preview data.'}
    api = env['campus.question.paper'].with_user(account)
    record_id = api.save_submission(values, [pdf(subject, level) for level in ('balanced','moderate','advanced')], submit=target!='draft')
    reviewer = api.with_user(hod)
    if target == 'returned':
        reviewer.decide(record_id, 'return', note='Please clarify unit coverage and the marks allocation in Section B.')
    if target in ('approved','forwarded'):
        row = next(r for r in api.get_workspace()['rows'] if r['id']==record_id)
        reviewer.decide(record_id, 'approve', row['sets'][0]['id'], 'Syllabus and blueprint verified.')
        if target == 'forwarded':
            reviewer.decide(record_id, 'forward', note='Official selected paper delivered to exam control.')
env.cr.commit()
print({'faculty_action': env.ref('ideastone_erp.action_faculty_question_papers').id,
       'faculty_login': faculty.login, 'hod_login': hod.login, 'coe_login': coe.login, 'preview_submissions': 13})
