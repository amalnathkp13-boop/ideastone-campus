from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class LibraryDesk(models.AbstractModel):
    _name = "campus.library.desk"
    _description = "Collection scoped faculty circulation desk"

    def _scope(self):
        return self.env["campus.responsibility"]._library_scope()

    def _card_domain(self):
        return ["|", "&", ("type", "=", "student"), ("student_id.company_id", "=", self.env.company.id),
                "&", ("type", "=", "faculty"), ("faculty_id.company_id", "=", self.env.company.id)]

    @api.model
    def get_desk(self, query="", page=0, card_query=""):
        scope = self._scope()
        if any(not isinstance(value, str) or len(value) > 200 for value in (query, card_query)) or type(page) is not int or not 0 <= page <= 10000:
            raise ValidationError(_("Invalid library search."))
        units = self.env["op.media.unit"].sudo().search([
            ("campus_company_id", "=", self.env.company.id),
            ("media_type_id", "in", scope), ("state", "=", "available"),
            "|", "|", ("name", "ilike", query), ("media_id.name", "ilike", query), ("barcode", "ilike", query),
        ], limit=30)
        cards = self.env["op.library.card"].sudo().search(self._card_domain() + [("number", "ilike", card_query)], limit=30)
        loans = self.env["op.media.movement"].sudo().search([
            ("media_type_id", "in", scope), ("company_id", "=", self.env.company.id), ("state", "=", "issue"),
        ], offset=page * 20, limit=21)
        return {
            "units": [{"id": r.id, "label": f"{r.barcode} · {r.media_id.name}"} for r in units],
            "cards": [{"id": r.id, "label": f"{r.number} · {r.partner_id.name}"} for r in cards],
            "loans": [{"id": r.id, "title": r.media_id.name, "borrower": r.library_card_id.number,
                       "due": fields.Date.to_string(r.return_date)} for r in loans[:20]],
            "next": len(loans) > 20,
        }

    @api.model
    def issue(self, unit_id, card_id):
        scope = self._scope()
        if type(unit_id) is not int or type(card_id) is not int:
            raise ValidationError(_("Select a copy and a library card."))
        unit = self.env["op.media.unit"].sudo().search([("id", "=", unit_id), ("media_type_id", "in", scope),
                                                        ("campus_company_id", "=", self.env.company.id)], limit=1)
        card = self.env["op.library.card"].sudo().search(self._card_domain() + [("id", "=", card_id)], limit=1)
        if not unit or not card:
            raise AccessError(_("This copy or borrower is outside your appointment scope."))
        # Lock both resources so simultaneous issues cannot exceed copy/card capacity.
        self.env.cr.execute("SELECT id FROM op_library_card WHERE id=%s FOR UPDATE", [card.id])
        self.env.cr.execute("SELECT id FROM op_media_unit WHERE id=%s FOR UPDATE", [unit.id])
        unit.invalidate_recordset()
        loans = self.env["op.media.movement"].sudo()
        if unit.state != "available" or loans.search_count([("library_card_id", "=", card.id), ("state", "=", "issue")]) >= card.library_card_type_id.allow_media:
            raise ValidationError(_("The copy is unavailable or the borrower has reached the loan limit."))
        today = fields.Date.context_today(self)
        loan = loans.create({
            "media_id": unit.media_id.id, "media_unit_id": unit.id, "library_card_id": card.id,
            "type": card.type, "student_id": card.student_id.id, "faculty_id": card.faculty_id.id,
            "partner_id": card.partner_id.id, "user_id": (card.student_id or card.faculty_id).user_id.id,
            "issued_date": today, "return_date": today + timedelta(days=card.library_card_type_id.duration),
            "company_id": self.env.company.id,
        })
        loan.issue_media()
        loan.message_post(body=_("Issued through the approved faculty circulation desk."))
        return True

    @api.model
    def return_loan(self, loan_id):
        scope = self._scope()
        if type(loan_id) is not int:
            raise ValidationError(_("Invalid loan."))
        loan = self.env["op.media.movement"].sudo().search([
            ("id", "=", loan_id), ("media_type_id", "in", scope), ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not loan:
            raise AccessError(_("This loan is outside your appointment scope."))
        self.env.cr.execute("SELECT id FROM op_media_movement WHERE id=%s FOR UPDATE", [loan.id])
        loan.invalidate_recordset()
        if loan.state != "issue":
            raise ValidationError(_("Only an issued loan can be returned."))
        loan.return_media(fields.Date.context_today(self))
        loan.message_post(body=_("Returned through the approved faculty circulation desk. Any fine requires the finance workflow."))
        return True


class LibraryCopy(models.Model):
    _inherit = "op.media.unit"

    campus_company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
