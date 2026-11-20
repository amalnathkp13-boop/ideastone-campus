"""Load the supplied Learning Studio example into the disposable localhost preview."""
import json
import os

from odoo.tools import file_open

assert env.cr.dbname == "student_learning_studio_preview", "Preview database only"  # noqa: F821
student = env["op.student"].search([("user_id.login", "=", "student@openeducat.com")], limit=1)  # noqa: F821
assert student and student.user_id
student.user_id.with_context(no_reset_password=True).write({"password": os.environ["LMS_PREVIEW_PASSWORD"]})
student.company_id.campus_demo = True
service = env["campus.student.portal"].with_user(student.user_id)  # noqa: F821
snapshot = service._learning_snapshot()
if not snapshot["revision"]:
    with file_open("ideastone_erp/static/src/learning_studio/sample_state.json", "r") as source:
        example = json.load(source)
    service._learning_save(example, snapshot["revision"])
if not service._learning_files():
    service._learning_add_file(b"Learning Studio sample notes\nReview binary search trees before the practice quiz.\n", "Study notes.txt")
env.cr.commit()  # noqa: F821
print("Learning Studio preview ready for", student.user_id.login)
