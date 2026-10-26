from odoo import api, models


class QuestionPaperNavigation(models.AbstractModel):
    _inherit = 'campus.dashboard'

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self.env.user.has_group('ideastone_erp.group_exam_paper_hod'):
            action = self.env.ref('ideastone_erp.action_hod_question_papers')
            for module in data.get('faculty_modules', []):
                if module['key'] == 'teaching':
                    for item in module['items']:
                        if item.get('action') == 'ideastone_erp.action_faculty_question_papers':
                            item.update(action='ideastone_erp.action_hod_question_papers', action_id=action.id)
            data.update(is_hod=True, workspace_role='Faculty · Department HOD')
        return data
