import base64
import csv
import hashlib
import io
import json

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class StudentImport(models.TransientModel):
    _name = "campus.student.import"
    _description = "Preview and validate a student CSV before importing"
    _inherit = "campus.mvp.mixin"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    file = fields.Binary(required=True)
    filename = fields.Char()
    mapping = fields.Text(required=True, default='{"number":"student_number","first":"first_name","last":"last_name","phone":"phone","section":"section_code"}',
                          help="JSON mapping from number, first, last, phone, section to CSV column headers.")
    preview = fields.Text(readonly=True)
    checksum = fields.Char(readonly=True)
    committed = fields.Boolean(readonly=True)

    def _validated_rows(self):
        self.ensure_one()
        self._mvp_require("ideastone_erp.group_mvp_registrar")
        self._mvp_company()
        try:
            raw = base64.b64decode(self.file)
            if len(raw) > 2_000_000:
                raise ValidationError(_("Import at most 2 MB per file."))
            mapping = json.loads(self.mapping)
            if not isinstance(mapping, dict) or set(mapping) != {"number", "first", "last", "phone", "section"} or any(not isinstance(header, str) or not header.strip() for header in mapping.values()):
                raise ValueError()
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if not reader.fieldnames or any(header not in reader.fieldnames for header in mapping.values()):
                raise ValidationError(_("Map every field to an existing CSV column header."))
            rows, errors, seen = [], [], set()
            for index, source in enumerate(reader, 2):
                if index > 1001:
                    raise ValidationError(_("Preview at most 1,000 students at a time."))
                row = {key: (source.get(header) or "").strip() for key, header in mapping.items()}
                if not row["number"] or not row["first"] or not row["section"]:
                    errors.append("Row %s: student number, first name and section are required." % index)
                if row["number"] in seen or self.env["op.student"].with_context(active_test=False).search_count([("gr_no", "=", row["number"])]):
                    errors.append("Row %s: duplicate student number %s." % (index, row["number"]))
                seen.add(row["number"])
                section = self.env["op.batch"].search([("code", "=", row["section"]), ("company_id", "=", self.company_id.id)], limit=1)
                if not section or not section.campus_year_id:
                    errors.append("Row %s: configure this college's section and academic year first." % index)
                row["section_id"] = section.id
                rows.append(row)
            if not rows:
                errors.append("The CSV has no student rows.")
        except (ValueError, UnicodeError, csv.Error) as exc:
            raise ValidationError(_("Use a UTF-8 CSV and valid JSON column mapping.")) from exc
        digest = hashlib.sha256(raw + self.mapping.encode() + str(self.company_id.id).encode()).hexdigest()
        return rows, errors, digest

    def action_preview(self):
        rows, errors, digest = self._validated_rows()
        super().write({"preview": "\n".join(errors) if errors else "%s valid rows. No changes saved.\n%s" % (len(rows), "\n".join("%s — %s %s — %s" % (r["number"], r["first"], r["last"], r["section"]) for r in rows[:30])),
                       "checksum": False if errors else digest})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "current"}

    def action_commit(self):
        self._mvp_lock()
        if self.committed:
            return True
        rows, errors, digest = self._validated_rows()
        if errors or not self.checksum or self.checksum != digest:
            raise ValidationError(_("Preview and resolve all row errors before importing the unchanged file."))
        # One transaction: a failing row rolls back partners, students and enrolments.
        with self.env.cr.savepoint():
            for row in rows:
                section = self.env["op.batch"].browse(row["section_id"])
                partner = self.env["res.partner"].create({"name": (row["first"] + " " + row["last"]).strip(), "phone": row["phone"], "company_id": self.company_id.id})
                student = self.env["op.student"].create({"partner_id": partner.id, "gr_no": row["number"], "first_name": row["first"], "last_name": row["last"], "gender": "o"})
                self.env["op.student.course"].create({"student_id": student.id, "batch_id": section.id, "course_id": section.course_id.id,
                    "academic_years_id": section.campus_year_id.id, "academic_term_id": section.campus_term_id.id})
            super().write({"committed": True, "preview": "Imported %s students and enrolments." % len(rows)})
            self._mvp_log("Student CSV imported", details={"rows": len(rows), "sha256": digest})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(set(v).intersection({"preview", "checksum", "committed"}) for v in vals_list):
            raise AccessError(_("Import verification evidence is maintained by preview and commit."))
        return super().create(vals_list)

    def write(self, vals):
        if self.committed or {"preview", "checksum", "committed"}.intersection(vals):
            raise AccessError(_("Import verification evidence cannot be changed manually."))
        return super().write(vals)
