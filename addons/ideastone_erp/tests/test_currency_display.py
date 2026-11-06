from markupsafe import escape
from odoo.addons.ideastone_campus.currency_display import format_amount
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import format_amount as original_format_amount


@tagged("post_install", "-at_install")
class TestCurrencyDisplay(TransactionCase):
    def test_shared_native_and_report_display_preserves_currency_and_numbers(self):
        usd = self.env.ref("base.USD")
        source = usd.read(["name", "symbol", "rounding", "position", "rate"])[0]
        company_currency = self.env.company.currency_id
        for amount in (0, -0.0, -1234.56, 987654.32):
            expected = original_format_amount(self.env, amount, usd).replace(usd.symbol, "₹")
            self.assertEqual(format_amount(self.env, amount, usd), expected)
            self.assertEqual(usd.format(amount), original_format_amount(self.env, amount + 0.0, usd).replace(usd.symbol, "₹"))
            rendered = self.env["ir.qweb.field.monetary"].value_to_html(amount, {"display_currency": usd})
            self.assertIn("₹", rendered)
            self.assertNotIn("$", rendered)
            self.assertIn('class="oe_currency_value"', rendered)
            self.assertIn(escape(expected.replace("₹", "").strip()), rendered)
        currencies = self.env["ir.http"].get_currencies()
        self.assertTrue(all(row["symbol"] == "₹" for row in currencies.values()))
        self.assertEqual(currencies[usd.id]["digits"], [69, usd.decimal_places])
        self.assertEqual(currencies[usd.id]["position"], usd.position)
        currencies[usd.id]["symbol"] = "test mutation"
        self.assertEqual(self.env["ir.http"].get_currencies()[usd.id]["symbol"], "₹")
        self.assertEqual(usd.read(list(source.keys() - {"id"}))[0], source)
        self.assertEqual(self.env.company.currency_id, company_currency)

    def test_display_handles_currency_position_precision_and_escaping(self):
        currency = self.env["res.currency"].create({"name": "QAX", "symbol": "<&>",
            "rounding": 0.001, "position": "after"})
        amount = 1234.567
        self.assertEqual(format_amount(self.env, amount, currency),
                         original_format_amount(self.env, amount, currency).replace("<&>", "₹"))
        rendered = self.env["ir.qweb.field.monetary"].value_to_html(amount, {"display_currency": currency})
        self.assertTrue(rendered.endswith("₹"))
        self.assertNotIn("&lt;", rendered)
        self.assertIn("1,234.567", rendered)
        self.assertEqual((currency.symbol, currency.rounding, amount), ("<&>", 0.001, 1234.567))

    def test_preformatted_tax_totals_keep_numeric_values_and_source_currency(self):
        usd = self.env.ref("base.USD")
        tax = self.env["account.tax"].create({"name": "Display-only QA tax", "amount": 10})
        line = tax._convert_to_tax_base_line_dict(None, currency=usd, taxes=tax,
                                                 price_unit=1234, quantity=1)
        totals = tax._prepare_tax_totals([line], usd)
        self.assertEqual((totals["amount_untaxed"], totals["amount_total"]), (1234, 1357.4))
        rows = [totals, *totals["subtotals"],
                *(row for group in totals["groups_by_subtotal"].values() for row in group)]
        for row in rows:
            for key, value in row.items():
                if key.startswith("formatted_"):
                    self.assertIn("₹", value)
                    self.assertNotIn("$", value)
        self.assertEqual((usd.name, usd.symbol, line["price_unit"]), ("USD", "$", 1234))
        untaxed = tax._convert_to_tax_base_line_dict(None, currency=usd, price_unit=10, quantity=1)
        without_currency = tax._prepare_tax_totals([untaxed], False)
        self.assertEqual(without_currency["amount_total"], 10)
        self.assertIn("₹", without_currency["formatted_amount_total"])

    def test_native_invoice_cash_rounding_labels_are_rupees(self):
        usd = self.env.ref("base.USD")
        rounding = self.env["account.cash.rounding"].create({"name": "Display QA rounding", "rounding": 0.05,
            "rounding_method": "UP", "strategy": "add_invoice_line"})
        move = self.env["account.move"].new({"move_type": "out_invoice", "currency_id": usd.id,
            "invoice_cash_rounding_id": rounding.id,
            "invoice_line_ids": [(0, 0, {"name": "Display QA item", "quantity": 1, "price_unit": 10.03, "tax_ids": [(5, 0, 0)]})]})
        totals = move.tax_totals
        self.assertAlmostEqual(totals["amount_total"], 10.05)
        self.assertAlmostEqual(totals["rounding_amount"], 0.02)
        self.assertIn("₹", totals["formatted_rounding_amount"])
        self.assertIn("₹", totals["formatted_amount_total"])
        self.assertEqual((move.currency_id, move.invoice_line_ids.price_unit), (usd, 10.03))
