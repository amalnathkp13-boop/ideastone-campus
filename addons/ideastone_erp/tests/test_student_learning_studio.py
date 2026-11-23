import copy

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..models.student_learning_studio import MAX_FILE, LearningRevisionConflict
from .test_owner_mvp import OwnerMVPFixture


@tagged("post_install", "-at_install")
class TestStudentLearningStudio(OwnerMVPFixture, TransactionCase):
    def setUp(self):
        super().setUp()
        self.student = self.enrolled().student_id
        self.other = self.enrolled().student_id
        self.user = new_test_user(self.env, login="learning_studio_student", groups="base.group_portal", partner_id=self.student.partner_id.id)
        self.other_user = new_test_user(self.env, login="learning_studio_other", groups="base.group_portal", partner_id=self.other.partner_id.id)
        self.student.user_id, self.other.user_id = self.user, self.other_user
        self.portal = self.env["campus.student.portal"].with_user(self.user)
        self.other_portal = self.env["campus.student.portal"].with_user(self.other_user)

    def test_progress_persists_with_identity_and_revision_boundaries(self):
        initial = self.portal._learning_snapshot()
        state = initial["state"]
        self.assertEqual(state["done"], {"ds": [], "db": [], "dl": []})
        state.update(name="Different learner", anchor="1999-01-01")
        state["notes"]["ds-0"] = "A private note <script>not executable</script>"
        state["done"]["ds"] = [0, 5]
        saved = self.portal._learning_save(state, initial["revision"])
        self.assertEqual(saved["state"]["name"], self.student.name)
        self.assertEqual(saved["state"]["anchor"], self.today.isoformat())
        self.assertEqual(saved["state"]["done"]["ds"], [0])
        self.assertEqual(self.portal._learning_snapshot()["state"]["notes"], state["notes"])
        self.assertFalse(self.other_portal._learning_snapshot()["state"]["notes"])
        with self.assertRaises(LearningRevisionConflict):
            self.portal._learning_save(state, initial["revision"])
        with self.assertRaises(AccessError):
            self.env["campus.student.learning.state"].with_user(self.user).search([])
        with self.assertRaises(AccessError):
            self.portal.with_user(self.owner)._learning_snapshot()
        self.student.write({"active": False, "campus_status_reason": "Testing an inactive learning account"})
        with self.assertRaises(AccessError):
            self.portal._learning_snapshot()

    def test_assessment_scores_are_recomputed_and_submissions_remain_fixed(self):
        initial = self.portal._learning_snapshot()
        state = initial["state"]
        state["attempts"]["ds"] = [{"answers": [1, 0, 2], "score": 99, "ts": 1}]
        state["testAttempts"]["ds-fundamentals"] = {"answers": [0, 0, 0], "score": 99, "total": 99, "ts": 2}
        state["submissions"]["ds"] = {"text": "My traversal reasoning", "ts": 3}
        saved = self.portal._learning_save(state, initial["revision"])
        self.assertEqual(saved["state"]["attempts"]["ds"][0]["score"], 3)
        self.assertEqual(saved["state"]["testAttempts"]["ds-fundamentals"]["score"], 1)
        self.assertEqual(saved["state"]["testAttempts"]["ds-fundamentals"]["total"], 3)
        self.assertEqual(saved["state"]["done"]["ds"], [4, 5])
        changed = copy.deepcopy(saved["state"])
        changed["testAttempts"]["ds-fundamentals"]["answers"] = [1, 0, 2]
        with self.assertRaises(ValidationError):
            self.portal._learning_save(changed, saved["revision"])
        changed = copy.deepcopy(saved["state"])
        changed["testAttempts"]["ds-applications"] = {"answers": [1, 0, 2], "score": 3, "ts": 4}
        with self.assertRaises(ValidationError):
            self.portal._learning_save(changed, saved["revision"])
        changed = copy.deepcopy(saved["state"])
        changed["submissions"]["ds"]["text"] = "Replaced"
        with self.assertRaises(ValidationError):
            self.portal._learning_save(changed, saved["revision"])

    def test_invalid_payload_and_booking_clash_are_rejected(self):
        initial = self.portal._learning_snapshot()
        for mutation in ({"done": {"ds": [True]}}, {"notes": {"ds-0": "x" * 6001}},
                         {"enrolled": ["unknown"]}, {"student_id": self.other.id},
                         {"drafts": {"quiz-ds": [1, 7, None]}},
                         {"bookings": {"ds": {"off": 1, "time": "15:00"}, "db": {"off": 1, "time": "15:00"}}}):
            state = copy.deepcopy(initial["state"])
            state.update(mutation)
            with self.assertRaises(ValidationError):
                self.portal._learning_save(state, initial["revision"])
        with self.assertRaises(ValidationError):
            self.portal._learning_save(initial["state"], True)

    def test_private_files_are_scoped_and_size_limited(self):
        record = self.portal._learning_add_file(b"private study note", "note.txt")
        self.assertEqual(self.portal._learning_download_file(record["id"]), (b"private study note", "note.txt", "application/octet-stream"))
        self.assertEqual(len(self.portal._learning_files()), 1)
        self.assertFalse(self.other_portal._learning_files())
        for method in (self.other_portal._learning_download_file, self.other_portal._learning_delete_file):
            with self.assertRaises(AccessError):
                method(record["id"])
        with self.assertRaises(AccessError):
            self.env["campus.student.learning.file"].with_user(self.user).browse(int(record["id"])).read(["data"])
        for raw, name in ((b"x" * (MAX_FILE + 1), "large.txt"), (b"", "empty.txt"), (b"x", "../note.txt")):
            with self.assertRaises(ValidationError):
                self.portal._learning_add_file(raw, name)
        self.portal._learning_delete_file(record["id"])
        self.assertFalse(self.portal._learning_files())
        for index in range(20):
            self.portal._learning_add_file(b"small note", f"note-{index}.txt")
        with self.assertRaises(ValidationError):
            self.portal._learning_add_file(b"another note", "over-quota.txt")
        with self.assertRaises(AccessError):
            self.portal._learning_download_file(2**100)
