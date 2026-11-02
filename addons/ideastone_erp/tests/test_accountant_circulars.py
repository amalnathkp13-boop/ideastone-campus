from datetime import timedelta

from freezegun import freeze_time
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo import fields

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestAccountantFeeCirculars(OwnerMVPFixture, TransactionCase):
    def payload(self, **changes):
        return {"name": "Semester fee notification", "body": "Pay the fee through the college portal.",
            "category": "fees", "audience": "student", "scope": "all", "effective_from": str(self.today),
            "due_date": str(self.today + timedelta(days=10)), "status": "draft", **changes}

    def service(self):
        return self.env["campus.dashboard"].with_user(self.accountant)

    def row(self, notice_id):
        return next(row for row in self.service().get_fee_circulars()["rows"] if row["id"] == notice_id)

    def test_draft_persistence_publication_archive_and_stale_edit(self):
        service = self.service()
        message = "Pay <fee> & save the receipt.\nContact accounts for help."
        notice_id = service.save_fee_circular(self.payload(category="exam", body=message))
        notice = self.env["campus.circular"].browse(notice_id)
        row = self.row(notice_id)
        self.assertTrue(row["reference"].startswith("FC/"))
        self.assertEqual(notice.campus_category, "Fees")
        self.assertEqual(row["category_label"], "Examination")
        self.assertEqual(row["body"], message)
        service.save_fee_circular(self.payload(name="Updated fee deadline", category="exam", updated=row["updated"]), notice_id)
        self.assertEqual(notice.name, "Updated fee deadline")
        with self.assertRaises(ValidationError):
            service.save_fee_circular(self.payload(updated="stale"), notice_id)
        latest = self.row(notice_id)
        service.save_fee_circular(self.payload(status="published", updated=latest["updated"]), notice_id)
        self.assertEqual(notice.campus_status, "published")
        with self.assertRaises(ValidationError):
            notice.with_user(self.accountant).write({"body": "<p>Overwrite a release</p>"})
        self.env["campus.student.notice.read"].create({"student_id": self.enrolled().student_id.id, "notice_id": notice.id})
        self.assertEqual(self.row(notice_id)["student_reads"], 1)
        service.archive_fee_circular(notice_id)
        self.assertEqual(self.row(notice_id)["status"], "archived")

    def test_same_day_schedule_and_portal_department_scope(self):
        self.accountant.tz = "UTC"
        now = fields.Datetime.now()
        student = self.enrolled().student_id
        service = self.service()
        notice_id = service.save_fee_circular(self.payload(audience="student_parent", scope=str(self.department.id),
            status="scheduled", publish_at=(now + timedelta(hours=2)).isoformat(timespec="minutes")))
        notice = self.env["campus.circular"].browse(notice_id)
        self.assertEqual(notice.campus_status, "scheduled")
        self.env["campus.circular"]._cron_publish_notices()
        self.assertEqual(notice.campus_status, "scheduled")
        with freeze_time(now + timedelta(hours=3)):
            self.env["campus.circular"]._cron_publish_notices()
            self.assertEqual(notice.campus_status, "published")
            for model in ["campus.student.portal", "campus.parent.portal"]:
                self.assertIn(notice, self.env[model]._notice_records(student))
                other_department = self.env["op.department"].create({"name": model, "code": model})
                notice._set_system_values({"fee_department_id": other_department.id})
                self.assertNotIn(notice, self.env[model]._notice_records(student))
                notice._set_system_values({"fee_department_id": self.department.id})

    def test_validation_permissions_and_office_scope(self):
        service = self.service()
        for values in [self.payload(name=""), self.payload(status="scheduled"), self.payload(scope="accounts"),
                       self.payload(scope="not-a-department"), self.payload(due_date=str(self.today - timedelta(days=1))),
                       self.payload(category="Academic")]:
            with self.assertRaises(ValidationError):
                service.save_fee_circular(values)
        office = service.save_fee_circular(self.payload(audience="faculty", scope="accounts", status="published"))
        self.assertEqual(self.row(office)["scope_label"], "Accounts office")
        self.assertNotIn(self.env["campus.circular"].browse(office),
                         self.env["campus.student.portal"]._notice_records(self.enrolled().student_id))
        with self.assertRaises(AccessError):
            service.with_user(self.outsider).get_fee_circulars()
        other = self.env["res.company"].create({"name": "Other circular college"})
        foreign = self.env["campus.circular"].create({"name": "Private fee notice", "reference": "FOREIGN-FEE",
            "company_id": other.id, "audience": "student", "campus_category": "Fees", "campus_managed": True,
            "body": "<p>Other college</p>", "date_from": self.today})
        with self.assertRaises(AccessError):
            service.archive_fee_circular(foreign.id)
        with self.assertRaises(AccessError):
            self.env["campus.circular"].with_user(self.accountant).create({
                "name": "Academic notice", "reference": "OUTSIDE-FEES", "audience": "student",
                "campus_category": "Academic", "campus_managed": True, "body": "<p>Not a fee circular</p>"})
