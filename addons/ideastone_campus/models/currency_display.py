from markupsafe import escape
from odoo.addons.ideastone_campus.currency_display import format_tax_labels

from odoo import api, models


class CurrencyDisplay(models.Model):
    _inherit = "res.currency"

    def format(self, amount):
        rendered = super().format(amount)
        return rendered.replace(self.symbol, "₹") if self.symbol else "₹\N{NO-BREAK SPACE}" + rendered


class CurrencyDisplaySession(models.AbstractModel):
    _inherit = "ir.http"

    def get_currencies(self):
        # Copy the cached metadata; never change res.currency or its rates.
        return {key: dict(value, symbol="₹") for key, value in super().get_currencies().items()}


class CurrencyDisplayReport(models.AbstractModel):
    _inherit = "ir.qweb.field.monetary"

    @api.model
    def value_to_html(self, value, options):
        rendered = super().value_to_html(value, options)
        symbol = options["display_currency"].symbol
        return rendered.replace(escape(symbol), "₹") if symbol else "₹\N{NO-BREAK SPACE}" + rendered


class CurrencyDisplayTaxTotals(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None, is_company_currency_requested=False):
        totals = super()._prepare_tax_totals(base_lines, currency, tax_lines=tax_lines,
                                           is_company_currency_requested=is_company_currency_requested)
        # Native invoice/bill/purchase reports also use preformatted tax labels.
        # Keep every numeric total, tax group, and calculation unchanged.
        return format_tax_labels(totals, currency)


class CurrencyDisplayInvoiceTotals(models.Model):
    _inherit = "account.move"

    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            if move.tax_totals:
                move.tax_totals = format_tax_labels(move.tax_totals, move.currency_id)
