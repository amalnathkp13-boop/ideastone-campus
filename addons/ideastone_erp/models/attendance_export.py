import base64
import csv
import hashlib
import io
import json

from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models


class AttendanceExportWizard(models.TransientModel):
    _name = "campus.attendance.export.wizard"
    _description = "Attendance shortage report filters"

    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    course_id = fields.Many2one("op.course", string="Programme")
    batch_id = fields.Many2one("op.batch")
    academic_year = fields.Char(required=True)
    semester = fields.Char(required=True)
    threshold = fields.Float(required=True, default=lambda self: self.env.company.campus_attendance_threshold)

    def _snapshot(self):
        self.ensure_one()
        self.check_access_rights("read")
        self.check_access_rule("read")
        if self.date_from > self.date_to or not 0 <= self.threshold <= 100:
            raise ValidationError(_("Check the report dates and threshold (0–100)."))
        if any(not (value or "").strip() or len(value) > 80 for value in [self.academic_year, self.semester]):
            raise ValidationError(_("Enter academic year and semester labels of at most 80 characters."))
        lines = self.env["op.attendance.line"]
        lines.check_access_rights("read")
        domain = [
            ("attendance_date", ">=", self.date_from), ("attendance_date", "<=", self.date_to),
            ("attendance_id.state", "=", "done"), ("student_id.company_id", "=", self.env.company.id),
            "|", ("attendance_id.session_id", "=", False), ("attendance_id.session_id.state", "!=", "cancel"),
        ]
        if not (self.env.user.has_group("ideastone_erp.group_manager") or
                self.env.user.has_group("openeducat_attendance.group_op_attendance_manager")):
            domain.append(("attendance_id.faculty_id.user_id", "=", self.env.uid))
        if self.course_id:
            domain.append(("course_id", "=", self.course_id.id))
        if self.batch_id:
            domain.append(("batch_id", "=", self.batch_id.id))
        if lines.search_count(domain) > 50000:
            raise ValidationError(_("Select a shorter period or one programme (maximum 50,000 attendance lines)."))
        rows = {}
        for line in lines.search(domain, order="student_id, id"):
            if line.excused and self.env.company.campus_excused_policy == "exclude":
                continue
            key = line.student_id.id
            row = rows.setdefault(key, {"id": key, "register": line.student_id.gr_no or str(key),
                                        "name": line.student_id.name, "sessions": 0, "present": 0})
            row["sessions"] += 1
            row["present"] += int(line.present or line.late or line.excused and self.env.company.campus_excused_policy == "present")
        for row in rows.values():
            row["rate"] = round(row["present"] * 100 / row["sessions"], 1)
            # Compare the actual ratio, so rounding cannot move a student across the threshold.
            row["shortage"] = row["present"] * 100 < self.threshold * row["sessions"]
        snapshot = {"rows": list(rows.values()), "from": str(self.date_from), "to": str(self.date_to),
                    "academic_year": self.academic_year, "semester": self.semester,
                    "programme": self.course_id.name or "All permitted programmes", "batch": self.batch_id.name or "All permitted batches",
                    "threshold": self.threshold, "shortage": sum(r["shortage"] for r in rows.values()),
                    "sessions": sum(r["sessions"] for r in rows.values()), "present": sum(r["present"] for r in rows.values())}
        return self.env["campus.attendance.export"].sudo().create({
            "name": "Attendance shortage report", "company_id": self.env.company.id,
            "user_id": self.env.uid, "snapshot": snapshot,
            "checksum": hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
        })

    def action_pdf(self):
        export = self._snapshot()
        return self.env.ref("ideastone_erp.report_attendance_export").report_action(export, config=False)

    def action_csv(self):
        export = self._snapshot()
        return {"type": "ir.actions.act_url", "url": f"/web/content/campus.attendance.export/{export.id}/csv_file?download=true&filename=Attendance-{export.id}.csv", "target": "self"}


class AttendanceExport(models.Model):
    _name = "campus.attendance.export"
    _description = "Immutable attendance export and audit snapshot"
    _order = "id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True)
    user_id = fields.Many2one("res.users", required=True)
    snapshot = fields.Json(required=True)
    checksum = fields.Char(required=True)
    csv_file = fields.Binary(compute="_compute_csv")

    def _compute_csv(self):
        def safe(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
        for rec in self:
            out = io.StringIO()
            writer = csv.writer(out)
            data = rec.snapshot
            writer.writerows([
                [safe(rec.company_id.name), rec.name], ["Export ID", rec.id, "Generated UTC", rec.create_date, "Prepared by", safe(rec.user_id.name)],
                ["Period", data["from"], data["to"], "Programme", safe(data["programme"]), "Batch", safe(data["batch"])],
                ["Source", "Odoo/OpenEduCat completed attendance", "State", "DRAFT", "Threshold", data["threshold"]],
                ["Academic year", safe(data["academic_year"]), "Semester", safe(data["semester"])],
                ["Student ID", "Register ID", "Student", "Sessions", "Present", "Rate %", "Status"],
            ])
            for row in data["rows"]:
                writer.writerow([row["id"], safe(row["register"]), safe(row["name"]), row["sessions"], row["present"], row["rate"], "Shortage" if row["shortage"] else "Good"])
            writer.writerow(["TOTAL", len(data["rows"]), "Reviewed", data["sessions"], data["present"], "Below threshold", data["shortage"]])
            writer.writerow(["Snapshot SHA256", rec.checksum])
            rec.csv_file = base64.b64encode(out.getvalue().encode("utf-8-sig"))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Generate exports through the filtered attendance report."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Report snapshots are immutable."))

    def unlink(self):
        raise AccessError(_("Retain report exports for audit."))
