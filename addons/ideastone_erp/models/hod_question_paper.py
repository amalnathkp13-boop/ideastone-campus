from odoo import api, models


class QuestionPaperNavigation(models.AbstractModel):
    _inherit = 'campus.dashboard'

    @api.model
    def get_overview(self):
        data = super().get_overview()
        if self.env.user.has_group('ideastone_erp.group_exam_paper_hod'):
            data.update(is_hod=True, workspace_role='Faculty · Department HOD')
        return data
