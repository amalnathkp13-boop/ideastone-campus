from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestFacultyCommunication(OwnerMVPFixture, TransactionCase):
    def test_faculty_records_persist_and_stay_in_their_college(self):
        service = self.env["campus.faculty.communication"].with_user(self.teacher)
        native = self.env["survey.survey"].create({"title": "Native communication survey", "user_id": self.teacher.id})
        self.assertIn(f"native-survey-{native.id}", [row["id"] for row in service.get_data()["rows"]["surveys"]])
        before = len(service.get_data()["rows"]["surveys"])
        values = {"name": "Teaching feedback", "owner": "MVP Faculty", "date": str(self.today),
                  "status": "Draft", "description": "Synthetic test survey."}
        record_id = service.create_record("surveys", values)
        self.assertIn(record_id, [row["id"] for row in service.get_data()["rows"]["surveys"]])
        self.assertEqual(len(service.get_data()["rows"]["surveys"]), before + 1)
        self.assertEqual(self.env["campus.faculty.communication.record"].browse(record_id).created_by, self.teacher)
        with self.assertRaises(ValidationError):
            service.create_record("surveys", dict(values, status="Ended"))
        with self.assertRaises(AccessError):
            self.env["campus.faculty.communication"].with_user(self.outsider).get_data()
        other = self.env["res.company"].create({"name": "Other communication college"})
        self.env["campus.faculty.communication.record"].create(dict(values, kind="surveys", company_id=other.id, created_by=self.teacher.id))
        self.assertEqual(len(service.get_data()["rows"]["surveys"]), before + 1)
