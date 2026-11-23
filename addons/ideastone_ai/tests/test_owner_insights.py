from unittest.mock import patch

from odoo.addons.ideastone_erp.tests.test_owner_mvp import OwnerMVPFixture
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOwnerAIInsights(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.insights = self.env["campus.owner.ai.insights"].with_user(self.owner)

    def assessment(self, student_id, department_id=1):
        return {
            "id": student_id, "name": f"Student {student_id}", "department_id": department_id,
            "department": f"Department {department_id}", "band": "watch", "score": 30,
            "provisional": False, "mentor_id": self.owner.id, "mentor": self.owner.name,
            "action": "Arrange a mentor follow-up.",
            "attendance": {"rate": 70, "threshold": 75},
            "academics": {"exams": 1}, "fees": {"overdue": 100},
            "engagement": {"overdue_follow_up": 1},
            "factors": [{"key": "attendance", "points": 20}, {"key": "fees", "points": 10}],
        }

    def test_all_students_and_department_filter_are_aggregated_before_limit(self):
        rows = [self.assessment(index) for index in range(1, 502)]
        rows.append(self.assessment(502, department_id=2))
        with patch.object(type(self.env["campus.success.radar"]), "_assessment_rows",
                          return_value=("owner", self.today, rows)):
            all_data = self.insights.get_overview()
            self.assertEqual(all_data["summary"]["students"], 502)
            self.assertEqual(all_data["summary"]["attention"], 502)
            self.assertEqual(all_data["summary"]["overdue_amount"], 50200)
            self.assertEqual(len(all_data["priorities"]), 8)
            self.assertEqual(all_data["factors"][0]["count"], 502)
            self.assertEqual(all_data["factors"][2]["count"], 502)
            selected = self.insights.get_overview("2")
            self.assertEqual(selected["summary"]["students"], 1)
            self.assertEqual(selected["summary"]["watch"], 1)
            self.assertEqual(selected["summary"]["overdue_amount"], 100)
            self.assertEqual([row["id"] for row in selected["priorities"]], [502])
            self.assertEqual([row["id"] for row in selected["department_summaries"]], [2])
            self.assertEqual(len(selected["departments"]), 2)
            self.assertTrue(all(row["recorded"] == row["total"] == 1 for row in selected["coverage"]))
            with self.assertRaises(AccessError):
                self.insights.get_overview(999)

    def test_missing_records_are_reported_as_coverage_gaps(self):
        row = self.assessment(1)
        row.update(provisional=True, mentor_id=0, mentor="", score=0, band="low", factors=[])
        row["attendance"]["rate"] = None
        row["academics"]["exams"] = 0
        row["fees"]["overdue"] = 0
        row["engagement"]["overdue_follow_up"] = 0
        with patch.object(type(self.env["campus.success.radar"]), "_assessment_rows",
                          return_value=("owner", self.today, [row])):
            data = self.insights.get_overview()
        self.assertEqual(data["summary"]["attention"], 0)
        self.assertEqual(data["summary"]["attendance_below"], 0)
        self.assertEqual(data["summary"]["provisional"], 1)
        self.assertEqual(data["summary"]["missing_results"], 1)
        self.assertEqual(data["summary"]["missing_mentor"], 1)
        self.assertFalse(data["priorities"])
        self.assertTrue(all(row["recorded"] == 0 and row["total"] == 1 for row in data["coverage"]))

    def test_owner_permission_and_current_college_scope(self):
        student = self.enrolled().student_id
        data = self.insights.get_overview()
        self.assertEqual(data["summary"]["students"], 1)
        self.assertEqual(data["company"], student.company_id.name)
        other_college = self.env["res.company"].create({"name": "Other insights college"})
        self.owner.company_ids |= other_college
        self.assertEqual(self.insights.with_company(other_college).get_overview()["summary"]["students"], 0)
        for user in (self.teacher, self.outsider, self.accountant):
            with self.assertRaises(AccessError):
                self.insights.with_user(user).get_overview()
        for value in (True, -1, "invalid", [], 1.5):
            with self.assertRaises(ValidationError):
                self.insights.get_overview(value)
