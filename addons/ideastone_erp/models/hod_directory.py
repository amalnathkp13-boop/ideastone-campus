from collections import Counter, defaultdict
from datetime import timedelta

import pytz
from odoo.exceptions import AccessError, ValidationError

from odoo import _, api, fields, models

from .late_punch import local_bounds

PAGES = [("staff", "Staff directory"), ("students", "Student directory")]


class HodDirectoryNavigation(models.AbstractModel):
    _inherit = "campus.dashboard"

    def _faculty_modules(self, visible, faculty, pages):
        modules = super()._faculty_modules(visible, faculty, pages)
        if self.env["campus.hod.directory"]._department():
            items = []
            for page, label in PAGES:
                action = f"ideastone_erp.action_hod_directory_{page}"
                items.append({"label": label, "action": action, "action_id": self.env.ref(action).id})
            index = next((i for i, module in enumerate(modules) if module["key"] == "reports"), len(modules))
            modules.insert(index, {"key": "hod-directory", "label": "Staff & Students", "icon": "address-book-o", "items": items})
        return modules


class HodDirectory(models.AbstractModel):
    _name = "campus.hod.directory"
    _description = "HOD department staff and student directory"

    def _department(self):
        user = self.env.user
        if not user.has_group("base.group_user") or not user.has_group("ideastone_erp.group_mvp_hod"):
            return self.env["op.department"]
        return self.env["op.department"].sudo().search([
            ("id", "=", user.dept_id.id), ("company_id", "=", self.env.company.id),
        ], limit=1)

    def _staff(self, department, staff_id=None):
        domain = [("company_id", "=", self.env.company.id), ("main_department_id", "=", department.id)]
        if staff_id is not None:
            domain.append(("id", "=", staff_id))
        return self.env["op.faculty"].sudo().search(domain, order="name, id")

    def _academic_year(self, today):
        company = self.env.company.id
        years = self.env["op.academic.year"].sudo()
        year = years.search([("company_id", "=", company), ("campus_current", "=", True)], limit=1)
        if not year:
            year = years.search([
                ("company_id", "=", company), ("start_date", "<=", today), ("end_date", ">=", today),
            ], order="start_date desc, id desc", limit=1)
        return year

    def _placements(self, department, today, year, placement_id=None):
        company = self.env.company.id
        domain = [
            ("company_id", "=", company), ("course_id.company_id", "=", company),
            ("course_id.department_id", "=", department.id), ("student_id.company_id", "=", company),
            ("student_id.active", "=", True), ("state", "=", "running"),
            ("batch_id.company_id", "=", company), ("academic_term_id.company_id", "=", company),
            ("academic_term_id.campus_sequence", "in", list(range(1, 9))),
            "|", ("campus_date_from", "=", False), ("campus_date_from", "<=", today),
            "|", ("campus_date_to", "=", False), ("campus_date_to", ">=", today),
        ]
        if year:
            domain.append(("academic_years_id", "=", year.id))
        if placement_id is not None:
            domain.append(("id", "=", placement_id))
        return self.env["op.student.course"].sudo().search(domain, order="id desc")

    def _sections(self, department, year, today):
        if not year:
            return {}
        batches = self.env["op.batch"].sudo().search([
            ("company_id", "=", self.env.company.id), ("course_id.department_id", "=", department.id),
            ("campus_year_id", "=", year.id), ("start_date", "<=", today), ("end_date", ">=", today),
            ("campus_term_id.campus_sequence", "in", list(range(1, 9))),
        ])
        return {batch.id: {"id": batch.id, "year": (batch.campus_term_id.campus_sequence + 1) // 2,
                           "name": batch.name, "programme": batch.course_id.name, "count": 0}
                for batch in batches}

    def _staff_attendance(self, employees, day, today):
        if not employees or day > today:
            return {}
        punches = self.env["hr.attendance"].sudo().search([
            ("employee_id", "in", employees.ids), ("check_in", ">=", day - timedelta(days=1)),
            ("check_in", "<", day + timedelta(days=2)),
        ])
        bounds = {employee.id: local_bounds(day, pytz.timezone(employee.resource_calendar_id.tz or "UTC"))
                  for employee in employees}
        present = {p.employee_id.id for p in punches if bounds[p.employee_id.id][0] <= p.check_in < bounds[p.employee_id.id][1]}
        on_leave = set(self.env["hr.leave"].sudo().search([
            ("employee_id", "in", employees.ids), ("company_id", "=", self.env.company.id),
            ("state", "=", "validate"), ("request_date_from", "<=", day), ("request_date_to", ">=", day),
        ]).employee_id.ids)
        absent = on_leave - present
        # Only infer a missed punch on a completed scheduled workday. The calendar
        # removes non-working days and public holidays.
        if day < today:
            for employee in employees:
                calendar = employee.resource_calendar_id
                if not calendar or not employee.resource_id or employee.id in present or employee.id in absent:
                    continue
                start, end = (pytz.UTC.localize(value) for value in bounds[employee.id])
                intervals = calendar._work_intervals_batch(start, end, resources=employee.resource_id)
                if intervals[employee.resource_id.id]:
                    absent.add(employee.id)
        return dict.fromkeys(absent, "Absent") | dict.fromkeys(present, "Present")

    def _student_attendance(self, placements, day):
        marks = defaultdict(set)
        lines = self.env["op.attendance.line"].sudo().search([
            ("company_id", "=", self.env.company.id), ("student_id", "in", placements.student_id.ids),
            ("attendance_id.batch_id", "in", placements.batch_id.ids), ("attendance_id.state", "=", "done"),
            ("attendance_id.attendance_date", "=", day),
        ])
        for line in lines:
            marks[(line.student_id.id, line.attendance_id.batch_id.id, line.attendance_id.course_id.id)].add(line.campus_status)
        return {key: "Present" if statuses & {"present", "late"} else "Excused" if "excused" in statuses else "Absent"
                for key, statuses in marks.items()}

    def _staff_row(self, staff, employee, attendance):
        return {
            "id": staff.id, "name": staff.name, "code": staff.campus_staff_code or staff.id_number,
            "category": "Teaching" if staff.campus_category in (False, "teaching") else "Non-teaching",
            "designation": staff.campus_designation or employee.job_title,
            "unit": staff.campus_work_location or staff.main_department_id.name,
            "contact": employee.work_phone or employee.mobile_phone,
            "attendance": attendance.get(employee.id, "Not recorded"),
        }

    def _student_row(self, placement, marks):
        student = placement.student_id
        return {
            "id": placement.id, "student_id": student.id, "name": student.name, "code": student.register_no or student.gr_no,
            "programme": placement.course_id.name, "year": (placement.academic_term_id.campus_sequence + 1) // 2,
            "section": placement.batch_id.name, "section_id": placement.batch_id.id,
            "semester": placement.academic_term_id.name, "contact": student.email,
            "attendance": marks.get((student.id, placement.batch_id.id, placement.course_id.id), "Not recorded"),
        }

    def _scope(self, view, attendance_date):
        department = self._department()
        if not department:
            raise AccessError(_("An HOD assignment in the active college is required."))
        if view not in ("staff", "students"):
            raise ValidationError(_("Choose Staff directory or Student directory."))
        today = fields.Date.context_today(self)
        try:
            day = fields.Date.to_date(attendance_date) if attendance_date else today
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Choose a valid attendance date.")) from exc
        if not day or day > today or day.year < 1900:
            raise ValidationError(_("Choose an attendance date through today."))
        return department, today, day

    @api.model
    def get_directory(self, view, attendance_date=None):
        department, today, day = self._scope(view, attendance_date)
        if view == "staff":
            staff = self._staff(department)
            employees = staff.emp_id.filtered(lambda employee: employee.company_id == self.env.company)
            attendance = self._staff_attendance(employees, day, today)
            rows = [self._staff_row(person, person.emp_id & employees,
                                    attendance if not person.campus_joining_date or person.campus_joining_date <= day else {})
                    for person in staff]
            sections = []
        else:
            year = self._academic_year(today)
            placements = self._placements(department, today, year)
            marks = self._student_attendance(placements, day)
            rows, sections = [], self._sections(department, year, today)
            seen = set()
            for placement in placements:
                row = self._student_row(placement, marks)
                membership = (row["student_id"], row["section_id"])
                if membership in seen:
                    continue
                seen.add(membership)
                rows.append(row)
                section = sections.setdefault(row["section_id"], {"id": row["section_id"], "year": row["year"],
                    "name": row["section"], "programme": row["programme"], "count": 0})
                section["count"] += 1
            rows.sort(key=lambda row: (row["name"].casefold(), row["id"]))
            sections = sorted(sections.values(), key=lambda section: (section["year"], section["name"]))
        # A student with two current placements is counted once in the department totals.
        unique = {}
        for row in rows:
            key = row.get("student_id", row["id"])
            if key not in unique or row["attendance"] == "Present":
                unique[key] = row
        attendance_counts = Counter(row["attendance"] for row in unique.values())
        return {"department": department.name, "demo": bool(self.env.company.campus_demo), "today": str(today),
                "date": str(day), "rows": rows, "sections": sections, "total": len(unique),
                "present": attendance_counts["Present"], "absent": attendance_counts["Absent"]}

    @api.model
    def get_profile(self, view, record_id, attendance_date=None):
        department, today, day = self._scope(view, attendance_date)
        if not isinstance(record_id, int) or isinstance(record_id, bool):
            raise ValidationError(_("Choose a valid directory profile."))
        if view == "staff":
            staff = self._staff(department, record_id)
            if not staff:
                raise AccessError(_("This profile is outside your department."))
            employee = staff.emp_id.filtered(lambda emp: emp.company_id == self.env.company)
            joined = staff.campus_joining_date
            attendance = self._staff_attendance(employee, day, today) if not joined or joined <= day else {}
            row = self._staff_row(staff, employee, attendance)
            qualification = staff.campus_detail_ids.filtered(
                lambda item: item.kind == "qualification" and item.company_id == self.env.company
            ).sorted(lambda item: (item.year, item.id), reverse=True)[:1]
            experience = today.year - joined.year - ((today.month, today.day) < (joined.month, joined.day)) if joined else None
            details = [
                (_("Staff ID"), row["code"]), (_("Designation"), row["designation"]), (_("Department / Unit"), row["unit"]),
                (_("Employment category"), row["category"]), (_("Attendance"), row["attendance"]),
                (_("Email"), employee.work_email or staff.email), (_("Phone"), row["contact"]),
                (_("Qualification"), qualification.name), (_("Experience"), _("%s years") % experience if experience is not None else ""),
                (_("Specialization"), qualification.specialization), (_("Date of joining"), str(joined or "")),
            ]
            subtitle = row["designation"]
        else:
            placement = self._placements(department, today, self._academic_year(today), record_id)
            if not placement:
                raise AccessError(_("This profile is outside your department."))
            row = self._student_row(placement, self._student_attendance(placement, day))
            subtitle = _("%(programme)s · Year %(year)s / %(section)s") % row
            details = [
                (_("Register number"), row["code"]), (_("Programme"), row["programme"]),
                (_("Academic year"), _("Year %s") % row["year"]), (_("Section"), row["section"]),
                (_("Semester"), row["semester"]), (_("Attendance"), row["attendance"]),
                (_("College email"), row["contact"]), (_("Batch"), placement.academic_years_id.name),
            ]
            # Keep identity, health, address and guardian details out of the directory projection.
        return {"name": row["name"], "subtitle": subtitle, "attendance": row["attendance"],
                "details": [{"label": label, "value": value or "—"} for label, value in details]}
