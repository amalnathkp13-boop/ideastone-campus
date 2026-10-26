import base64
import io
from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from PyPDF2 import PdfFileWriter

from odoo import fields


@tagged('post_install', '-at_install')
class TestQuestionPapers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_notrack=True))
        cls.dept = cls.env['op.department'].create({'name': 'Paper QA ECE', 'code': 'QPQA'})
        cls.subject = cls.env['op.subject'].create({'name': 'Paper QA subject', 'code': 'QPQA', 'department_id': cls.dept.id})
        cls.teacher = new_test_user(cls.env, login='qp.teacher.qa', groups='openeducat_core.group_op_faculty')
        cls.other = new_test_user(cls.env, login='qp.other.qa', groups='openeducat_core.group_op_faculty')
        cls.hod = new_test_user(cls.env, login='qp.hod.qa', groups='ideastone_erp.group_exam_paper_hod', dept_id=cls.dept.id)
        cls.coe = new_test_user(cls.env, login='qp.coe.qa', groups='ideastone_erp.group_exam_paper_coe')
        for user in (cls.teacher, cls.other):
            cls.env['op.faculty'].create({'first_name': user.name, 'last_name': 'QA', 'gender': 'male', 'birth_date': '1990-01-01',
                'partner_id': cls.env['res.partner'].create({'name': user.name, 'user_id': user.id, 'company_id': cls.env.company.id}).id,
                'main_department_id': cls.dept.id, 'faculty_subject_ids': [(6, 0, cls.subject.ids)]})
        cls.env['campus.question.paper.routing'].create({'department_id': cls.dept.id, 'hod_id': cls.hod.id, 'coe_id': cls.coe.id})
        cls.values = {'subject_id': cls.subject.id, 'department_id': cls.dept.id, 'exam_type': 'CAT II',
            'exam_date': str(fields.Date.today() + timedelta(days=10)), 'paper_code': 'QPQA', 'duration': '3 hours', 'notes': 'QA',
            'study_year': '3', 'semester': 'V'}
        writer = PdfFileWriter()
        writer.addBlankPage(width=595, height=842)
        out = io.BytesIO()
        writer.write(out)
        cls.file = {'level': 'balanced', 'filename': 'qa.pdf', 'content': base64.b64encode(out.getvalue()).decode()}
        cls.api = cls.env['campus.question.paper'].with_user(cls.teacher)

    def submit(self):
        return self.api.save_submission(self.values, [self.file], submit=True)

    def coe_exam(self):
        self.coe.groups_id |= self.env.ref('ideastone_erp.group_coe_admin')
        today = fields.Date.today()
        year = self.env['op.academic.year'].create({'name': 'COE QA academic year', 'code': 'COEQA',
            'start_date': today - timedelta(days=60), 'end_date': today + timedelta(days=365), 'company_id': self.env.company.id})
        course = self.env['op.course'].create({'name': 'COE QA programme', 'code': 'COEQA', 'department_id': self.dept.id, 'company_id': self.env.company.id})
        batch = self.env['op.batch'].create({'name': 'COE QA Year III', 'code': 'COEQA', 'course_id': course.id,
            'start_date': year.start_date, 'end_date': year.end_date, 'company_id': self.env.company.id, 'campus_year_id': year.id})
        kind = self.env['op.exam.type'].create({'name': 'COE QA assessment', 'code': 'COEQA', 'company_id': self.env.company.id})
        session = self.env['op.exam.session'].create({'name': 'COE QA session', 'exam_code': 'COEQA', 'course_id': course.id,
            'batch_id': batch.id, 'exam_type': kind.id, 'company_id': self.env.company.id, 'campus_year_id': year.id,
            'start_date': year.start_date, 'end_date': year.end_date})
        start = datetime.combine(today + timedelta(days=10), time(4))
        return self.env['op.exam'].create({'name': 'COE QA paper', 'exam_code': 'COEQA', 'session_id': session.id,
            'subject_id': self.subject.id, 'start_time': start, 'end_time': start + timedelta(hours=3), 'total_marks': 100,
            'min_marks': 50, 'coe_study_year': '3', 'coe_expected': 60})

    def test_coe_filters_scope_and_navigation(self):
        exam = self.coe_exam()
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        f = {'year_id': exam.campus_year_id.id, 'department_id': self.dept.id, 'study_year': '3'}
        self.assertEqual([r['id'] for r in api.get_workspace('records', f)['exams']], exam.ids)
        self.assertEqual(api.get_workspace('records', dict(f, study_year='4'))['exams'], [])
        self.assertEqual(api.exam_action(exam.id)['views'], [(self.env.ref('ideastone_erp.mvp_exams_form').id, 'form')])
        self.assertFalse(api.exam_action()['res_id'])
        with self.assertRaises(AccessError):
            api.with_user(self.teacher).get_workspace()
        foreign = self.env['res.company'].create({'name': 'COE restricted college'})
        other_year = self.env['op.academic.year'].create({'name': 'Private year', 'code': 'COEPRIVATE',
            'start_date': exam.campus_year_id.start_date, 'end_date': exam.campus_year_id.end_date, 'company_id': foreign.id})
        with self.assertRaises(AccessError):
            api.get_workspace('records', {'year_id': other_year.id})
        with self.assertRaises(ValidationError):
            api.get_workspace('records', dict(f, study_year=True))
        overview = self.env['campus.dashboard'].with_user(self.coe).get_overview()
        self.assertTrue(overview['is_coe_workspace'])
        self.assertEqual(len(overview['faculty_modules']), 7)
        for module in overview['faculty_modules']:
            for item in module['items']:
                view = self.env.ref(item['action']).params
                self.assertTrue(view)

    def test_coe_operations_and_case_register(self):
        exam = self.coe_exam()
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        api.save_operations(exam.id, {'coe_hall': 'QA A201', 'coe_invigilator': 'QA invigilator', 'coe_present': 55})
        self.assertEqual(exam.coe_present, 55)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            api.save_operations(exam.id, {'coe_present': 61})
        with self.assertRaises(ValidationError):
            api.save_operations(exam.id, {'campus_state': 'published'})
        with self.assertRaises(AccessError):
            api.with_user(self.teacher).save_operations(exam.id, {'coe_hall': 'Other hall'})
        case_id = api.save_case({'exam_id': exam.id, 'name': 'QA correction', 'kind': 'correction', 'note': 'QA notes'})
        api.save_case({'state': 'resolved', 'note': 'QA resolved'}, case_id)
        self.assertEqual(self.env['campus.coe.case'].browse(case_id).state, 'resolved')
        self.assertTrue(self.env['campus.mvp.audit'].search_count([('model_name', '=', 'campus.coe.case'), ('record_id', '=', case_id)]))

    def test_coe_subject_progress_reports_hod_status_without_confidential_content(self):
        exam = self.coe_exam()
        record_id = self.submit()
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        scope = {'year_id': exam.campus_year_id.id, 'department_id': self.dept.id, 'study_year': '3'}
        data = api.get_workspace('papers', scope)
        subject = data['subject_progress'][0]
        self.assertEqual(subject['subject_id'], self.subject.id)
        self.assertEqual(subject['study_year'], '3')
        self.assertEqual(subject['updates'][0]['state'], 'submitted')
        self.assertEqual(data['papers'], [])
        with self.assertRaises(AccessError):
            self.api.with_user(self.coe).download_set(self.api.get_workspace()['rows'][0]['sets'][0]['id'])
        reviewer = self.api.with_user(self.hod)
        reviewer.decide(record_id, 'return', note='Confidential HOD revision detail')
        updates = api.get_workspace('papers', scope)['subject_progress'][0]['updates']
        self.assertEqual(updates[0]['state'], 'returned')
        self.assertNotIn('Confidential HOD revision detail', str(updates))
        self.assertEqual(set(updates[0]), {'state', 'status', 'hod', 'updated', 'exam_date', 'department_id', 'subject_id', 'study_year', 'semester'})
        self.api.save_submission(self.values, [self.file], record_id, True)
        row = self.api.get_workspace()['rows'][0]
        reviewer.decide(record_id, 'approve', row['sets'][0]['id'])
        data = api.get_workspace('papers', scope)
        self.assertEqual(data['subject_progress'][0]['updates'][0]['state'], 'approved')
        self.assertEqual(data['papers'][0]['study_year'], '3')
        self.assertEqual(len(data['papers'][0]['sets']), 1)
        self.other.groups_id |= self.env.ref('ideastone_erp.group_exam_paper_coe')
        route = self.env['campus.question.paper.routing'].search([('department_id', '=', self.dept.id)])
        route.coe_id = self.other
        self.submit()
        self.assertEqual(len(api.get_workspace('papers', scope)['subject_progress'][0]['updates']), 1)

    def test_coe_ambiguous_subject_year_stays_in_unassigned_group(self):
        exam = self.coe_exam()
        exam.copy({'exam_code': 'COEQA-SECOND', 'coe_study_year': '4',
                   'start_time': exam.start_time + timedelta(hours=4), 'end_time': exam.end_time + timedelta(hours=4)})
        record_id = self.submit()
        self.env['campus.question.paper'].browse(record_id).sudo().write({'study_year': False, 'semester': False})
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        scope = {'year_id': exam.campus_year_id.id, 'department_id': self.dept.id}
        data = api.get_workspace('papers', scope)
        unassigned = next(s for s in data['subject_progress'] if s['study_year'] == '')
        self.assertEqual(unassigned['updates'][0]['state'], 'submitted')
        assigned = api.get_workspace('papers', dict(scope, study_year='3'))
        self.assertFalse(assigned['subject_progress'][0]['updates'])
        data = api.get_workspace('papers', dict(scope, study_year='unassigned'))
        self.assertEqual(data['exams'], [])
        self.assertEqual(len(data['subject_progress']), 1)
        self.assertEqual(len(data['subject_progress'][0]['updates']), 1)

    def test_year_and_roman_semester_validation_and_handoff(self):
        for year, semester in [('', ''), ('5', 'IX'), (True, 'I'), ([], 'I'), ('3', 'II'), ('4', 'V'), ('2', '')]:
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.api.save_submission(dict(self.values, study_year=year, semester=semester), [self.file], submit=True)
        for year, semesters in [('1', ('I', 'II')), ('2', ('III', 'IV')), ('3', ('V', 'VI')), ('4', ('VII', 'VIII'))]:
            for semester in semesters:
                record_id = self.api.save_submission(dict(self.values, study_year=year, semester=semester), [self.file])
                self.assertEqual(self.env['campus.question.paper'].browse(record_id).semester, semester)
        record_id = self.submit()
        reviewer = self.api.with_user(self.hod)
        row = next(r for r in reviewer.get_workspace('hod')['rows'] if r['id'] == record_id)
        self.assertEqual((row['study_year'], row['semester']), ('3', 'V'))
        reviewer.decide(record_id, 'approve', row['sets'][0]['id'])
        reviewer.decide(record_id, 'forward')
        for api, role in [(self.api, 'faculty'), (reviewer, 'hod'), (self.api.with_user(self.coe), 'coe')]:
            row = next(r for r in api.get_workspace(role)['rows'] if r['id'] == record_id)
            self.assertEqual((row['study_year'], row['semester']), ('3', 'V'))
        with self.assertRaises(AccessError):
            self.api.save_submission(dict(self.values, study_year='4', semester='VIII'), [], record_id)

    def test_explicit_paper_year_overrides_scheduled_subject_year(self):
        exam = self.coe_exam()
        record_id = self.api.save_submission(dict(self.values, study_year='4', semester='VIII'), [self.file], submit=True)
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        scope = {'year_id': exam.campus_year_id.id, 'department_id': self.dept.id, 'study_year': '4'}
        update = api.get_workspace('papers', scope)['subject_progress'][0]['updates'][0]
        self.assertEqual((update['study_year'], update['semester']), ('4', 'VIII'))
        self.assertFalse(api.get_workspace('papers', dict(scope, study_year='3'))['subject_progress'][0]['updates'])
        reviewer = self.api.with_user(self.hod)
        reviewer.decide(record_id, 'approve', self.env['campus.question.paper'].browse(record_id).set_ids.id)
        reviewer.decide(record_id, 'forward')
        api.paper_action(record_id, 'receive')
        api.save_operations(exam.id, {'coe_hall': 'QA Hall', 'coe_invigilator': 'QA Invigilator'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            api.paper_action(record_id, 'dispatch', 'Wrong study year', exam.id)

    def test_coe_approved_selected_pdf_receipt_and_dispatch(self):
        exam = self.coe_exam()
        record_id = self.api.save_submission(self.values, [self.file, dict(self.file, level='advanced')], submit=True)
        sets = self.api.get_workspace()['rows'][0]['sets']
        reviewer = self.api.with_user(self.hod)
        reviewer.decide(record_id, 'approve', sets[0]['id'])
        api = self.env['campus.coe.workspace'].with_user(self.coe)
        official = next(r for r in api.get_workspace('papers', {'year_id': exam.campus_year_id.id})['papers'] if r['id'] == record_id)
        self.assertEqual(len(official['sets']), 1)
        with self.assertRaises(AccessError):
            self.api.with_user(self.coe).download_set(sets[1]['id'])
        with self.assertRaises(AccessError):
            api.paper_action(record_id, 'receive')
        reviewer.decide(record_id, 'forward')
        api.paper_action(record_id, 'receive')
        with self.assertRaises(ValidationError):
            api.paper_action(record_id, 'receive')
        with self.assertRaises(ValidationError):
            api.paper_action(record_id, 'dispatch', 'QA packet', exam.id)
        api.save_operations(exam.id, {'coe_hall': 'QA A201', 'coe_invigilator': 'QA invigilator'})
        start, end = exam.start_time, exam.end_time
        exam.write({'start_time': start + timedelta(days=1), 'end_time': end + timedelta(days=1)})
        with self.assertRaises(ValidationError):
            api.paper_action(record_id, 'dispatch', 'Wrong examination date', exam.id)
        exam.write({'start_time': start, 'end_time': end})
        api.paper_action(record_id, 'dispatch', 'QA sealed packet 01', exam.id)
        self.assertTrue(self.env['campus.question.paper'].browse(record_id).coe_dispatched_at)
        self.assertEqual(exam.coe_paper_id.id, record_id)
        self.assertEqual(len(self.api.with_user(self.coe).get_workspace('coe')['rows'][0]['sets']), 1)
        with self.assertRaises(ValidationError):
            api.paper_action(record_id, 'dispatch', 'Duplicate packet', exam.id)

    def test_shared_faculty_can_open_workspace_and_submit(self):
        faculty = self.env['op.faculty'].search([('user_id', '=', self.teacher.id)])
        faculty.company_id = False
        self.assertEqual(self.api.get_workspace()['rows'], [])
        record_id = self.submit()
        paper = self.env['campus.question.paper'].browse(record_id)
        self.assertEqual(paper.faculty_id, faculty)
        self.assertEqual(paper.company_id, self.env.company)
        self.assertEqual(self.api.get_workspace()['rows'][0]['id'], record_id)

    def test_foreign_college_and_inactive_faculty_cannot_open_workspace(self):
        faculty = self.env['op.faculty'].search([('user_id', '=', self.teacher.id)])
        foreign = self.env['res.company'].create({'name': 'Other faculty college'})
        faculty.company_id = foreign
        with self.assertRaises(AccessError):
            self.api.get_workspace()
        with self.assertRaises(AccessError):
            self.submit()
        faculty.write({'company_id': False, 'active': False})
        with self.assertRaises(AccessError):
            self.api.get_workspace()

    def test_connected_approval_forwarding_and_receipt(self):
        record_id = self.submit()
        reviewer = self.api.with_user(self.hod)
        row = reviewer.get_workspace('hod')['rows'][0]
        self.assertEqual(row['id'], record_id)
        self.assertEqual(self.api.with_user(self.coe).get_workspace('coe')['rows'], [])
        reviewer.decide(record_id, 'approve', row['sets'][0]['id'], 'Blueprint checked')
        self.assertEqual(self.api.get_workspace()['rows'][0]['state'], 'approved')
        reviewer.decide(record_id, 'forward')
        receipt = self.api.with_user(self.coe).get_workspace('coe')['rows'][0]
        self.assertEqual(receipt['state'], 'forwarded')
        self.assertEqual(len(receipt['history']), 4)
        self.assertEqual(self.api.with_user(self.coe).download_set(receipt['sets'][0]['id'])['filename'], 'qa.pdf')

    def test_return_revision_pdf_versions_and_history(self):
        record_id = self.submit()
        reviewer = self.api.with_user(self.hod)
        with self.assertRaises(ValidationError):
            reviewer.decide(record_id, 'return', note='')
        reviewer.decide(record_id, 'return', note='Fix the blueprint')
        old_id = self.api.get_workspace()['rows'][0]['sets'][0]['id']
        self.api.save_submission(self.values, [self.file], record_id, True)
        row = reviewer.get_workspace('hod')['rows'][0]
        self.assertEqual(row['revision'], 2)
        self.assertNotEqual(row['sets'][0]['id'], old_id)
        self.assertEqual(len(self.env['campus.question.paper.set'].with_context(active_test=False).search([('paper_id', '=', record_id)])), 2)
        self.assertIn('Returned for revision', [e['action'] for e in row['history']])

    def test_author_other_faculty_and_direct_crud_guards(self):
        record_id = self.submit()
        with self.assertRaises(AccessError):
            self.api.with_user(self.other).download_set(self.api.get_workspace()['rows'][0]['sets'][0]['id'])
        self.assertEqual(self.api.with_user(self.other).get_workspace()['rows'], [])
        with self.assertRaises(AccessError):
            self.api.decide(record_id, 'approve')
        with self.assertRaises(AccessError):
            self.api.browse(record_id).write({'state': 'forwarded'})
        with self.assertRaises(AccessError):
            self.api.save_submission(self.values, [], record_id)
        with self.assertRaises(AccessError):
            self.api.with_user(self.other).get_workspace('hod')

    def test_only_one_current_set_can_be_selected(self):
        first = self.submit()
        second = self.submit()
        rows = {r['id']: r for r in self.api.get_workspace()['rows']}
        reviewer = self.api.with_user(self.hod)
        with self.assertRaises(ValidationError):
            reviewer.decide(first, 'approve', rows[second]['sets'][0]['id'])
        reviewer.decide(first, 'approve', rows[first]['sets'][0]['id'])
        with self.assertRaises(ValidationError):
            reviewer.decide(first, 'approve', rows[first]['sets'][0]['id'])
        with self.assertRaises(ValidationError):
            reviewer.decide(second, 'forward')

    def test_pdf_validation_and_required_upload(self):
        for invalid in ([], {}, True, 'unknown'):
            with self.assertRaises(ValidationError):
                self.api.save_submission(self.values,[dict(self.file,level=invalid)],submit=True)
            with self.assertRaises(ValidationError):
                self.api.save_submission(self.values,[self.file],submit=True,levels=[invalid])
        for bad in ('not base64', base64.b64encode(b'%PDF-1.4 invalid').decode(), base64.b64encode(b'not PDF').decode()):
            with self.assertRaises(ValidationError):
                self.api.save_submission(self.values, [dict(self.file, content=bad)], submit=True)
        with self.assertRaises(ValidationError):
            self.api.save_submission(self.values, [], submit=True)
        with self.assertRaises(ValidationError):
            self.api.save_submission(self.values, [self.file, self.file], submit=True)

    def test_assignment_active_college_and_id_validation(self):
        wrong = dict(self.values, subject_id=0)
        with self.assertRaises(AccessError):
            self.api.save_submission(wrong, [self.file], submit=True)
        record_id = self.submit()
        foreign = self.env['res.company'].create({'name': 'Private QP college'})
        self.teacher.company_ids |= foreign
        scoped = self.api.with_context(allowed_company_ids=[foreign.id])
        with self.assertRaises(AccessError):
            scoped.download_set(self.api.get_workspace()['rows'][0]['sets'][0]['id'])
        with self.assertRaises(ValidationError):
            self.api.decide(True, 'forward')
        self.assertTrue(record_id)

    def test_coe_sees_only_official_set(self):
        record_id = self.api.save_submission(self.values, [self.file, dict(self.file, level='advanced', filename='advanced.pdf')], submit=True)
        sets = self.api.get_workspace()['rows'][0]['sets']
        reviewer = self.api.with_user(self.hod)
        reviewer.decide(record_id, 'approve', sets[0]['id'])
        reviewer.decide(record_id, 'forward')
        self.assertEqual(len(self.api.with_user(self.coe).get_workspace('coe')['rows'][0]['sets']), 1)
        with self.assertRaises(AccessError):
            self.api.with_user(self.coe).download_set(sets[1]['id'])
        self.assertEqual(self.env['campus.question.paper.set'].with_user(self.coe).search_count([]), 1)

    def test_archived_sets_and_revoked_recipient_cannot_be_forwarded(self):
        record_id=self.api.save_submission(self.values,[self.file])
        old_id=self.api.get_workspace()['rows'][0]['sets'][0]['id']
        self.api.save_submission(self.values,[self.file],record_id,True)
        reviewer=self.api.with_user(self.hod).with_context(active_test=False)
        with self.assertRaises(ValidationError):
            reviewer.decide(record_id,'approve',old_id)
        current=self.api.get_workspace()['rows'][0]['sets'][0]['id']
        reviewer.decide(record_id,'approve',current)
        foreign=self.env['res.company'].create({'name':'New COE college'})
        self.coe.write({'company_id':foreign.id,'company_ids':[(6,0,foreign.ids)]})
        with self.assertRaises(ValidationError):
            reviewer.decide(record_id,'forward')

    def test_selected_difficulty_sets_persist_after_draft_edit(self):
        record_id = self.api.save_submission(self.values, [self.file, dict(self.file, level='advanced')])
        self.api.save_submission(self.values, [], record_id, True, ['advanced'])
        self.assertEqual([s['level'] for s in self.api.get_workspace()['rows'][0]['sets']], ['advanced'])
        with self.assertRaises(ValidationError):
            self.api.save_submission(self.values, [], submit=True, levels=['moderate'])

    def test_hod_and_faculty_navigation_use_separate_actions(self):
        self.env['op.faculty'].create({'first_name': 'Question paper', 'last_name': 'HOD QA', 'gender': 'male', 'birth_date': '1980-01-01',
            'partner_id': self.env['res.partner'].create({'name': 'HOD QA', 'user_id': self.hod.id, 'company_id': self.env.company.id}).id,
            'main_department_id': self.dept.id})
        for account, expected in [(self.teacher,'ideastone_erp.action_faculty_question_papers'), (self.hod,'ideastone_erp.action_hod_question_papers')]:
            data=self.env['campus.dashboard'].with_user(account).get_overview()
            teaching=next(m for m in data['faculty_modules'] if m['key']=='teaching')
            action=next(i for i in teaching['items'] if i['label']=='Examinations')
            self.assertEqual(action['action'], expected)

    def test_revoked_hod_and_past_exam_submission_are_rejected(self):
        record_id=self.submit()
        self.hod.groups_id -= self.env.ref('ideastone_erp.group_exam_paper_hod')
        with self.assertRaises(AccessError):
            self.api.with_user(self.hod).decide(record_id,'return',note='Review')
        with self.assertRaises(ValidationError):
            self.api.save_submission(dict(self.values,exam_date=str(fields.Date.today()-timedelta(days=1))),[self.file],submit=True)
