import base64
import io
from datetime import timedelta

from PyPDF2 import PdfFileWriter

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


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
            'exam_date': str(fields.Date.today() + timedelta(days=10)), 'paper_code': 'QPQA', 'duration': '3 hours', 'notes': 'QA'}
        writer = PdfFileWriter()
        writer.addBlankPage(width=595, height=842)
        out = io.BytesIO()
        writer.write(out)
        cls.file = {'level': 'balanced', 'filename': 'qa.pdf', 'content': base64.b64encode(out.getvalue()).decode()}
        cls.api = cls.env['campus.question.paper'].with_user(cls.teacher)

    def submit(self):
        return self.api.save_submission(self.values, [self.file], submit=True)

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
