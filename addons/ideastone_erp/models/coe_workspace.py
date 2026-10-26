from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


COE_MODULES = [
    ('coe-home', 'COE overview', 'home', [('overview', 'Overview'), ('attention', 'Action queue')]),
    ('coe-exams', 'Examination records', 'calendar', [('records', 'All examinations'), ('upcoming', 'Upcoming'), ('recent', 'Recent'), ('past', 'Past records'), ('timetable', 'Timetable')]),
    ('coe-papers', 'Question papers', 'file-text-o', [('papers', 'Approved paper inbox'), ('received', 'Received papers'), ('dispatch', 'Dispatch register')]),
    ('coe-operations', 'Exam operations', 'building-o', [('halls', 'Hall allocations'), ('invigilation', 'Invigilation'), ('attendance', 'Attendance & incidents')]),
    ('coe-results', 'Evaluation & results', 'graduation-cap', [('evaluation', 'Evaluation tracker'), ('results', 'Results register'), ('cases', 'Revaluation & corrections')]),
    ('coe-reports', 'Reports & audit', 'bar-chart', [('departments', 'Department summary'), ('year-summary', 'Years I–IV'), ('audit', 'Workflow audit')]),
    ('coe-setup', 'Academic setup', 'cog', [('years', 'Academic years'), ('routes', 'Departments & HOD routes')]),
]
COE_VIEWS = {key: (module, label) for module, _, _, items in COE_MODULES for key, label in items}


class COENavigation(models.AbstractModel):
    _inherit = 'campus.dashboard'

    @api.model
    def get_overview(self):
        if not self.env.user.has_group('ideastone_erp.group_coe_admin'):
            return super().get_overview()
        modules = []
        for key, label, icon, views in COE_MODULES:
            items = [{'label': title, 'action': 'ideastone_erp.action_coe_' + view,
                      'action_id': self.env.ref('ideastone_erp.action_coe_' + view).id, 'allowed': True}
                     for view, title in views]
            modules.append({'key': key, 'label': label, 'icon': icon, 'items': items})
        return {'company': self.env.company.name, 'user': self.env.user.name, 'today': str(fields.Date.context_today(self)),
                'workspace_role': 'Controller of Examinations', 'is_coe_workspace': True,
                'is_admin': False, 'is_hod': False, 'is_owner_workspace': False, 'faculty_modules': modules,
                'navigation': [item for module in modules for item in module['items']], 'pages': [], 'stats': [],
                'queues': [], 'quick': [], 'appointments': [], 'library_allowed': False}


class COEExam(models.Model):
    _inherit = 'op.exam'

    coe_study_year = fields.Selection([(str(n), 'Year ' + str(n)) for n in range(1, 5)], default='1', required=True)
    coe_hall = fields.Char(string='Hall allocation')
    coe_invigilator = fields.Char(string='Invigilator / chief superintendent')
    coe_expected = fields.Integer(string='Expected candidates')
    coe_present = fields.Integer(string='Present candidates')
    coe_evaluation_due = fields.Date(string='Evaluation deadline')
    coe_paper_id = fields.Many2one('campus.question.paper', string='Official question paper', ondelete='restrict')

    @api.constrains('coe_expected', 'coe_present', 'coe_paper_id', 'company_id', 'subject_id')
    def _check_coe_operations(self):
        for exam in self:
            if not 0 <= exam.coe_present <= exam.coe_expected:
                raise ValidationError(_('Present candidates must be between zero and the expected count.'))
            paper = exam.coe_paper_id
            if paper and (paper.company_id != exam.company_id or paper.subject_id != exam.subject_id
                          or paper.department_id != exam.course_id.department_id):
                raise ValidationError(_('Link a question paper for this subject, department and college.'))


class COEPaper(models.Model):
    _inherit = 'campus.question.paper'

    coe_received_at = fields.Datetime(readonly=True, copy=False)
    coe_received_by = fields.Many2one('res.users', readonly=True, copy=False)
    coe_dispatched_at = fields.Datetime(readonly=True, copy=False)
    coe_dispatch_note = fields.Text(readonly=True, copy=False)


class COECase(models.Model):
    _name = 'campus.coe.case'
    _description = 'Examination cell case register'
    _order = 'create_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company, index=True)
    exam_id = fields.Many2one('op.exam', required=True, ondelete='restrict')
    name = fields.Char(required=True)
    kind = fields.Selection([('revaluation', 'Revaluation'), ('correction', 'Result correction'), ('incident', 'Examination incident')], required=True)
    reference = fields.Char(string='Student / case reference')
    note = fields.Text(required=True)
    state = fields.Selection([('open', 'Open'), ('review', 'Under review'), ('resolved', 'Resolved')], default='open', required=True)

    @api.constrains('exam_id', 'company_id')
    def _check_college(self):
        for case in self:
            if case.exam_id.company_id != case.company_id:
                raise ValidationError(_('The case and examination must belong to the same college.'))


class COEWorkspace(models.AbstractModel):
    _name = 'campus.coe.workspace'
    _description = 'Controller of Examinations workspace'

    def _check(self):
        if not self.env.user.has_group('ideastone_erp.group_coe_admin'):
            raise AccessError(_('This workspace requires an appointed COE administrator.'))

    def _id(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit() or not 0 < int(value) < 2147483648:
            raise ValidationError(_('Choose a valid record.'))
        return int(value)

    def _exam(self, record_id):
        exam = self.env['op.exam'].search([('id', '=', self._id(record_id)), ('company_id', '=', self.env.company.id)])
        if not exam:
            raise AccessError(_('This examination is outside the active college.'))
        return exam

    @api.model
    def get_workspace(self, view='overview', filters=None):
        self._check()
        if not isinstance(view, str) or view not in COE_VIEWS or filters is not None and not isinstance(filters, dict):
            raise ValidationError(_('Choose a valid COE workspace.'))
        filters = filters or {}
        today = fields.Date.context_today(self)
        company = [('company_id', '=', self.env.company.id)]
        years = self.env['op.academic.year'].search(company, order='start_date desc, id desc')
        departments = self.env['op.department'].search(company, order='name')
        selected = self._id(filters['year_id']) if filters.get('year_id') else (years.filtered(lambda y: y.start_date <= today <= y.end_date)[:1] or years[:1]).id
        year = years.filtered(lambda y: y.id == selected)
        if not year:
            raise AccessError(_('Choose an academic year in the active college.'))
        department_id = self._id(filters['department_id']) if filters.get('department_id') else 0
        if department_id and department_id not in departments.ids:
            raise AccessError(_('Choose a department in the active college.'))
        study = filters.get('study_year', '')
        if not isinstance(study, str) or study not in ('', '1', '2', '3', '4'):
            raise ValidationError(_('Choose Year I, II, III or IV.'))
        domain = company + [('campus_year_id', '=', year.id)]
        if department_id:
            domain += [('course_id.department_id', '=', department_id)]
        if study:
            domain += [('coe_study_year', '=', study)]
        exams = self.env['op.exam'].search(domain, order='start_time desc, id desc')
        now = fields.Datetime.now()
        rows = []
        for exam in exams:
            lines = exam.campus_result_ids
            entered = len(lines.filtered('campus_entered'))
            period = 'upcoming' if exam.start_time > now else 'recent' if exam.end_time >= now - timedelta(days=30) else 'past'
            rows.append({'id': exam.id, 'name': exam.name, 'code': exam.exam_code, 'subject': exam.subject_id.name,
                'subject_id': exam.subject_id.id, 'session': exam.session_id.name, 'department': exam.course_id.department_id.name or 'Unassigned',
                'department_id': exam.course_id.department_id.id, 'study_year': exam.coe_study_year,
                'start': fields.Datetime.to_string(exam.start_time), 'end': fields.Datetime.to_string(exam.end_time),
                'period': period, 'status': dict(exam._fields['campus_state'].selection)[exam.campus_state], 'state': exam.campus_state,
                'hall': exam.coe_hall or '', 'invigilator': exam.coe_invigilator or '', 'expected': exam.coe_expected,
                'present': exam.coe_present, 'evaluation_due': str(exam.coe_evaluation_due or ''), 'entered': entered,
                'roster': len(lines), 'passed': len(lines.filtered(lambda line: line.campus_entered and line.status == 'pass')),
                'paper_id': exam.coe_paper_id.id, 'notes': exam.note or ''})
        papers = self.env['campus.question.paper'].get_workspace('coe')['rows']
        paper_records = self.env['campus.question.paper'].browse([r['id'] for r in papers])
        links = self.env['op.exam'].search(company + [('coe_paper_id', 'in', paper_records.ids)])
        for row in papers:
            rec = paper_records.browse(row['id'])
            linked = links.filtered(lambda e: e.coe_paper_id == rec)[:1]
            row.update(received_at=fields.Datetime.to_string(rec.coe_received_at) if rec.coe_received_at else '',
                       dispatched_at=fields.Datetime.to_string(rec.coe_dispatched_at) if rec.coe_dispatched_at else '',
                       dispatch_note=rec.coe_dispatch_note or '', exam_id=linked.id, study_year=linked.coe_study_year or '',
                       hod=rec.sudo().hod_id.name, approved_at=fields.Datetime.to_string(rec.approved_at) if rec.approved_at else '')
        papers = [r for r in papers if year.start_date <= fields.Date.to_date(r['exam_date']) <= year.end_date
                  and (not department_id or r['department_id'] == department_id)
                  and (not study or r['study_year'] == study)]
        cases = self.env['campus.coe.case'].search(company + [('exam_id', 'in', exams.ids)])
        case_rows = [{'id': c.id, 'exam_id': c.exam_id.id, 'name': c.name, 'exam': c.exam_id.name, 'reference': c.reference or '',
                      'kind': c.kind, 'state': c.state, 'note': c.note, 'department': c.exam_id.course_id.department_id.name} for c in cases]
        summaries = []
        for dept in departments:
            subset = [r for r in rows if r['department_id'] == dept.id]
            if department_id and dept.id != department_id:
                continue
            summaries.append({'id': dept.id, 'name': dept.name, 'code': dept.code or '', 'total': len(subset),
                'upcoming': sum(r['period'] == 'upcoming' for r in subset),
                'years': [sum(r['study_year'] == str(n) for r in subset) for n in range(1, 5)],
                'papers': sum(r['department_id'] == dept.id for r in papers)})
        routes = self.env['campus.question.paper.routing'].sudo().search(company)
        audit = self.env['campus.mvp.audit'].sudo().search(company + [
            ('model_name', 'in', ['op.exam', 'campus.question.paper', 'campus.coe.case']),
            ('create_date', '>=', str(year.start_date)), ('create_date', '<', str(year.end_date + timedelta(days=1)))], limit=80)
        audit = audit.filtered(lambda a: a.record_id in (exams.ids if a.model_name == 'op.exam' else [r['id'] for r in papers] if a.model_name == 'campus.question.paper' else cases.ids))
        return {'view': view, 'title': COE_VIEWS[view][1], 'company': self.env.company.name, 'today': str(today),
            'year_id': year.id, 'year': year.name, 'years': [{'id': y.id, 'name': y.name, 'start': str(y.start_date), 'end': str(y.end_date)} for y in years],
            'departments': [{'id': d.id, 'name': d.name, 'code': d.code or ''} for d in departments], 'exams': rows, 'papers': papers,
            'cases': case_rows, 'summaries': summaries,
            'routes': [{'id': d.id, 'department': d.name, 'hod': routes.filtered(lambda r: r.department_id == d)[:1].hod_id.name or 'Not configured',
                        'coe': routes.filtered(lambda r: r.department_id == d)[:1].coe_id.name or 'Not configured'}
                       for d in departments if not department_id or d.id == department_id],
            'audit': [{'id': a.id, 'action': a.name, 'actor': a.actor_id.name, 'at': fields.Datetime.to_string(a.create_date), 'reason': a.reason or ''} for a in audit],
            'counts': {'exams': len(rows), 'upcoming': sum(r['period'] == 'upcoming' for r in rows), 'papers': len(papers),
                       'unreceived': sum(not r['received_at'] and r['state'] == 'forwarded' for r in papers),
                       'cases': len(cases.filtered(lambda c: c.state != 'resolved')),
                       'readiness': sum(r['period'] == 'upcoming' and (not r['hall'] or not r['invigilator']) for r in rows)}}

    @api.model
    def save_operations(self, record_id, values):
        self._check()
        exam = self._exam(record_id)
        allowed = {'coe_hall', 'coe_invigilator', 'coe_expected', 'coe_present', 'coe_evaluation_due', 'coe_study_year', 'note'}
        if not isinstance(values, dict) or set(values) - allowed:
            raise ValidationError(_('Use the examination operations fields.'))
        for key in ('coe_hall', 'coe_invigilator', 'note'):
            if key in values and (not isinstance(values[key], str) or len(values[key]) > 2000):
                raise ValidationError(_('Keep the examination notes concise.'))
        for key in ('coe_expected', 'coe_present'):
            if key in values and (isinstance(values[key], bool) or not isinstance(values[key], int) or not 0 <= values[key] <= 10000):
                raise ValidationError(_('Enter a candidate count from 0 to 10,000.'))
        exam._mvp_lock()
        exam.write(values)
        exam._mvp_log('COE examination operations updated', details=values)
        return exam.id

    @api.model
    def paper_action(self, record_id, action, note='', exam_id=None):
        self._check()
        paper = self.env['campus.question.paper']._record(self._id(record_id), lock=True)
        if paper.coe_id != self.env.user or paper.state != 'forwarded' or not paper.selected_set_id:
            raise AccessError(_('The assigned HOD must forward the selected official set before receipt or dispatch.'))
        if not isinstance(note, str) or len(note) > 2000:
            raise ValidationError(_('Enter a concise dispatch reference.'))
        if action == 'receive':
            if paper.coe_received_at:
                raise ValidationError(_('Receipt has already been recorded.'))
            paper.sudo().write({'coe_received_at': fields.Datetime.now(), 'coe_received_by': self.env.uid})
            paper._event('COE receipt acknowledged')
        elif action == 'dispatch':
            if not paper.coe_received_at or paper.coe_dispatched_at or not note.strip():
                raise ValidationError(_('Acknowledge receipt first, then enter a new dispatch reference.'))
            exam = self._exam(exam_id)
            if not exam.coe_hall or not exam.coe_invigilator or exam.start_time < fields.Datetime.now():
                raise ValidationError(_('Choose an upcoming examination with a hall and invigilator assigned.'))
            exam._mvp_lock()
            if fields.Datetime.context_timestamp(exam, exam.start_time).date() != paper.exam_date:
                raise ValidationError(_('The examination date must match the approved question paper.'))
            if exam.coe_paper_id and exam.coe_paper_id != paper:
                raise ValidationError(_('This examination already has an official question paper.'))
            exam.write({'coe_paper_id': paper.id})
            paper.sudo().write({'coe_dispatched_at': fields.Datetime.now(), 'coe_dispatch_note': note.strip()})
            paper._event('COE official paper dispatched', note.strip())
        else:
            raise ValidationError(_('Choose receipt or dispatch.'))
        return True

    @api.model
    def save_case(self, values, record_id=None):
        self._check()
        if not isinstance(values, dict) or set(values) - {'exam_id', 'name', 'kind', 'reference', 'note', 'state'}:
            raise ValidationError(_('Use the examination case form.'))
        for key in ('name', 'reference', 'note'):
            if key in values and (not isinstance(values[key], str) or len(values[key]) > 4000):
                raise ValidationError(_('Enter concise case details.'))
        if 'exam_id' in values:
            self._exam(values['exam_id'])
        if record_id:
            case = self.env['campus.coe.case'].search([('id', '=', self._id(record_id)), ('company_id', '=', self.env.company.id)])
            if not case:
                raise AccessError(_('This case is outside the active college.'))
            case.write(values)
        else:
            case = self.env['campus.coe.case'].create(dict(values, company_id=self.env.company.id))
        self.env['campus.mvp.audit']._log(case, 'COE case updated', case.note, {'state': case.state})
        return case.id

    @api.model
    def exam_action(self, record_id=None):
        self._check()
        exam = self._exam(record_id) if record_id is not None else self.env['op.exam']
        return {'type': 'ir.actions.act_window', 'name': exam.name or _('Create examination'), 'res_model': 'op.exam',
                'res_id': exam.id, 'views': [(self.env.ref('ideastone_erp.mvp_exams_form').id, 'form')], 'target': 'current',
                'context': {'campus_module': 'coe-exams', 'default_campus_managed': True}}
