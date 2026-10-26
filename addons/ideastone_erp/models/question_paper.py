import base64
import io

from PyPDF2 import PdfFileReader

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


LEVELS = [('balanced', 'Balanced'), ('moderate', 'Moderate'), ('advanced', 'Advanced')]
STATES = [('draft', 'Draft'), ('submitted', 'Awaiting HOD'), ('returned', 'Revision required'),
          ('approved', 'Approved'), ('forwarded', 'Forwarded to COE')]


class QuestionPaperRouting(models.Model):
    _name = 'campus.question.paper.routing'
    _description = 'Department question-paper reviewers'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    department_id = fields.Many2one('op.department', required=True, check_company=True)
    hod_id = fields.Many2one('res.users', required=True)
    coe_id = fields.Many2one('res.users', required=True, string='Exam control recipient')
    _sql_constraints = [('department_company', 'unique(company_id, department_id)', 'Configure one review route per department and college.')]

    @api.constrains('hod_id', 'coe_id', 'department_id', 'company_id')
    def _check_reviewers(self):
        for route in self:
            if (not route.hod_id.active or not route.coe_id.active
                    or not route.hod_id.has_group('ideastone_erp.group_exam_paper_hod')
                    or not route.coe_id.has_group('ideastone_erp.group_exam_paper_coe')
                    or route.hod_id.dept_id != route.department_id
                    or route.company_id not in route.hod_id.company_ids
                    or route.company_id not in route.coe_id.company_ids
                    or route.hod_id == route.coe_id):
                raise ValidationError(_('Choose an active department HOD and a separate authorized exam-control recipient in this college.'))


class QuestionPaper(models.Model):
    _name = 'campus.question.paper'
    _description = 'Confidential question-paper submission'
    _order = 'write_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, index=True)
    faculty_id = fields.Many2one('op.faculty', required=True, ondelete='restrict')
    department_id = fields.Many2one('op.department', required=True, ondelete='restrict')
    subject_id = fields.Many2one('op.subject', required=True, ondelete='restrict')
    exam_type = fields.Char(required=True)
    exam_date = fields.Date(required=True)
    paper_code = fields.Char(required=True)
    duration = fields.Selection([('3 hours', '3 hours'), ('2 hours', '2 hours'), ('90 minutes', '90 minutes'), ('1 hour', '1 hour')], default='3 hours', required=True)
    notes = fields.Text()
    state = fields.Selection(STATES, default='draft', required=True, index=True)
    hod_id = fields.Many2one('res.users', index=True)
    coe_id = fields.Many2one('res.users', index=True)
    set_ids = fields.One2many('campus.question.paper.set', 'paper_id')
    selected_set_id = fields.Many2one('campus.question.paper.set', ondelete='restrict')
    review_note = fields.Text()
    revision = fields.Integer(default=1)
    history = fields.Json(default=list)
    approved_at = fields.Datetime()
    forwarded_at = fields.Datetime()

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Use the question-paper submission workspace.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('Use the submission and review actions.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('Question-paper history must be retained.'))

    def _faculty(self):
        if not self.env.user.has_group('openeducat_core.group_op_faculty'):
            raise AccessError(_('A linked faculty account is required.'))
        faculty = self.env['op.faculty'].sudo().search([
            ('user_id', '=', self.env.uid), ('active', '=', True),
            ('company_id', 'in', [False, self.env.company.id])], limit=1)
        if not faculty:
            raise AccessError(_('Link this login to a faculty record in the active college.'))
        return faculty

    def _subjects(self, faculty):
        subjects = faculty.faculty_subject_ids | self.env['op.session'].sudo().search([
            ('faculty_id', '=', faculty.id), ('company_id', '=', self.env.company.id)]).subject_id
        return subjects.filtered(lambda s: s.company_id in (self.env.company, self.env['res.company']) and s.department_id)

    def _record(self, record_id, lock=False):
        if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id <= 0:
            raise ValidationError(_('Choose a valid submission.'))
        rec = self.search([('id', '=', record_id), ('company_id', '=', self.env.company.id)], limit=1)
        if not rec:
            raise AccessError(_('This submission is not assigned to your account.'))
        if lock:
            self.env.cr.execute('SELECT id FROM campus_question_paper WHERE id=%s FOR UPDATE', [rec.id])
            rec.invalidate_recordset()
        return rec

    def _event(self, action, note=''):
        self.ensure_one()
        event = {'action': action, 'by': self.env.user.name, 'at': fields.Datetime.to_string(fields.Datetime.now()),
                 'note': note, 'revision': self.revision}
        self.sudo().write({'history': (self.history or []) + [event]})
        self.env['campus.mvp.audit']._log(self, action, note, {'revision': self.revision, 'selected_set_id': self.selected_set_id.id})

    @api.model
    def save_submission(self, values, files=None, record_id=None, submit=False, levels=None):
        faculty = self._faculty()
        allowed = {'subject_id', 'department_id', 'exam_type', 'exam_date', 'paper_code', 'duration', 'notes'}
        if not isinstance(values, dict) or set(values) - allowed or not isinstance(submit, bool):
            raise ValidationError(_('Use the question-paper form fields.'))
        if any(isinstance(values.get(key), bool) or not isinstance(values.get(key), int) for key in ('subject_id', 'department_id')):
            raise ValidationError(_('Choose a department and subject from the form.'))
        subject = self._subjects(faculty).filtered(lambda s: s.id == values.get('subject_id'))
        if len(subject) != 1 or values.get('department_id') != subject.department_id.id:
            raise AccessError(_('Choose a subject and department assigned to your faculty account.'))
        vals = dict(values)
        try:
            due = fields.Date.to_date(vals.get('exam_date'))
        except (TypeError, ValueError) as exc:
            raise ValidationError(_('Enter a valid examination date.')) from exc
        if not due or not str(vals.get('exam_type', '')).strip() or not str(vals.get('paper_code', '')).strip():
            raise ValidationError(_('Enter the exam type, date and paper code before saving.'))
        if vals.get('duration') not in dict(self._fields['duration'].selection):
            raise ValidationError(_('Choose a valid examination duration.'))
        if any(not isinstance(vals.get(k, ''), str) or len(vals.get(k, '')) > limit
               for k, limit in [('notes', 4000), ('exam_type', 120), ('paper_code', 60)]):
            raise ValidationError(_('Keep the examination details and notes concise.'))
        rec = self._record(record_id, lock=True) if record_id else self.browse()
        if rec and (rec.faculty_id != faculty or rec.state not in ('draft', 'returned')):
            raise AccessError(_('Only your drafts and returned papers can be edited.'))
        if rec and rec.set_ids and rec.subject_id != subject:
            raise ValidationError(_('Start a new submission to change the subject after uploading sets.'))
        if submit and due < fields.Date.context_today(self):
            raise ValidationError(_('Submit papers for an upcoming examination.'))
        route = self.env['campus.question.paper.routing'].sudo().search([
            ('department_id', '=', subject.department_id.id), ('company_id', '=', self.env.company.id)], limit=1)
        if submit:
            if not route:
                raise ValidationError(_('Ask the administrator to configure the department HOD and exam-control route.'))
            route._check_reviewers()
            if route.hod_id == self.env.user or route.coe_id == self.env.user:
                raise ValidationError(_('The author, HOD and exam-control recipient must be separate people.'))
            vals.update(hod_id=route.hod_id.id, coe_id=route.coe_id.id)
        prepared = []
        files = files or []
        if not isinstance(files, list) or len(files) > 3:
            raise ValidationError(_('Upload at most one PDF for each difficulty set.'))
        seen = set()
        for item in files:
            if (not isinstance(item, dict) or set(item) != {'level', 'filename', 'content'}
                    or not isinstance(item['level'], str) or item['level'] not in dict(LEVELS) or item['level'] in seen):
                raise ValidationError(_('Choose a unique difficulty label for each PDF.'))
            seen.add(item['level'])
            filename, content = item['filename'], item['content']
            if not isinstance(filename, str) or not filename.lower().endswith('.pdf') or len(filename) > 200 or not isinstance(content, str) or len(content) > 28 * 1024 * 1024:
                raise ValidationError(_('Upload PDF files up to 20 MB each.'))
            try:
                raw = base64.b64decode(content, validate=True)
                if len(raw) > 20 * 1024 * 1024 or not raw.startswith(b'%PDF-'):
                    raise ValueError('Invalid PDF')
                reader = PdfFileReader(io.BytesIO(raw), strict=False)
                if reader.isEncrypted or not reader.getNumPages():
                    raise ValueError('Locked or empty PDF')
                pages = reader.getNumPages()
            except Exception as exc:
                raise ValidationError(_('Upload a readable, unencrypted PDF with at least one page.')) from exc
            prepared.append({'level': item['level'], 'filename': filename, 'content': content, 'page_count': pages})
        levels = levels if levels is not None else list({p['level'] for p in prepared} | set(rec.set_ids.mapped('level') if rec else []))
        if not isinstance(levels, list) or any(not isinstance(level, str) or level not in dict(LEVELS) for level in levels) or len(set(levels)) != len(levels):
            raise ValidationError(_('Choose valid difficulty sets.'))
        available = {p['level'] for p in prepared} | set(rec.set_ids.mapped('level') if rec else [])
        if any(p['level'] not in levels for p in prepared) or (submit and (not levels or set(levels) - available)):
            raise ValidationError(_('Attach at least one question-paper PDF before submitting.'))
        if rec:
            if rec.state == 'returned':
                vals.update(revision=rec.revision + 1, state='draft')
            rec.sudo().write(vals)
        else:
            rec = self.sudo().create(dict(vals, company_id=self.env.company.id, faculty_id=faculty.id)).with_user(self.env.user)
        rec.set_ids.filtered(lambda item: item.level not in levels).sudo().write({'active': False})
        for item in prepared:
            previous = rec.set_ids.filtered(lambda s: s.level == item['level'])
            previous.sudo().write({'active': False})
            self.env['campus.question.paper.set'].sudo().create(dict(item, paper_id=rec.id, revision=rec.revision))
        rec._event('Draft saved')
        if submit:
            rec.sudo().write({'state': 'submitted'})
            rec._event('Submitted to HOD')
        return rec.id

    @api.model
    def decide(self, record_id, decision, set_id=None, note=''):
        rec = self._record(record_id, lock=True)
        if (not self.env.user.has_group('ideastone_erp.group_exam_paper_hod') or rec.hod_id != self.env.user
                or rec.department_id != self.env.user.dept_id or rec.sudo().faculty_id.user_id == self.env.user):
            raise AccessError(_('Only this department submission’s assigned HOD can decide.'))
        if decision not in ('approve', 'return', 'forward') or not isinstance(note, str) or len(note) > 4000:
            raise ValidationError(_('Choose a valid review action and a concise note.'))
        if decision == 'forward':
            if (rec.state != 'approved' or not rec.selected_set_id or not rec.coe_id.active
                    or rec.company_id not in rec.coe_id.company_ids
                    or not rec.coe_id.has_group('ideastone_erp.group_exam_paper_coe')):
                raise ValidationError(_('Forward one approved paper to an active exam-control recipient.'))
            rec.sudo().write({'state': 'forwarded', 'forwarded_at': fields.Datetime.now()})
            rec._event('Forwarded to COE', note)
        else:
            if rec.state != 'submitted':
                raise ValidationError(_('This paper has already been reviewed. Refresh the queue.'))
            if decision == 'return':
                if not note.strip():
                    raise ValidationError(_('Give a reason for returning the paper.'))
                rec.sudo().write({'state': 'returned', 'review_note': note.strip()})
                rec._event('Returned for revision', note.strip())
            else:
                selected = rec.set_ids.filtered(lambda s: s.active and s.id == set_id)
                if len(selected) != 1:
                    raise ValidationError(_('Select one current PDF set belonging to this submission.'))
                rec.sudo().write({'state': 'approved', 'selected_set_id': selected.id, 'review_note': note.strip(), 'approved_at': fields.Datetime.now()})
                rec._event('Approved ' + dict(LEVELS)[selected.level] + ' set', note.strip())
        return rec.state

    @api.model
    def download_set(self, set_id):
        if isinstance(set_id, bool) or not isinstance(set_id, int):
            raise ValidationError(_('Choose a valid PDF set.'))
        item = self.env['campus.question.paper.set'].search([('id', '=', set_id)], limit=1)
        if not item:
            raise AccessError(_('This question paper is not available to your account.'))
        self._record(item.paper_id.id)
        if self.env.user == item.paper_id.coe_id and item != item.paper_id.selected_set_id:
            raise AccessError(_('Exam control receives only the selected official paper.'))
        return {'filename': item.filename, 'content': item.content.decode() if isinstance(item.content, bytes) else item.content}

    @api.model
    def get_workspace(self, role='faculty'):
        if role not in ('faculty', 'hod', 'coe'):
            raise AccessError(_('Choose your assigned workspace.'))
        if role == 'faculty':
            faculty = self._faculty()
            subjects = self._subjects(faculty)
            domain = [('faculty_id', '=', faculty.id)]
        else:
            if not self.env.user.has_group('ideastone_erp.group_exam_paper_' + role):
                raise AccessError(_('This reviewer workspace is not assigned to your login.'))
            subjects = self.env['op.subject']
            domain = [(role + '_id', '=', self.env.uid), ('state', 'in', ['approved', 'forwarded'])] if role == 'coe' else [
                ('hod_id', '=', self.env.uid), ('department_id', '=', self.env.user.dept_id.id), ('state', '!=', 'draft')]
        records = self.search(domain + [('company_id', '=', self.env.company.id)])
        rows = []
        for visible in records:
            # The submission rule was checked above; project only its linked labels.
            rec = visible.sudo()
            sets = rec.set_ids
            if role == 'coe':
                sets = sets & rec.selected_set_id
            rows.append({'id': rec.id, 'subject_id': rec.subject_id.id, 'subject': rec.subject_id.name,
                'department_id': rec.department_id.id, 'department': rec.department_id.name, 'department_code': rec.department_id.code,
                'staff': rec.faculty_id.name, 'exam_type': rec.exam_type, 'exam_date': str(rec.exam_date),
                'paper_code': rec.paper_code, 'duration': rec.duration, 'notes': rec.notes or '', 'revision': rec.revision,
                'state': rec.state, 'status': dict(STATES)[rec.state], 'updated': fields.Datetime.to_string(rec.write_date),
                'review_note': rec.review_note or '', 'history': rec.history or [], 'selected_set_id': rec.selected_set_id.id,
                'sets': [{'id': s.id, 'level': s.level, 'label': dict(LEVELS)[s.level], 'filename': s.filename, 'pages': s.page_count} for s in sets]})
        return {'role': role, 'company': self.env.company.name, 'user': self.env.user.name, 'rows': rows,
            'subjects': [{'id': s.id, 'name': s.name, 'code': s.code, 'department_id': s.department_id.id} for s in subjects],
            'departments': [{'id': d.id, 'name': d.name, 'code': d.code} for d in (subjects.department_id | records.department_id)],
            'counts': {'upcoming': len({r['subject_id'] for r in rows if r['exam_date'] >= str(fields.Date.context_today(self))}),
                **{state: sum(r['state'] == state for r in rows) for state, label in STATES}, 'received': len(rows)}}


class QuestionPaperSet(models.Model):
    _name = 'campus.question.paper.set'
    _description = 'Restricted question-paper PDF version'
    _order = 'id'

    paper_id = fields.Many2one('campus.question.paper', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='paper_id.company_id', store=True)
    active = fields.Boolean(default=True)
    level = fields.Selection(LEVELS, required=True)
    filename = fields.Char(required=True)
    content = fields.Binary(required=True, attachment=False)
    page_count = fields.Integer()
    revision = fields.Integer(required=True)
    is_official = fields.Boolean(compute='_compute_official', store=True)

    @api.depends('paper_id.selected_set_id')
    def _compute_official(self):
        for item in self:
            item.is_official = item.paper_id.selected_set_id == item

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Upload PDFs through the submission workspace.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('Submitted PDF versions are immutable.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('PDF version history must be retained.'))
