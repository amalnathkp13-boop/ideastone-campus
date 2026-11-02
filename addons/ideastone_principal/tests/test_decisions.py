from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo import fields


class TestPrincipalDecisions(TransactionCase):
    def setUp(self):
        super().setUp()
        users = self.env['res.users']
        self.principal = users.create({'name': 'Principal', 'login': 'decisions.principal@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('ideastone_principal.group_principal').id])]})
        self.other = users.create({'name': 'Other Principal', 'login': 'other.principal@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('ideastone_principal.group_principal').id])]})
        self.staff = users.create({'name': 'Organizer', 'login': 'organizer@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.coordinator = users.create({'name': 'Coordinator', 'login': 'coordinator@test.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.service = self.env['ideastone.principal.decisions'].with_user(self.principal)
        start = fields.Date.today() + timedelta(days=7)
        self.start = start + timedelta(days=(7 - start.weekday()) % 7)

    def leave(self):
        employee = self.env['hr.employee'].create({'name': 'Assigned staff member', 'company_id': self.env.company.id})
        category = self.env['hr.leave.type'].create({'name': 'Principal test leave', 'requires_allocation': 'no', 'leave_validation_type': 'both'})
        return self.env['hr.leave'].create({'employee_id': employee.id, 'holiday_status_id': category.id,
            'request_date_from': self.start, 'request_date_to': self.start + timedelta(days=1),
            'principal_reviewer_id': self.principal.id, 'private_name': 'Test coverage request'})

    def test_staff_native_approval_and_immutable_evidence(self):
        leave = self.leave()
        with self.assertRaises(UserError):
            self.service.decide('staff', leave.id, 'approved', 'Cannot skip HoD')
        leave.action_approve()
        leave.employee_id.user_id = self.principal
        with self.assertRaises(AccessError):
            self.service.decide('staff', leave.id, 'approved', 'Own leave must use another reviewer')
        leave.employee_id.user_id = False
        with self.assertRaises(AccessError):
            self.service.with_user(self.other).decide('staff', leave.id, 'approved', 'Wrong reviewer')
        with self.assertRaises(ValidationError):
            self.service.decide('staff', leave.id, 'approved', '')
        self.service.decide('staff', leave.id, 'approved', 'Coverage verified')
        self.assertEqual(leave.state, 'validate')
        self.assertTrue(self.env['resource.calendar.leaves'].search_count([('holiday_id', '=', leave.id)]))
        log = self.env['ideastone.principal.decision.log'].search([('source_model', '=', 'hr.leave'), ('source_id', '=', leave.id)])
        self.assertEqual(log.decided_by_id, self.principal)
        self.assertEqual(log.remark, 'Coverage verified')
        with self.assertRaises(AccessError):
            log.with_user(self.principal).write({'remark': 'Changed'})
        with self.assertRaises(UserError):
            self.service.decide('staff', leave.id, 'rejected', 'Duplicate click')

    def test_event_return_resubmit_sign_and_calendar(self):
        event = self.env['ideastone.principal.event.proposal'].with_user(self.staff).create({
            'name': 'Technical symposium', 'coordinator_id': self.coordinator.id, 'principal_id': self.principal.id,
            'date_start': self.start, 'date_end': self.start, 'venue': 'Main hall', 'organizer': 'ECE Department',
            'purpose': 'Student research presentations', 'budget': 95000, 'attendees': 380,
        })
        event.action_submit()
        with self.assertRaises(UserError):
            self.service.decide('event', event.id, 'approved', 'Cannot skip coordinator')
        event.with_user(self.coordinator).write({'recommendation': 'Department recommends approval'})
        event.with_user(self.coordinator).action_forward()
        with self.assertRaises(ValidationError):
            self.service.decide('event', event.id, 'approved', 'Missing planning checks')
        self.service.decide('event', event.id, 'changes', 'Add safety plan and funding details')
        self.assertEqual(event.state, 'changes')
        self.assertFalse(event.calendar_event_id)
        event.with_user(self.staff).write({'safety_plan': 'Emergency exits and first aid confirmed', 'funding': 'Department budget'})
        event.with_user(self.staff).action_submit()
        event.with_user(self.coordinator).write({'venue_checked': True, 'budget_checked': True, 'safety_checked': True})
        event.with_user(self.coordinator).action_forward()
        self.service.decide('event', event.id, 'approved', 'Signed after planning checks')
        self.assertEqual(event.calendar_event_id.name, event.name)
        self.assertEqual(event.calendar_event_id.status, 'upcoming')
        self.assertEqual(event.calendar_event_id.company_id, self.env.company)
        with self.assertRaises(UserError):
            self.service.decide('event', event.id, 'approved', 'Repeated signature')
        with self.assertRaises(AccessError):
            event.with_user(self.staff).write({'state': 'review'})

    def test_queue_filters_routing_and_generic_request(self):
        leave = self.leave()
        leave.action_approve()
        request = self.env['ideastone.principal.request'].with_user(self.staff).create({
            'name': 'Late admission exception', 'request_type': 'admission', 'description': 'Verified documents'})
        request.action_submit()
        with self.assertRaises(AccessError):
            request.with_user(self.principal).write({'state': 'approved'})
        data = self.service.get_data()
        self.assertIn(f'staff-{leave.id}', [row['key'] for row in data['rows']])
        other_data = self.service.with_user(self.other).get_data()
        self.assertNotIn(f'staff-{leave.id}', [row['key'] for row in other_data['rows']])
        with self.assertRaises(AccessError):
            self.service.with_user(self.staff).get_data()
        self.service.decide('request', request.id, 'approved', 'Documents checked')
        self.assertEqual(request.state, 'approved')
        modules = self.env['campus.dashboard'].with_user(self.principal).get_overview()['faculty_modules']
        decisions = next(module for module in modules if module['key'] == 'decisions')
        self.assertEqual([item['label'] for item in decisions['items']],
            ['Pending decisions', 'Staff leave approvals', 'Student leave approvals', 'Event management'])

    def test_student_canonical_review_and_no_cross_company_decisions(self):
        advisor = self.staff
        advisor.groups_id = [(4, self.env.ref('openeducat_core.group_op_faculty').id)]
        student = self.env['op.student'].create({'first_name': 'Student', 'last_name': 'Review', 'gender': 'm',
            'birth_date': '2005-01-01', 'company_id': self.env.company.id,
            'partner_id': self.env['res.partner'].create({'name': 'Student Review', 'company_id': self.env.company.id}).id})
        route = self.env['campus.student.leave.routing'].create({'name': 'Assigned route', 'student_id': student.id,
            'advisor_id': advisor.id, 'hod_id': self.coordinator.id, 'principal_id': self.principal.id})
        leave = self.env['campus.student.leave'].with_user(advisor).create({'name': 'Long-term medical leave',
            'routing_id': route.id, 'reason': 'Extended recovery', 'date': self.start,
            'deadline': self.start + timedelta(days=30), 'principal_supporting_details': 'Continuity plan supplied'})
        leave.action_submit()
        leave.action_approve()
        leave.with_user(self.coordinator).action_approve()
        self.service.decide('student', leave.id, 'approved', 'Academic continuity plan reviewed')
        self.assertEqual(leave.state, 'approved')
        self.assertIn('Academic continuity plan reviewed', leave.decision_log)
        earlier = self.env['campus.student.leave'].with_user(advisor).create({'name': 'Earlier stage rejection',
            'routing_id': route.id, 'reason': 'Supporting details missing', 'date': self.start, 'deadline': self.start})
        earlier.action_submit()
        earlier.write({'decision_reason': 'Advisor declined before Principal review'})
        earlier.action_reject()
        self.assertNotIn(f'student-{earlier.id}', [row['key'] for row in self.service.get_data()['rows']])
        other_company = self.env['res.company'].create({'name': 'Other college'})
        self.principal.company_ids = [(4, other_company.id)]
        self.coordinator.company_ids = [(4, other_company.id)]
        event = self.env['ideastone.principal.event.proposal'].sudo().create({'name': 'Other event',
            'company_id': other_company.id, 'coordinator_id': self.coordinator.id, 'principal_id': self.principal.id,
            'date_start': self.start, 'date_end': self.start, 'venue': 'Hall', 'organizer': 'Other college',
            'purpose': 'Review', 'state': 'review'})
        with self.assertRaises(AccessError):
            self.service.decide('event', event.id, 'approved', 'Wrong active college')
