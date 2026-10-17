from collections import Counter

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FacultyLeaveUI(models.AbstractModel):
    _name = "campus.faculty.leave.ui"
    _description = "Faculty leave self service page"

    def _check_staff(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("An internal staff account is required."))

    def _employee(self):
        return self.env["hr.employee"].sudo().search([
            ("user_id", "=", self.env.uid),
            ("company_id", "in", [False, self.env.company.id]),
        ], limit=1)

    def _leave_types(self):
        leave_type_model = self.env["hr.leave.type"].sudo()
        domain = [("active", "=", True)]
        if "company_id" in leave_type_model._fields:
            domain.append(("company_id", "in", [False, self.env.company.id]))
        return leave_type_model.search(domain, order="sequence, name")

    @api.model
    def get_page_data(self):
        self._check_staff()
        employee = self._employee()
        leave_types = self._leave_types()
        today = fields.Date.context_today(self)
        year = today.year if today.month >= 6 else today.year - 1
        result = {
            "user_name": self.env.user.name,
            "company_name": self.env.company.name,
            "role": "Faculty" if self.env["op.faculty"].sudo().search_count([
                ("user_id", "=", self.env.uid),
            ]) else "Staff",
            "academic_years": [f"{year}-{year + 1}", f"{year - 1}-{year}"],
            "today": fields.Date.to_string(today),
            "reporting_authority": employee.parent_id.name if employee and employee.parent_id else "Not assigned",
            "can_apply": bool(employee and leave_types),
            "leave_types": [{"id": item.id, "name": item.name, "unit": item.request_unit}
                            for item in leave_types],
            "balance": None,
            "monthly_eligibility": None,
            "approved_count": 0,
            "pending_count": 0,
            "history": [],
            "attendance": [],
            "approval_percent": None,
            "most_common_leave": "No approved requests",
            "notification_count": 0,
            "notifications": [],
        }
        activities = self.env["mail.activity"].sudo().search([
            ("user_id", "=", self.env.uid),
        ], order="date_deadline asc", limit=5)
        result["notification_count"] = self.env["mail.activity"].sudo().search_count([
            ("user_id", "=", self.env.uid),
        ])
        result["notifications"] = [activity.summary or activity.res_name or _("Activity")
                                   for activity in activities]
        if not employee:
            return result

        leave_model = self.env["hr.leave"].sudo()
        own_domain = [("employee_id", "=", employee.id)]
        result["approved_count"] = leave_model.search_count(own_domain + [("state", "=", "validate")])
        result["pending_count"] = leave_model.search_count(own_domain + [("state", "in", ["draft", "confirm", "validate1"])])
        leaves = leave_model.search(own_domain, order="create_date desc, id desc", limit=50)
        state_labels = {"draft": "Pending", "confirm": "Pending", "validate1": "Pending",
                        "validate": "Approved", "refuse": "Refused"}
        result["history"] = [{
            "id": leave.id,
            "type": leave.holiday_status_id.name,
            "from": fields.Date.to_string(leave.request_date_from) if leave.request_date_from else "",
            "to": fields.Date.to_string(leave.request_date_to) if leave.request_date_to else "",
            "days": round(leave.number_of_days_display, 2),
            "reason": leave.private_name or "",
            "status": state_labels.get(leave.state, leave.state or "Pending"),
        } for leave in leaves]
        decided = [leave for leave in leaves if leave.state in ("validate", "refuse")]
        if decided:
            result["approval_percent"] = round(100 * sum(leave.state == "validate" for leave in decided) / len(decided))
        approved_types = Counter(leave.holiday_status_id.name for leave in leaves if leave.state == "validate")
        if approved_types:
            result["most_common_leave"] = approved_types.most_common(1)[0][0]

        casual_type = next((item for item in leave_types if "casual" in item.name.lower()), None)
        if casual_type:
            allocations = self.env["hr.leave.allocation"].sudo().search([
                ("employee_id", "=", employee.id),
                ("holiday_status_id", "=", casual_type.id),
                ("state", "=", "validate"),
            ])
            used = leave_model.search(own_domain + [
                ("holiday_status_id", "=", casual_type.id), ("state", "=", "validate"),
            ])
            result["balance"] = round(sum(allocations.mapped("number_of_days"))
                                      - sum(used.mapped("number_of_days")), 2)

        attendance = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee.id),
        ], order="check_in desc", limit=30)
        days = {}
        for entry in attendance:
            local_in = fields.Datetime.context_timestamp(self, entry.check_in)
            day = local_in.date().isoformat()
            if day not in days:
                days[day] = {"date": day, "day": local_in.strftime("%a"), "fn": "—", "an": "—"}
            if local_in.hour < 12:
                days[day]["fn"] = "Present"
            if entry.check_out:
                local_out = fields.Datetime.context_timestamp(self, entry.check_out)
                if local_out.date() == local_in.date() and local_out.hour >= 12:
                    days[day]["an"] = "Present"
            elif local_in.hour >= 12:
                days[day]["an"] = "Present"
        result["attendance"] = list(days.values())[:4]
        return result

    @api.model
    def submit_leave(self, values):
        self._check_staff()
        employee = self._employee()
        if not employee:
            raise UserError(_("Your account must be linked to an employee before you can request leave."))
        leave_type = self._leave_types().filtered(lambda item: item.id == int(values.get("leave_type_id") or 0))[:1]
        if not leave_type:
            raise UserError(_("Choose an available leave type."))
        try:
            start = fields.Date.to_date(values.get("date_from"))
            end = fields.Date.to_date(values.get("date_to"))
        except (TypeError, ValueError):
            raise UserError(_("Enter valid leave dates."))
        if not start or not end or end < start:
            raise UserError(_("The end date must be on or after the start date."))
        first = values.get("from_session")
        last = values.get("to_session")
        if first not in ("FN", "AN") or last not in ("FN", "AN"):
            raise UserError(_("Choose valid leave sessions."))
        reason = (values.get("reason") or "").strip()
        if not reason:
            raise UserError(_("Enter a reason for the leave request."))
        partial = first == "AN" or last == "FN"
        if partial and start != end:
            raise UserError(_("Odoo supports half-day requests for one day only. Submit separate requests for partial days."))
        if start == end and first == "AN" and last == "FN":
            raise UserError(_("The selected sessions do not include any leave time."))
        if partial and leave_type.request_unit not in ("half_day", "hour"):
            raise UserError(_("This leave type does not allow half-day requests."))
        data = {
            "employee_id": employee.id,
            "holiday_status_id": leave_type.id,
            "request_date_from": fields.Date.to_string(start),
            "request_date_to": fields.Date.to_string(end),
            "private_name": reason,
        }
        if partial:
            data.update(request_unit_half=True,
                        request_date_from_period="pm" if first == "AN" else "am")
        leave = self.env["hr.leave"].sudo().create(data)
        if leave.state == "draft":
            leave.action_confirm()
        return {"id": leave.id, "status": leave.state}
