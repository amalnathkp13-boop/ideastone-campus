from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html2plaintext

from odoo import _, api, fields, models


class PrincipalNoticeWorkspace(models.Model):
    _inherit = "ideastone.principal.notice"

    reference = fields.Char(default=lambda self: _("New"), readonly=True, copy=False)
    office = fields.Char(string="Responsible office")
    publish_at = fields.Datetime(string="Publication date")
    expires_at = fields.Datetime(string="Expiry date")
    return_note = fields.Text(readonly=True)
    reviewed_by = fields.Many2one("res.users", readonly=True, copy=False)
    reviewed_on = fields.Datetime(readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Draft"), ("pending", "Pending approval"), ("scheduled", "Scheduled"),
        ("published", "Published"), ("returned", "Returned for edits"), ("archived", "Archived"),
    ], default="draft", required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        self._require_principal()
        for vals in vals_list:
            if vals.get("state", "draft") != "draft" or any(vals.get(k) for k in ("published_on", "reviewed_by", "reviewed_on", "return_note")):
                raise AccessError(_("New notices must start as drafts."))
            vals["reference"] = self.env["ir.sequence"].next_by_code("principal.notice") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        self._require_principal()
        if set(vals) & {"state", "published_on", "reviewed_by", "reviewed_on", "return_note", "reference"}:
            raise AccessError(_("Use the notice workflow to change publication or review status."))
        if set(vals) & {"name", "body", "audience", "company_id", "author_id", "office", "publish_at", "expires_at"}:
            if any(row.state not in ("draft", "returned") for row in self):
                raise UserError(_("Return the notice for edits before changing its content or dates."))
        return super().write(vals)

    @api.constrains("publish_at", "expires_at")
    def _check_publication_dates(self):
        for row in self:
            if row.publish_at and row.expires_at and row.expires_at <= row.publish_at:
                raise ValidationError(_("Expiry must be after publication."))

    def _lock_notices(self):
        self._require_principal()
        self.check_access_rights("write")
        self.check_access_rule("write")
        if self:
            self.env.cr.execute("SELECT id FROM ideastone_principal_notice WHERE id IN %s ORDER BY id FOR UPDATE", [tuple(self.ids)])
            self.invalidate_recordset()

    def _set_workflow(self, values):
        return super().write(values)

    def action_submit(self):
        self._lock_notices()
        if any(row.state not in ("draft", "returned") for row in self):
            raise UserError(_("Only drafts or returned notices can be submitted."))
        self._set_workflow({"state": "pending"})

    def _approve(self, allowed):
        self._lock_notices()
        now = fields.Datetime.now()
        for row in self:
            if row.state not in allowed:
                raise UserError(_("This notice is no longer awaiting this decision. Refresh the queue."))
            if row.expires_at and row.expires_at <= now:
                raise UserError(_("Update the expired visibility dates before publication."))
            scheduled = row.publish_at and row.publish_at > now
            row._set_workflow({"state": "scheduled" if scheduled else "published",
                "published_on": False if scheduled else now, "return_note": False,
                "reviewed_by": self.env.uid, "reviewed_on": now})

    def action_approve(self):
        return self._approve(("pending",))

    def action_publish(self):
        # Preserve the existing direct-publish action for principal-authored drafts.
        return self._approve(("draft", "pending"))

    def action_return(self, reason=None):
        self._lock_notices()
        if any(row.state != "pending" for row in self):
            raise UserError(_("Only pending notices can be returned."))
        if not (reason or "").strip():
            raise ValidationError(_("Explain the correction required before returning a notice."))
        self._set_workflow({"state": "returned", "return_note": reason.strip(),
            "reviewed_by": self.env.uid, "reviewed_on": fields.Datetime.now()})

    def action_archive(self):
        self._lock_notices()
        if any(row.state not in ("published", "scheduled") for row in self):
            raise UserError(_("Only published or scheduled notices can be archived."))
        self._set_workflow({"state": "archived"})

    @api.model
    def _cron_publication(self, company_id=None):
        now = fields.Datetime.now()
        domain = [("company_id", "=", company_id)] if company_id else []
        due = self.search(domain + [("state", "=", "scheduled"), ("publish_at", "<=", now)])
        expired = self.search(domain + [("state", "in", ["published", "scheduled"]), ("expires_at", "<=", now)])
        candidates = due | expired
        if candidates:
            self.env.cr.execute("SELECT id FROM ideastone_principal_notice WHERE id IN %s ORDER BY id FOR UPDATE", [tuple(candidates.ids)])
            candidates.invalidate_recordset()
            due = candidates.filtered(lambda row: row.state == "scheduled" and row.publish_at <= now)
            expired = candidates.filtered(lambda row: row.state in ("published", "scheduled") and row.expires_at and row.expires_at <= now)
        (due - expired)._set_workflow({"state": "published", "published_on": now})
        expired._set_workflow({"state": "archived"})

    @api.model
    def get_workspace(self):
        self._require_principal()
        self._cron_publication(self.env.company.id)
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        rows = self.search([("company_id", "=", self.env.company.id)], order="create_date desc, id desc")
        order = {"pending": 0, "scheduled": 1, "published": 2, "returned": 3, "draft": 4, "archived": 5}
        rows = rows.sorted(lambda row: (order[row.state], row.publish_at if row.state == "scheduled" else now))
        pending = rows.filtered(lambda row: row.state == "pending")
        upcoming = rows.filtered(lambda row: row.state == "scheduled" and fields.Date.context_today(self, row.publish_at) <= today + timedelta(days=7)).sorted("publish_at")
        labels = dict(self._fields["state"].selection)
        audiences = {"all": _("All campus"), "staff": _("Faculty & staff"), "students": _("Students"), "parents": _("Parents")}

        def serialize(row):
            return {"id": row.id, "name": row.name, "reference": row.reference, "office": row.office or row.author_id.name,
                "audience": row.audience, "audience_label": audiences[row.audience], "state": row.state, "status": labels[row.state],
                "summary": html2plaintext(row.body or "")[:350], "publish_at": fields.Datetime.to_string(row.publish_at) if row.publish_at else "",
                "published_on": fields.Datetime.to_string(row.published_on) if row.published_on else "", "return_note": row.return_note or ""}

        insights = []
        if pending.filtered(lambda row: any(word in row.name.lower() for word in ("exam", "examination"))):
            insights.append({"icon": "!", "title": _("Prioritize exam communication"), "text": _("Examination instructions are awaiting approval. Confirm publication timing so students receive guidance before hall-ticket checks.")})
        student_count = len(pending.filtered(lambda row: row.audience in ("students", "all")))
        if student_count > 1:
            insights.append({"icon": "↗", "title": _("Check audience overlap"), "text": _("%(count)s pending notices target students. Coordinate release dates to avoid a crowded notice feed.", count=student_count)})
        insights.append({"icon": "✓", "title": _("Keep scheduled notices current"), "text": _("Review publication and expiry dates weekly; archive notices that are no longer actionable.")})
        return {"today": str(today), "company": self.env.company.name,
            "counts": {"active": len(rows.filtered(lambda row: row.state == "published")), "pending": len(pending),
                "upcoming": len(rows.filtered(lambda row: row.state == "scheduled")),
                "expiring": len(rows.filtered(lambda row: row.state == "published" and row.expires_at and row.expires_at <= now + timedelta(days=7)))},
            "rows": [serialize(row) for row in rows], "upcoming": [serialize(row) for row in upcoming], "insights": insights}
