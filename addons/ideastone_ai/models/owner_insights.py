"""Owner insights aggregated from the existing student assessment rules."""

from collections import Counter

from odoo.addons.ideastone_erp.models.owner_attendance_ui import owner_access
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class OwnerAIInsights(models.AbstractModel):
    _name = "campus.owner.ai.insights"
    _description = "Owner AI insights overview"

    @api.model
    def get_overview(self, department_id=None):
        owner_access(self.env)
        if not self.env.user.active:
            raise AccessError(_("An active owner account is required."))
        try:
            selected = int(department_id or 0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError(_("Choose a valid department.")) from exc
        if isinstance(department_id, bool) or not isinstance(department_id, (int, str, type(None))) or selected < 0:
            raise ValidationError(_("Choose a valid department."))

        _role, today, all_rows = self.env["campus.success.radar"]._assessment_rows()
        departments = sorted(
            {row["department_id"]: row["department"] for row in all_rows if row["department_id"]}.items(),
            key=lambda item: item[1],
        )
        if selected and selected not in dict(departments):
            raise AccessError(_("Choose a department available in the active college."))
        rows = [row for row in all_rows if row["department_id"] == selected] if selected else all_rows
        bands = Counter(row["band"] for row in rows)
        factor_counts = Counter(factor["key"] for row in rows for factor in row["factors"])
        total = len(rows)
        money = self.env.company.currency_id.round

        def attendance_below(row):
            attendance = row["attendance"]
            return attendance["rate"] is not None and attendance["rate"] < attendance["threshold"]

        summary = {
            "students": total,
            "high": bands["high"],
            "watch": bands["watch"],
            "attention": bands["high"] + bands["watch"],
            "attendance_below": sum(attendance_below(row) for row in rows),
            "overdue_amount": money(sum(row["fees"]["overdue"] for row in rows)),
            "overdue_students": sum(row["fees"]["overdue"] > 0 for row in rows),
            "followups": sum(bool(row["engagement"]["overdue_follow_up"]) for row in rows),
            "provisional": sum(row["provisional"] for row in rows),
            "missing_results": sum(not row["academics"]["exams"] for row in rows),
            "missing_mentor": sum(not row["mentor_id"] for row in rows),
        }
        grouped = {}
        for row in rows:
            department = grouped.setdefault(row["department_id"], {
                "id": row["department_id"], "name": row["department"] or _("Unassigned department"),
                "students": 0, "high": 0, "watch": 0, "attendance_below": 0, "overdue_amount": 0,
            })
            department["students"] += 1
            department["high"] += row["band"] == "high"
            department["watch"] += row["band"] == "watch"
            department["attendance_below"] += attendance_below(row)
            department["overdue_amount"] += row["fees"]["overdue"]
        for department in grouped.values():
            department["overdue_amount"] = money(department["overdue_amount"])
        priorities = sorted(
            (row for row in rows if row["band"] in {"high", "watch"}),
            key=lambda row: (-row["score"], row["name"], row["id"]),
        )[:8]
        return {
            "company": self.env.company.name,
            "today": fields.Date.to_string(today),
            "updated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "threshold": self.env.company.campus_attendance_threshold,
            "currency_symbol": "₹",
            "currency_code": self.env.company.currency_id.name,
            "department_id": selected,
            "departments": [{"id": key, "name": name} for key, name in departments],
            "summary": summary,
            "department_summaries": sorted(grouped.values(), key=lambda row: (-row["high"], -row["watch"], row["name"])),
            "priorities": [{key: row[key] for key in
                ("id", "name", "department", "score", "band", "action", "factors", "mentor")} for row in priorities],
            "factors": [{"key": key, "label": label, "count": factor_counts[key]} for key, label in (
                ("attendance", _("Attendance")), ("academics", _("Results")),
                ("fees", _("Overdue fees")), ("engagement", _("Engagement")),
            )],
            "coverage": [
                {"key": "attendance", "label": _("Attendance history"), "recorded": total - summary["provisional"],
                 "total": total, "detail": _("Students with at least five recorded eligible classes")},
                {"key": "results", "label": _("Exam results"), "recorded": total - summary["missing_results"],
                 "total": total, "detail": _("Students with at least one completed exam result")},
                {"key": "mentor", "label": _("Assigned mentors"), "recorded": total - summary["missing_mentor"],
                 "total": total, "detail": _("Students with an active mentor routing")},
            ],
            "assistant": self.env["campus.ai.assistant"].get_status(),
        }
