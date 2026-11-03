from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import SUPERUSER_ID, _, api, fields, models


def principal(env):
    if not env.user.has_group('ideastone_principal.group_principal'):
        raise AccessError(_('Principal access is required.'))


class Company(models.Model):
    _inherit = 'res.company'

    principal_leave_reviewer_id = fields.Many2one('res.users', string='Principal leave reviewer')


class StaffLeave(models.Model):
    _inherit = 'hr.leave'

    principal_reviewer_id = fields.Many2one('res.users', string='Principal reviewer', copy=False, index=True)
    principal_coverage = fields.Text(string='Staffing coverage plan')
    principal_recommendation = fields.Char(string='Department recommendation')

    @api.constrains('principal_reviewer_id', 'employee_id')
    def _check_principal_reviewer(self):
        for row in self:
            reviewer = row.principal_reviewer_id
            if reviewer and (not reviewer.has_group('ideastone_principal.group_principal') or row.employee_id.company_id not in reviewer.company_ids):
                raise ValidationError(_('The leave reviewer must be a Principal of this college.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee = self.env['hr.employee'].sudo().browse(vals.get('employee_id')).exists()
            reviewer = employee.company_id.principal_leave_reviewer_id
            if reviewer and not vals.get('principal_reviewer_id'):
                vals['principal_reviewer_id'] = reviewer.id
        return super().create(vals_list)


class StudentLeave(models.Model):
    _inherit = 'campus.student.leave'

    principal_leave_category = fields.Selection([
        ('medical', 'Medical'), ('personal', 'Personal'), ('on_duty', 'On duty'), ('family', 'Family'),
    ], default='medical')
    principal_supporting_details = fields.Text(string='Supporting details / academic continuity plan')

    def action_approve(self):
        if self.env.user.has_group('ideastone_principal.group_principal'):
            for row in self:
                if row.state == 'principal' and not (row.decision_reason or '').strip():
                    raise ValidationError(_('Enter a Principal decision remark before approving.'))
        return super().action_approve()


class DecisionLog(models.Model):
    _name = 'ideastone.principal.decision.log'
    _description = 'Principal decision evidence'
    _order = 'decided_on desc, id desc'

    company_id = fields.Many2one('res.company', required=True)
    source_model = fields.Char(required=True)
    source_id = fields.Integer(required=True)
    kind = fields.Char(required=True)
    subject = fields.Char(required=True)
    requester = fields.Char()
    outcome = fields.Selection([('approved', 'Approved'), ('rejected', 'Rejected'), ('changes', 'Needs changes')], required=True)
    remark = fields.Text(required=True)
    decided_by_id = fields.Many2one('res.users', required=True)
    decided_on = fields.Datetime(required=True, default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Decision evidence is created by the approval workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_('Decision evidence cannot be edited.'))

    def unlink(self):
        raise AccessError(_('Decision evidence cannot be deleted.'))


class EventProposal(models.Model):
    _name = 'ideastone.principal.event.proposal'
    _description = 'Campus event proposal and Principal signature'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start, id'

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    requester_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user, readonly=True)
    coordinator_id = fields.Many2one('res.users', required=True)
    principal_id = fields.Many2one('res.users', required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    venue = fields.Char(required=True)
    organizer = fields.Char(required=True)
    purpose = fields.Text(required=True)
    audience = fields.Char(default='All campus')
    attendees = fields.Integer(default=0)
    budget = fields.Monetary(default=0)
    currency_id = fields.Many2one(related='company_id.currency_id')
    funding = fields.Char()
    safety_plan = fields.Text()
    venue_checked = fields.Boolean(string='Venue and timetable checked')
    budget_checked = fields.Boolean(string='Budget and funding checked')
    safety_checked = fields.Boolean(string='Safety and logistics checked')
    recommendation = fields.Text(string='Coordinator recommendation')
    state = fields.Selection([('draft', 'Draft'), ('coordinator', 'Coordinator review'), ('review', 'Pending signature'),
                              ('changes', 'Needs changes'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                             default='draft', required=True, tracking=True)
    calendar_event_id = fields.Many2one('campus.calendar.event', readonly=True, copy=False)
    can_edit = fields.Boolean(compute='_compute_permissions')
    can_submit = fields.Boolean(compute='_compute_permissions')
    can_forward = fields.Boolean(compute='_compute_permissions')

    @api.depends('state', 'requester_id', 'coordinator_id')
    @api.depends_context('uid')
    def _compute_permissions(self):
        for row in self:
            row.can_submit = row.state in ('draft', 'changes') and row.requester_id == self.env.user
            row.can_forward = row.state == 'coordinator' and row.coordinator_id == self.env.user
            row.can_edit = row.can_submit or row.can_forward

    @api.constrains('date_start', 'date_end', 'budget', 'attendees', 'principal_id', 'coordinator_id', 'company_id')
    def _check_proposal(self):
        for row in self:
            if row.date_end < row.date_start or row.budget < 0 or row.attendees < 0:
                raise ValidationError(_('Use ordered event dates and non-negative budget and attendee values.'))
            if not row.principal_id.has_group('ideastone_principal.group_principal'):
                raise ValidationError(_('Assign a Principal account for final approval.'))
            if row.principal_id == row.coordinator_id:
                raise ValidationError(_('Coordinator and Principal must be different people.'))
            if any(row.company_id not in user.company_ids or not user.active or not user.has_group('base.group_user')
                   for user in row.principal_id | row.coordinator_id):
                raise ValidationError(_('Reviewers must be active internal users of this college.'))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                if vals.get('state', 'draft') != 'draft' or vals.get('calendar_event_id') or vals.get('requester_id', self.env.uid) != self.env.uid:
                    raise AccessError(_('Create your own draft proposal first.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if set(vals) & {'state', 'calendar_event_id', 'company_id', 'requester_id'}:
                raise AccessError(_('Use the event workflow controls to change approval status.'))
            for row in self:
                if row.state in ('draft', 'changes') and row.requester_id == self.env.user:
                    continue
                if row.state == 'coordinator' and row.coordinator_id == self.env.user:
                    continue
                raise AccessError(_('This submitted proposal is locked for review.'))
        return super().write(vals)

    def _lock(self):
        self.env.cr.execute('SELECT id FROM ideastone_principal_event_proposal WHERE id IN %s FOR UPDATE', [tuple(self.ids)])
        self.invalidate_recordset()

    def action_submit(self):
        self._lock()
        for row in self:
            if row.requester_id != self.env.user or row.state not in ('draft', 'changes'):
                raise AccessError(_('Only the organizer can submit a draft or revised proposal.'))
        return super().write({'state': 'coordinator'})

    def action_forward(self):
        self._lock()
        for row in self:
            if row.coordinator_id != self.env.user or row.state != 'coordinator':
                raise AccessError(_('Only the assigned coordinator can forward a proposal.'))
            if not row.recommendation:
                raise ValidationError(_('Record the coordinator recommendation before forwarding.'))
        return super().write({'state': 'review'})

    def unlink(self):
        if any(row.state != 'draft' for row in self):
            raise UserError(_('Submitted proposals retain their approval history.'))
        return super().unlink()


class PrincipalDecisions(models.AbstractModel):
    _name = 'ideastone.principal.decisions'
    _description = 'Principal decisions workspace'

    def _sources(self):
        principal(self.env)
        company = self.env.company.id
        return {
            'staff': self.env['hr.leave'].sudo().search([('employee_id.company_id', '=', company),
                      ('principal_reviewer_id', '=', self.env.uid), ('state', 'in', ['confirm', 'validate1', 'validate', 'refuse'])], order='create_date desc'),
            'student': self.env['campus.student.leave'].sudo().search([('company_id', '=', company),
                        ('principal_id', '=', self.env.uid), ('state', 'in', ['principal', 'approved', 'rejected'])], order='create_date desc'),
            'request': self.env['ideastone.principal.request'].search([('company_id', '=', company), ('state', '!=', 'draft')]),
            'event': self.env['ideastone.principal.event.proposal'].sudo().search([('company_id', '=', company),
                       ('principal_id', '=', self.env.uid), ('state', 'in', ['review', 'changes', 'approved', 'rejected'])]),
        }

    def _staff_pending(self, row):
        return row.state == 'validate1' or (row.state == 'confirm' and row.validation_type != 'both')

    def _balance(self, row):
        if row.holiday_status_id.requires_allocation == 'no':
            return None
        data = row.holiday_status_id.get_allocation_data(row.employee_id, fields.Date.context_today(self)).get(row.employee_id, [])
        return round(data[0][1]['virtual_remaining_leaves'], 2) if data else 0

    @api.model
    def get_data(self):
        sources = self._sources()
        today = fields.Date.context_today(self)
        def text_date(value):
            return str(value or '')
        rows = []
        for row in sources['staff']:
            if row.state == 'confirm' and row.validation_type == 'both':
                continue
            rows.append({'id': row.id, 'key': f'staff-{row.id}', 'kind': 'staff', 'category': 'Staff leave',
                         'name': row.employee_id.name, 'code': row.employee_id.barcode or f'EMP-{row.employee_id.id:03}',
                         'department': row.employee_id.department_id.name or 'Unassigned department',
                         'designation': row.employee_id.job_title or '', 'type': row.holiday_status_id.name,
                         'from': text_date(row.request_date_from), 'to': text_date(row.request_date_to),
                         'days': row.number_of_days, 'balance': self._balance(row),
                         'recommendation': row.principal_recommendation or ('HoD recommended' if row.state == 'validate1' else 'Department review complete'),
                         'coverage': row.principal_coverage or 'Coverage plan not recorded',
                         'reason': row.private_name or row.name or '', 'details': '',
                         'subject': f'{row.holiday_status_id.name} · {row.number_of_days:g} day(s)',
                         'submitted': text_date(row.create_date.date()),
                         'status': 'pending' if self._staff_pending(row) else 'approved' if row.state == 'validate' else 'rejected'})
        for row in sources['student']:
            if row.state == 'rejected' and 'principal -> rejected' not in (row.decision_log or ''):
                continue
            days = (row.deadline - row.date).days + 1 if row.date and row.deadline else 0
            rows.append({'id': row.id, 'key': f'student-{row.id}', 'kind': 'student', 'category': 'Student leave',
                         'name': row.student_id.name, 'code': row.student_id.gr_no or f'STU-{row.student_id.id:03}',
                         'department': ', '.join(row.student_id.course_detail_ids.mapped('course_id.name')) or '',
                         'type': dict(row._fields['principal_leave_category'].selection).get(row.principal_leave_category, 'Medical'),
                         'from': text_date(row.date), 'to': text_date(row.deadline), 'days': days,
                         'reason': row.reason, 'details': row.principal_supporting_details or '',
                         'advisor': row.advisor_id.name, 'hod': row.hod_id.name, 'subject': row.name,
                         'submitted': text_date(row.create_date.date()),
                         'status': 'pending' if row.state == 'principal' else row.state})
        labels = {'admission': 'Admissions', 'academic': 'Academic matters', 'discipline': 'Student affairs',
                  'finance': 'Finance & facilities', 'facility': 'Finance & facilities', 'leave': 'Staff administration', 'other': 'Staff administration'}
        for row in sources['request']:
            rows.append({'id': row.id, 'key': f'request-{row.id}', 'kind': 'request', 'category': labels.get(row.request_type, 'Staff administration'),
                         'name': row.requester_id.name, 'subject': row.name, 'type': dict(row._fields['request_type'].selection)[row.request_type],
                         'reason': row.description, 'details': row.decision_note or '', 'submitted': text_date(row.due_date or row.create_date.date()),
                         'status': 'pending' if row.state == 'submitted' else row.state})
        for row in sources['event']:
            rows.append({'id': row.id, 'key': f'event-{row.id}', 'kind': 'event', 'category': 'Event management',
                         'name': row.organizer, 'subject': row.name, 'code': f'EVT-{row.id:03}',
                         'from': text_date(row.date_start), 'to': text_date(row.date_end), 'venue': row.venue,
                         'budget': row.budget, 'currency': row.currency_id.symbol, 'attendees': row.attendees,
                         'reason': row.purpose, 'details': row.recommendation or '', 'funding': row.funding or '',
                         'safety': row.safety_plan or '', 'checks': all([row.venue_checked, row.budget_checked, row.safety_checked]),
                         'readiness': ', '.join(label for flag, label in [(row.venue_checked, 'Venue'), (row.budget_checked, 'Budget'),
                                      (row.safety_checked, 'Safety')] if not flag) + ' review pending' if not all([row.venue_checked, row.budget_checked, row.safety_checked]) else 'Ready for Principal review',
                         'submitted': text_date(row.create_date.date()),
                         'status': 'pending' if row.state == 'review' else row.state})
        history = self.env['ideastone.principal.decision.log'].search([
            ('company_id', '=', self.env.company.id), ('decided_by_id', '=', self.env.uid)], limit=100)
        approved_month = {kind: self.env['ideastone.principal.decision.log'].search_count([
            ('company_id', '=', self.env.company.id), ('decided_by_id', '=', self.env.uid),
            ('kind', '=', kind), ('outcome', '=', 'approved'), ('decided_on', '>=', today.replace(day=1)),
        ]) for kind in ('staff', 'student')}
        for item in rows:
            source_model = {'staff': 'hr.leave', 'student': 'campus.student.leave', 'event': 'ideastone.principal.event.proposal',
                            'request': 'ideastone.principal.request'}[item['kind']]
            files = self.env['ir.attachment'].sudo().search([('res_model', '=', source_model), ('res_id', '=', item['id']), ('type', '=', 'binary')])
            item['attachments'] = [{'id': file.id, 'name': file.name, 'url': f'/web/content/{file.id}?download=true'} for file in files]
        overview = self.env['ideastone.principal.dashboard'].get_overview()
        return {'today': str(today), 'rows': rows, 'company': self.env.company.name,
                'user': self.env.user.name, 'upcoming_end': str(today + timedelta(days=60)),
                'counts': overview['counts'], 'notices': overview['notices'], 'approved_month': approved_month,
                'history': [{'id': row.id, 'kind': row.kind, 'name': row.requester, 'subject': row.subject,
                             'outcome': row.outcome, 'remark': row.remark, 'actor': row.decided_by_id.name,
                             'source_id': row.source_id, 'at': str(row.decided_on)} for row in history]}

    @api.model
    def decide(self, kind, record_id, outcome, remark):
        principal(self.env)
        if kind not in ('staff', 'student', 'event', 'request') or type(record_id) is not int:
            raise ValidationError(_('Choose a valid decision record.'))
        if outcome not in ('approved', 'rejected', 'changes') or (outcome == 'changes' and kind != 'event'):
            raise ValidationError(_('Choose a valid decision outcome.'))
        if not isinstance(remark, str) or not remark.strip() or len(remark) > 5000:
            raise ValidationError(_('Enter a decision remark of 1–5,000 characters.'))
        models_by_kind = {'staff': 'hr.leave', 'student': 'campus.student.leave',
                          'event': 'ideastone.principal.event.proposal', 'request': 'ideastone.principal.request'}
        row = self.env[models_by_kind[kind]].sudo().browse(record_id).exists()
        if not row:
            raise AccessError(_('This decision record is unavailable.'))
        self.env.cr.execute(f'SELECT id FROM {row._table} WHERE id = %s FOR UPDATE', [record_id])
        row.invalidate_recordset()
        company = row.employee_id.company_id if kind == 'staff' else row.company_id
        reviewer = row.principal_reviewer_id if kind == 'staff' else row.principal_id if kind in ('student', 'event') else self.env.user
        if company != self.env.company or reviewer != self.env.user:
            raise AccessError(_('Only the assigned Principal of this college may decide this record.'))
        if kind == 'staff' and row.employee_id.user_id == self.env.user:
            raise AccessError(_('Another assigned Principal must review your own leave.'))
        pending = self._staff_pending(row) if kind == 'staff' else row.state == {'student': 'principal', 'event': 'review', 'request': 'submitted'}[kind]
        if not pending:
            raise UserError(_('This record has already changed. Refresh the workspace before deciding.'))
        remark = remark.strip()
        subject = row.employee_id.name + ' · ' + row.holiday_status_id.name if kind == 'staff' else row.name
        requester = row.employee_id.name if kind == 'staff' else row.student_id.name if kind == 'student' else row.requester_id.name
        if kind == 'staff':
            # Native HR requires an HR officer even under sudo. Elevate only after the
            # college, assigned reviewer, final stage and self-approval checks above.
            native = row.with_user(SUPERUSER_ID)
            native.action_validate() if outcome == 'approved' else native.action_refuse()
        elif kind == 'student':
            row.write({'decision_reason': remark})
            row.action_approve() if outcome == 'approved' else row.action_reject()
        elif kind == 'request':
            row.write({'decision_note': remark})
            row.action_approve() if outcome == 'approved' else row.action_reject()
        else:
            if outcome == 'approved':
                if not all([row.venue_checked, row.budget_checked, row.safety_checked]):
                    raise ValidationError(_('Complete venue, budget and safety checks before signing.'))
                if not row.calendar_event_id:
                    event = self.env['campus.calendar.event'].sudo().create({
                        'name': row.name, 'company_id': row.company_id.id, 'date_start': row.date_start,
                        'date_end': row.date_end, 'venue': row.venue, 'organizer': row.organizer,
                        'audience': row.audience, 'description': row.purpose, 'status': 'upcoming',
                    })
                    row.write({'calendar_event_id': event.id})
            row.write({'state': outcome})
        self.env['ideastone.principal.decision.log'].sudo().create({
            'company_id': self.env.company.id, 'source_model': row._name, 'source_id': row.id,
            'kind': kind, 'subject': subject, 'requester': requester, 'outcome': outcome,
            'remark': remark, 'decided_by_id': self.env.uid,
        })
        row.message_post(body=_('Principal decision: %(outcome)s. %(remark)s', outcome=outcome, remark=remark), subtype_xmlid='mail.mt_note')
        return {'id': row.id, 'status': outcome}

    @api.model
    def related_action(self, key):
        principal(self.env)
        refs = {'admissions': 'ideastone_erp.action_admissions_overview', 'students': 'ideastone_erp.action_students_directory',
                'exams': 'ideastone_erp.action_examinations_overview', 'staff': 'ideastone_erp.action_owner_staff_directory',
                'attendance': 'ideastone_erp.action_faculty_attendance_page', 'calendar': 'ideastone_erp.action_college_calendar',
                'proposal': 'ideastone_principal.action_principal_event_proposals'}
        if key not in refs:
            raise ValidationError(_('Unknown related workspace.'))
        if key == 'attendance':
            return {'type': 'ir.actions.act_window', 'name': _('Staff attendance'), 'res_model': 'hr.attendance',
                    'views': [[False, 'tree'], [False, 'form']],
                    'domain': [('employee_id.company_id', '=', self.env.company.id)],
                    'context': dict(self.env.context, create=False, edit=False, delete=False, campus_module='attendance')}
        action = self.env.ref(refs[key]).sudo().read()[0]
        action['context'] = dict(self.env.context, campus_workspace_role='Principal',
                                 campus_module='decisions' if key == 'proposal' else key)
        return action
