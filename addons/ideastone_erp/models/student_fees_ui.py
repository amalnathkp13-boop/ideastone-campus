from datetime import datetime

from odoo import api, models


class StudentFeesUI(models.AbstractModel):
    _inherit = "campus.student.portal"

    @api.model
    def _fee_ui_projection(self, fees):
        """Present only the ledger and receipts already scoped by the portal."""
        invoices = []
        for source in fees["invoices"]:
            row = dict(source)
            row["status"] = "Paid" if row["balance"] <= 0 else "Partially paid" if row["paid"] > 0 else "Outstanding"
            row["tone"] = "good" if row["balance"] <= 0 else "bad" if row["overdue"] else "warn"
            row["progress"] = min(100, max(0, row["paid"] * 100 / row["total"])) if row["total"] else 0
            invoices.append(row)
        def due_key(row):
            return datetime.strptime(row["due_date"], "%d %b %Y") if row["due_date"] else datetime.max
        dues = sorted([row for row in invoices if row["balance"] > 0], key=due_key)
        methods = {"cash": "Cash", "bank": "Bank transfer", "upi": "UPI", "card": "Card", "other": "Other"}
        payments = [dict(row, method_label=methods.get(row["method"], row["method"] or "Not recorded")) for row in fees["payments"]]
        posted = [row for row in payments if row["status"] == "Posted"]
        return {"invoices": invoices, "dues": dues, "next_due": (dues[0]["due_date"] or "Not assigned") if dues else "No dues" if fees["recorded"] else "Not recorded",
                "status": "Not recorded" if not fees["recorded"] else "Paid" if fees["due"] <= 0 else "Partially paid" if fees["paid"] > 0 else "Outstanding",
                "tone": "neutral" if not fees["recorded"] else "good" if fees["due"] <= 0 else "warn",
                "periods": sorted({row["year"] for row in invoices}), "payments": payments,
                "methods": sorted({row["method_label"] for row in payments}), "posted_count": len(posted),
                "posted_total": sum(row["amount"] for row in posted), "adjustments": [row for row in invoices if row["concession"] > 0],
                "concession": sum(row["concession"] for row in invoices)}

    @api.model
    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        data = super().snapshot(enrolment, date_from, date_to)
        data["fee_ui"] = self._fee_ui_projection(data["fees"])
        return data
