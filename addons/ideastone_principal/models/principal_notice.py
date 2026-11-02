from odoo.exceptions import AccessError, UserError

from odoo import _, fields, models


class PrincipalNotice(models.Model):
    _name = "ideastone.principal.notice"
    _description = "Principal Notice"
    _inherit = ["mail.thread"]
    _order = "published_on desc, id desc"

    name = fields.Char(string="Title", required=True, tracking=True)
    body = fields.Html(required=True)
    audience = fields.Selection([
        ("all", "Everyone"), ("staff", "Staff"),
        ("students", "Students"), ("parents", "Parents"),
    ], required=True, default="all")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    author_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    published_on = fields.Datetime(readonly=True)
    state = fields.Selection([
        ("draft", "Draft"), ("published", "Published"), ("archived", "Archived"),
    ], default="draft", required=True, tracking=True)

    def _require_principal(self):
        if not self.env.user.has_group("ideastone_principal.group_principal"):
            raise AccessError(_("Only a principal can manage notices."))

    def action_publish(self):
        self._require_principal()
        for notice in self:
            if notice.state != "draft":
                raise UserError(_("Only draft notices can be published."))
            notice.write({"state": "published", "published_on": fields.Datetime.now()})

    def action_archive(self):
        self._require_principal()
        for notice in self:
            if notice.state != "published":
                raise UserError(_("Only published notices can be archived."))
            notice.write({"state": "archived"})
