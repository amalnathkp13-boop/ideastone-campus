"""Run in odoo shell against the isolated Principal notices preview only."""
from datetime import datetime, time, timedelta
from odoo import fields

assert env.cr.dbname == 'principal_notices_preview'
publication_cron = env.ref('ideastone_principal.cron_notice_publication')
env['ir.cron'].search([('id', '!=', publication_cron.id)]).write({'active': False})
publication_cron.write({'active': True})
principal = env['res.users'].search([('login','=','principal@campus.local')],limit=1)
model = env['ideastone.principal.notice'].with_user(principal).with_company(env['res.company'].browse(1))
today = fields.Date.context_today(model.with_context(tz='Asia/Kolkata'))

def notice(title, ref, audience, office, text, state, days=0, expiry=None):
    row = model.search([('reference','=',ref)],limit=1)
    if row:
        if state == 'scheduled' and row.state == 'scheduled':
            row._set_workflow({'publish_at': datetime.combine(today+timedelta(days=days),time(3,30)),
                               'expires_at': datetime.combine(today+timedelta(days=expiry),time(18,0))})
        return row
    vals = dict(name=title,audience=audience,office=office,body='<p>'+text+'</p>',company_id=1)
    if days: vals['publish_at'] = datetime.combine(today+timedelta(days=days),time(3,30))
    if expiry: vals['expires_at'] = datetime.combine(today+timedelta(days=expiry),time(18,0))
    row = model.create(vals)
    row._set_workflow({'reference':ref})
    if state in ('published','scheduled'): row.action_publish()
    elif state == 'pending': row.action_submit()
    return row

for i in range(12):
    notice(['Internal quality review meeting','Campus safety and access guidelines','Academic calendar update','Student club registration','Research seminar invitations','Semester course registration','Hostel visitor guidelines','Library borrowing policy','Placement readiness workshop','Sports trials circular','Department review schedule','Mentor meeting calendar'][i], 'PUB/2026/%03d'%(i+1), ['staff','all','students'][i%3], ['IQAC','Campus Administration','Student Affairs'][i%3], 'Meeting agenda, important dates and participation instructions for campus coordinators. Please review the published guidance and contact the responsible office for clarification.', 'published',expiry=3 if i<3 else 30)
for i,(title,audience,days) in enumerate([
    ('Library extended hours during exams','students',3),('Semester exam timetable release','all',5),('Scholarship deadline reminder','students',7),('Industry interaction series','staff',9),('Community service orientation','students',11),('Research proposal submission window','staff',14),
]):
    notice(title,'SCHD/2026/%03d'%(i+1),audience,'Campus Administration','Approved notice with publication and expiry dates aligned to the event calendar.','scheduled',days=days,expiry=days+10)
for title,ref,audience,office,summary in reversed([
    ('End-semester examination instructions','EXM/2026/118','students','Controller of Examinations','Instructions covering hall tickets, reporting time, permitted materials and examination conduct.'),
    ('Campus cultural fest – event circular','EVT/2026/064','all','Student Affairs','Event schedule, participation guidance and venue details for the upcoming cultural fest.'),
    ('Faculty development programme','HR/2026/042','staff','Faculty Development Cell','Proposed FDP announcement with registration deadline and session outline.'),
    ('Scholarship application deadline reminder','SCH/2026/031','students','Student Welfare Office','Reminder about required documents and final submission date for eligible students.'),
]):
    notice(title,ref,audience,office,summary,'pending',expiry=14)
env['ir.attachment'].search([('url','=like','/web/assets/%')]).unlink()
env.cr.commit()
print('Principal notice sample counts:',model.get_workspace()['counts'])
print('Action:',env.ref('ideastone_principal.action_principal_notices_workspace').id)
