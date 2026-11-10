"""Presentation only: retain the source currency's rounding and number format."""

from odoo.tools.misc import format_amount as odoo_format_amount


def format_amount(env, amount, currency, lang_code=False):
    value = odoo_format_amount(env, amount, currency, lang_code=lang_code)
    return value.replace(currency.symbol, "₹") if currency.symbol else "₹\N{NO-BREAK SPACE}" + value


def format_tax_labels(totals, currency):
    """Replace presentation strings, including labels added by cash rounding."""
    symbol = currency.symbol if currency else ""
    rows = [totals, *totals.get("subtotals", []),
            *(row for group in totals.get("groups_by_subtotal", {}).values() for row in group)]
    for row in rows:
        for key, value in row.items():
            if key.startswith("formatted_") and isinstance(value, str):
                row[key] = value.replace(symbol, "₹") if symbol else "₹\N{NO-BREAK SPACE}" + value
    return totals
