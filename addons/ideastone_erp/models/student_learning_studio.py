"""Private, personal Learning Studio records; these are not official exam results."""

import base64
import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import file_open

from odoo import _, fields, models

COURSES = ("ds", "db", "dl", "net")
MAX_FILE = 16 * 1024 * 1024
MAX_STORAGE = 64 * 1024 * 1024
MAX_STATE = 512 * 1024


class LearningRevisionConflict(UserError):
    """The client must reload before replacing newer learning progress."""


@lru_cache(maxsize=1)
def _catalog():
    with file_open("ideastone_erp/static/src/learning_studio/catalog.json", "r") as source:
        return {course["id"]: course for course in json.load(source)}


def _invalid():
    raise ValidationError(_("The learning record is invalid. Reload the workspace and try again."))


def _text(value, maximum):
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        _invalid()
    return value


def _integer(value, low=0, high=2**53 - 1):
    if type(value) is not int or not low <= value <= high:
        _invalid()
    return value


def _mapping(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        _invalid()
    return value


def _list(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        _invalid()
    return value


def _course_list(value, allowed=COURSES):
    values = _list(value, len(allowed))
    if any(not isinstance(item, str) or item not in allowed for item in values) or len(values) != len(set(values)):
        _invalid()
    return values


def _fresh(student):
    return {
        "name": student.name, "anchor": fields.Date.context_today(student).isoformat(),
        "enrolled": list(COURSES[:3]), "done": {course: [] for course in COURSES[:3]},
        "last": ["ds", 0], "stars": [], "answers": {}, "notes": {}, "drafts": {},
        "submissions": {}, "attempts": {}, "testAttempts": {}, "posts": [],
        "bookings": {}, "noticed": False, "files": [], "saved": [],
    }


def _validate_state(payload, previous, student):
    if not isinstance(payload, dict):
        _invalid()
    try:
        if len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()) > MAX_STATE:
            raise ValidationError(_("Your learning record is too large to save. Shorten your notes or drafts."))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationError(_("The learning record is not valid JSON.")) from exc
    state = _fresh(student)
    _mapping(payload, set(state) | {"updated", "exported"})
    state.update(copy.deepcopy(payload))
    state.pop("exported", None)
    state["name"] = student.name  # The portal identity is never supplied by the browser.
    state["anchor"] = previous["anchor"]
    state["files"] = []  # Files have a separate, access-checked storage endpoint.
    enrolled = _course_list(state["enrolled"])
    if not set(previous["enrolled"]).issubset(enrolled):
        _invalid()
    state["stars"] = _course_list(state["stars"], enrolled)
    state["saved"] = _course_list(state["saved"], enrolled)
    last = _list(state["last"], 2)
    if len(last) != 2 or not isinstance(last[0], str) or last[0] not in enrolled:
        _invalid()
    _integer(last[1], 0, 5)
    if type(state["noticed"]) is not bool:
        _invalid()
    for values in _mapping(state["done"], enrolled).values():
        values = _list(values, 6)
        if len(set(_integer(index, 0, 5) for index in values)) != len(values):
            _invalid()
    for answer in _mapping(state["answers"], enrolled).values():
        _integer(answer, 0, 2)
    note_keys = {f"{course}-{index}" for course in enrolled for index in range(6)}
    for note in _mapping(state["notes"], note_keys).values():
        _text(note, 6000)
    draft_keys = {f"{kind}-{course}" for course in enrolled for kind in ("task", "post", "quiz")}
    draft_keys |= {f"test-{course}-{kind}" for course in enrolled for kind in ("fundamentals", "applications")}
    for key, draft in _mapping(state["drafts"], draft_keys).items():
        if key.startswith(("quiz-", "test-")):
            answers = _list(draft, 3)
            if len(answers) != 3:
                _invalid()
            for answer in answers:
                if answer is not None:
                    _integer(answer, 0, 2)
        else:
            _text(draft, 12000 if key.startswith("task-") else 4000)
    for submission in _mapping(state["submissions"], enrolled).values():
        _mapping(submission, {"text", "ts"})
        if not _text(submission.get("text"), 12000).strip():
            _invalid()
        _integer(submission.get("ts"))
    for course, old in previous.get("submissions", {}).items():
        if state["submissions"].get(course) != old:
            raise ValidationError(_("A submitted practice assignment cannot be replaced by an older draft."))
    catalog = _catalog()
    for course, attempts in _mapping(state["attempts"], enrolled).items():
        for attempt in _list(attempts, 100):
            _score_attempt(attempt, catalog[course]["quiz"])
        old = previous.get("attempts", {}).get(course, [])
        if attempts[:len(old)] != old:
            raise ValidationError(_("Previously submitted practice attempts must remain in your learning history."))
    if set(previous.get("attempts", {})) - set(state["attempts"]):
        _invalid()
    test_ids = {f"{course}-{kind}" for course in enrolled for kind in ("fundamentals", "applications")}
    today = fields.Date.context_today(student)
    anchor = date.fromisoformat(state["anchor"])
    for key, attempt in _mapping(state["testAttempts"], test_ids).items():
        course, kind = key.split("-", 1)
        questions = catalog[course]["quiz"]
        if kind == "applications":
            questions = [catalog[course]["practice"], questions[1], questions[2]]
        _score_attempt(attempt, questions, scheduled=True)
        old = previous.get("testAttempts", {}).get(key)
        if old and attempt != old:
            raise ValidationError(_("This practice test has already been submitted."))
        if not old:
            opens, closes = (-1, 7) if kind == "fundamentals" else (4, 12)
            if not anchor + timedelta(days=opens) <= today <= anchor + timedelta(days=closes):
                raise ValidationError(_("This practice test is outside its submission period."))
    if set(previous.get("testAttempts", {})) - set(state["testAttempts"]):
        _invalid()
    for post in _list(state["posts"], 200):
        _mapping(post, {"name", "c", "text", "ts"})
        if post.get("c") not in enrolled or not _text(post.get("text"), 4000).strip():
            _invalid()
        _integer(post.get("ts"))
        post["name"] = student.name
    slots = set()
    for course, booking in _mapping(state["bookings"], enrolled).items():
        _mapping(booking, {"off", "time"})
        slot = (_integer(booking.get("off"), 1, 3), _text(booking.get("time"), 5))
        if slot not in {(1, "15:00"), (2, "11:00"), (3, "16:00")} or slot in slots:
            raise ValidationError(_("Choose an available, non-overlapping practice mentoring slot."))
        if previous.get("bookings", {}).get(course) != booking and anchor + timedelta(days=slot[0]) < today:
            raise ValidationError(_("Choose a practice mentoring date that has not passed."))
        slots.add(slot)
    # Completion of an assessed activity follows its saved evidence, not a supplied badge.
    for course in enrolled:
        completed = [item for item in state["done"].get(course, []) if item < 3]
        if state["answers"].get(course) == catalog[course]["practice"][2]:
            completed.append(3)
        if state["attempts"].get(course):
            completed.append(4)
        if state["submissions"].get(course):
            completed.append(5)
        state["done"][course] = sorted(completed)
    state["updated"] = int(datetime.now(timezone.utc).timestamp() * 1000)
    return state


def _score_attempt(attempt, questions, scheduled=False):
    _mapping(attempt, {"answers", "score", "total", "ts"})
    answers = _list(attempt.get("answers"), len(questions))
    if len(answers) != len(questions):
        _invalid()
    for answer in answers:
        _integer(answer, 0, 2)
    _integer(attempt.get("ts"))
    attempt["score"] = sum(answer == question[2] for answer, question in zip(answers, questions, strict=True))
    if scheduled:
        attempt["total"] = len(questions)
    else:
        attempt.pop("total", None)


class StudentLearningState(models.Model):
    _name = "campus.student.learning.state"
    _description = "Private student self-study record"
    _rec_name = "student_id"

    student_id = fields.Many2one("op.student", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="student_id.company_id", store=True, index=True)
    state = fields.Json(required=True, copy=False)
    revision = fields.Integer(default=0, required=True, copy=False)

    _sql_constraints = [("student_unique", "unique(student_id)", "Each student has one Learning Studio record.")]


class StudentLearningFile(models.Model):
    _name = "campus.student.learning.file"
    _description = "Private Learning Studio file"
    _order = "create_date desc, id desc"

    student_id = fields.Many2one("op.student", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="student_id.company_id", store=True, index=True)
    name = fields.Char(required=True)
    data = fields.Binary(required=True, attachment=True)
    size = fields.Integer(required=True)


class StudentLearningPortal(models.AbstractModel):
    _inherit = "campus.student.portal"

    def snapshot(self, enrolment=None, date_from=None, date_to=None):
        result = super().snapshot(enrolment, date_from, date_to)
        navigation = result["navigation"]
        if not any(item[0] == "lms" for item in navigation):
            index = next((i + 1 for i, item in enumerate(navigation) if item[0] == "academics"), len(navigation))
            navigation.insert(index, ("lms", "LMS", "graduation-cap"))
        return result

    def _learning_record(self, student):
        # Lock the student as well as the state so two first visits cannot create duplicate records.
        self.env.cr.execute("SELECT id FROM op_student WHERE id = %s FOR UPDATE", [student.id])
        record = self.env["campus.student.learning.state"].sudo().search([("student_id", "=", student.id)], limit=1)
        if not record:
            record = record.create({"student_id": student.id, "state": _fresh(student)})
        record.invalidate_recordset()
        return record

    def _learning_snapshot(self):
        student = self._identity()
        record = self._learning_record(student)
        state = copy.deepcopy(record.state)
        state["name"] = student.name
        return {"state": state, "revision": record.revision,
                "student": {"id": student.id, "name": student.name, "number": student.gr_no or ""}}

    def _learning_save(self, state, revision):
        student = self._identity()
        _integer(revision, 0, 2**31 - 1)
        record = self._learning_record(student)
        if revision != record.revision:
            raise LearningRevisionConflict(_("Your learning record changed in another tab. Reload before saving to protect the newer progress."))
        clean = _validate_state(state, record.state, student)
        record.write({"state": clean, "revision": record.revision + 1})
        return {"state": clean, "revision": record.revision}

    def _learning_files(self):
        student = self._identity()
        records = self.env["campus.student.learning.file"].sudo().search([("student_id", "=", student.id)])
        return [self._learning_file_metadata(record) for record in records]

    def _learning_file_metadata(self, record):
        return {"id": str(record.id), "name": record.name, "size": record.size,
                "ts": int(record.create_date.replace(tzinfo=timezone.utc).timestamp() * 1000)}

    def _learning_add_file(self, raw, filename):
        student = self._identity()
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_FILE:
            raise ValidationError(_("Choose a non-empty file up to 16 MB."))
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 200 or re.search(r"[/\\\x00-\x1f\x7f]", filename):
            raise ValidationError(_("Choose a file with a valid filename of at most 200 characters."))
        self.env.cr.execute("SELECT id FROM op_student WHERE id = %s FOR UPDATE", [student.id])
        files = self.env["campus.student.learning.file"].sudo().search([("student_id", "=", student.id)])
        if len(files) >= 20 or sum(files.mapped("size")) + len(raw) > MAX_STORAGE:
            raise ValidationError(_("Private files are limited to 20 files and 64 MB. Remove an unused file before uploading."))
        record = files.create({"student_id": student.id, "name": filename.strip(), "size": len(raw), "data": base64.b64encode(raw)})
        return self._learning_file_metadata(record)

    def _learning_file_record(self, record_id):
        student = self._identity()
        try:
            record_id = int(record_id)
        except (TypeError, ValueError) as exc:
            raise AccessError(_("This private file is not available.")) from exc
        if not 0 < record_id < 2**31:
            raise AccessError(_("This private file is not available."))
        record = self.env["campus.student.learning.file"].sudo().search([
            ("id", "=", record_id), ("student_id", "=", student.id)], limit=1)
        if not record:
            raise AccessError(_("This private file is not available."))
        return record

    def _learning_download_file(self, record_id):
        record = self._learning_file_record(record_id)
        return base64.b64decode(record.data), record.name, "application/octet-stream"

    def _learning_delete_file(self, record_id):
        return self._learning_file_record(record_id).unlink()
