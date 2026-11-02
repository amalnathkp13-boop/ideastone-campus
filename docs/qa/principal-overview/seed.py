"""Run with odoo shell in the isolated Principal preview database only."""
from datetime import datetime, timedelta
from odoo import fields

assert env.cr.dbname == 'principal_overview_preview', 'Preview database required'
env = env(context=dict(env.context, allowed_company_ids=[1]))
company = env['res.company'].browse(1)
today = fields.Date.today()

def ensure(model, domain, values):
    return env[model].search(domain, limit=1) or env[model].create(dict(company_id=1, **values))

students = env['op.student'].search([('company_id', '=', 1)], limit=50)
faculty = env['op.faculty'].search([('company_id', '=', 1)], limit=1)
for index, (name, code, present) in enumerate([
    ('Computer Science and Engineering','CSE',10), ('Electronics and Communication Engineering','ECE',9),
    ('Electrical and Electronics Engineering','EEE',9), ('Mechanical Engineering','MECH',7), ('Information Technology','IT',8),
]):
    dept = env['op.department'].search([('name','=',name),('company_id','=',1)],limit=1)
    course = ensure('op.course',[('code','=', 'PP-'+code)],dict(name='[Preview] '+name, code='PP-'+code,department_id=dept.id))
    batch = ensure('op.batch',[('code','=','PP-'+code)],dict(name='Preview '+code,code='PP-'+code,course_id=course.id,start_date='2026-01-01',end_date='2027-05-31'))
    register = ensure('op.attendance.register',[('code','=','PP-'+code)],dict(name='Preview '+code,code='PP-'+code,course_id=course.id,batch_id=batch.id))
    for month in range(6):
        date = fields.Date.subtract(today.replace(day=1),months=5-month)
        if env['op.attendance.sheet'].search_count([('register_id','=',register.id),('attendance_date','=',date)]):
            continue
        sheet = env['op.attendance.sheet'].create(dict(register_id=register.id,attendance_date=date))
        for position, student in enumerate(students[index*10:(index+1)*10]):
            is_present = position < max(4,present - (5-month)//2)
            env['op.attendance.line'].create(dict(attendance_id=sheet.id,student_id=student.id,present=is_present,absent=not is_present))
        sheet.attendance_done()

for index, student in enumerate(students[30:40]):
    ensure('campus.counseling',[('name','=','[Preview] Mentor review '+str(student.id))],dict(name='[Preview] Mentor review '+str(student.id),student_id=student.id,mentor_id=faculty.id,date=today,discussion='Attendance review and agreed study plan.',outcome='Weekly follow-up with class advisor.',follow_up_date=today,future_plan='studies' if index<4 else 'job'))

source = env['account.move'].search([('company_id','=',1),('campus_student_id','!=',False),('state','=','posted'),('move_type','=','out_invoice')],limit=1)
journal = env['account.journal'].search([('company_id','=',1),('type','=','bank')],limit=1)
for month, paid in enumerate([70000,76000,81000,85000,88000,92000]):
    ref = '[Preview] Principal fees '+str(month)
    if env['account.move'].search_count([('ref','=',ref)]): continue
    date = fields.Date.subtract(today.replace(day=1),months=5-month)
    invoice = source.copy(dict(ref=ref,invoice_date=date,invoice_date_due=date,invoice_line_ids=[(0,0,dict(name='Sample semester tuition',account_id=source.invoice_line_ids[0].account_id.id,quantity=1,price_unit=100000,tax_ids=[(5,0,0)]))]))
    invoice.action_post()
    wizard = env['account.payment.register'].with_context(active_model='account.move',active_ids=invoice.ids).create(dict(amount=paid,payment_date=date,journal_id=journal.id,campus_transaction_reference=ref))
    wizard._create_payments()

base_exam = env['op.exam'].search([('company_id','=',1),('campus_managed','=',False)],limit=1)
year = env['op.academic.year'].search([('company_id','=',1),('campus_current','=',True)],limit=1)
exam = env['op.exam'].search([('exam_code','=','PP-IA-2026')],limit=1)
if not exam:
    session = base_exam.session_id.copy(dict(name='[Preview] Assessment session',exam_code='PP-SESSION',start_date=today+timedelta(days=7),end_date=today+timedelta(days=9),campus_year_id=False,exam_ids=[(5,0,0)]))
    exam = base_exam.copy(dict(session_id=session.id,name='[Preview] Internal assessment window',exam_code='PP-IA-2026',start_time=datetime.combine(today+timedelta(days=7),datetime.min.time())+timedelta(hours=4),end_time=datetime.combine(today+timedelta(days=7),datetime.min.time())+timedelta(hours=7),state='draft',campus_year_id=year.id,attendees_line=[(5,0,0)],campus_result_ids=[(5,0,0)]))
exam.session_id.write({'campus_year_id': year.id})
if not exam.campus_schedule_published: exam.action_campus_release_schedule()

for index in range(5):
    source_admission=env['op.admission'].search([('company_id','=',1)],limit=1)
    app=env['op.admission'].search([('first_name','=','Preview Applicant '+str(index+1))],limit=1)
    if not app:
        app=source_admission.copy(dict(first_name='Preview Applicant '+str(index+1),last_name='Campus',student_id=False,campus_managed=True,image=False))
        app.action_campus_submit()

# Use real eligibility results and the normal placement approval workflow.
drive=env['campus.placement.drive'].search([('name','=','Preview placement drive')],limit=1)
if drive.state=='draft': drive.action_submit()
if drive.state=='submitted': drive.with_user(2).sudo().action_approve()
result_students=env['op.result.line'].search([('company_id','=',1),('status','=','pass')]).mapped('student_id')[:12]
for index,student in enumerate(result_students):
    candidate=ensure('campus.placement.candidate',[('drive_id','=',drive.id),('student_id','=',student.id)],dict(name='[Preview] Placement '+student.name,drive_id=drive.id,student_id=student.id))
    if candidate.eligible and index<8: candidate.write({'state':'selected'})
for student in students[-5:]:
    ensure('campus.placement.candidate',[('drive_id','=',drive.id),('student_id','=',student.id)],dict(name='[Preview] Placement '+student.name,drive_id=drive.id,student_id=student.id))

env.cr.commit()
print('Principal showcase records saved')
