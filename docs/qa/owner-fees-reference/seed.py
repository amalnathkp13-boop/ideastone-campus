"""Opt-in synthetic fixture for the named localhost preview only."""
import json
import os
from datetime import date, timedelta
from pathlib import Path

from odoo import fields

assert env.cr.dbname == "owner_fees_reference_preview"  # noqa: F821
assert not env["res.users"].search_count([("login", "=", "owner.fees.preview")]), "Preview already seeded"  # noqa: F821
sample = json.loads(Path("/tmp/owner-fees-reference-records.json").read_text())
company = env["res.company"].create({"name": "VCET Fees Reference Preview", "currency_id": env.ref("base.INR").id,  # noqa: F821
    "country_id": env.ref("base.in").id, "campus_demo": True,  # noqa: F821
    "external_report_layout_id": env.ref("web.external_layout_standard").id, "font": "Roboto"})  # noqa: F821
env = env(context=dict(env.context, allowed_company_ids=[company.id], no_reset_password=True, mail_create_nosubscribe=True, mail_notrack=True))  # noqa: F821
owner = env["res.users"].create({"name": "Fees Preview Owner", "login": "owner.fees.preview",  # noqa: F821
    "password": os.environ["OWNER_FEES_PREVIEW_PASSWORD"], "email": "fees.owner@example.test", "tz": "Asia/Kolkata",
    "company_id": company.id, "company_ids": [(6, 0, company.ids)], "groups_id": [(6, 0, [env.ref("ideastone_erp.group_mvp_owner").id])]})  # noqa: F821
ui = env["campus.owner.fees"].with_user(owner)  # noqa: F821


def account(code, name, kind, reconcile=False):
    return env["account.account"].create({"code": code, "name": name, "account_type": kind, "reconcile": reconcile, "company_id": company.id})  # noqa: F821


income = account("FEE4001", "Sample tuition and services income", "income")
receivable = account("FEE1101", "Sample student receivable", "asset_receivable", True)
payable = account("FEE2101", "Sample supplier payable", "liability_payable", True)
cash_account = account("FEE1001", "Sample cash", "asset_cash")
bank_account = account("FEE1002", "Sample bank", "asset_cash")
outstanding = account("FEE1102", "Sample receipts awaiting bank matching", "asset_current", True)
expense = account("FEE5001", "Sample campus supplier expense", "expense")
cash = env["account.journal"].create({"name": "Sample Cash", "code": "FCSH", "type": "cash", "company_id": company.id, "default_account_id": cash_account.id})  # noqa: F821
bank = env["account.journal"].create({"name": "Sample Bank", "code": "FBNK", "type": "bank", "company_id": company.id, "default_account_id": bank_account.id})  # noqa: F821
env["account.journal"].create({"name": "Sample Fee Invoices", "code": "FSALE", "type": "sale", "company_id": company.id, "default_account_id": income.id})  # noqa: F821
env["account.journal"].create({"name": "Sample Supplier Bills", "code": "FPUR", "type": "purchase", "company_id": company.id, "default_account_id": expense.id})  # noqa: F821
cash.inbound_payment_method_line_ids.payment_account_id = cash_account
bank.inbound_payment_method_line_ids.payment_account_id = outstanding
bank.outbound_payment_method_line_ids.payment_account_id = bank_account
env["ir.sequence"].create({"name": "Sample college receipts", "code": "campus.receipt", "prefix": "VCET-FEE/%(year)s/", "padding": 5, "company_id": company.id})  # noqa: F821
heads = {}
frequencies = {"Semester": "semester", "Annual": "annual", "Monthly": "monthly", "One-time": "once", "Per exam": "exam", "Term": "term"}
for row in sample["heads"]:
    head_id = ui.save_head({"name": row["name"], "default_code": row["code"], "campus_fee_category": row["category"].lower().replace(" ", "_"),
        "campus_fee_frequency": frequencies[row["frequency"]], "campus_fee_optional": row["optional"], "property_account_income_id": income.id})
    heads[row["name"]] = env["product.product"].browse(head_id)  # noqa: F821

today = fields.Date.context_today(ui)
year_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
year_end = date(year_start.year + 1, 3, 31)
year = env["op.academic.year"].create({"name": f"{year_start.year}–{str(year_end.year)[-2:]}", "code": f"FEE-{year_start.year}",  # noqa: F821
    "company_id": company.id, "start_date": year_start, "end_date": year_end, "campus_current": True})
for offset in [1, 2]:
    env["op.academic.year"].create({"name": f"{year_start.year-offset}–{str(year_end.year-offset)[-2:]}", "code": f"FEE-{year_start.year-offset}",  # noqa: F821
        "company_id": company.id, "start_date": date(year_start.year-offset, 4, 1), "end_date": date(year_end.year-offset, 3, 31)})
names = [("Priya", "S."), ("Arun", "Kumar"), ("Divya", "R."), ("Kavya", "R."), ("Sanjay", "M."), ("Nisha", "T.")]
for index, row in enumerate(sample["departments"]):
    department = env["op.department"].create({"name": row["name"], "code": row["code"], "company_id": company.id})  # noqa: F821
    course = env["op.course"].create({"name": "BE " + row["code"], "code": "FEE-" + row["code"], "department_id": department.id,  # noqa: F821
        "company_id": company.id, "campus_level": "undergraduate", "campus_award": "BE / B.Tech", "campus_duration": 8})
    term = env["op.academic.term"].create({"name": "Semester I · " + row["code"], "academic_year_id": year.id, "campus_course_id": course.id,  # noqa: F821
        "campus_sequence": 1, "term_start_date": year_start, "term_end_date": year_end, "company_id": company.id})
    batch = env["op.batch"].create({"name": row["code"] + " · I year A", "code": "FEE-" + row["code"], "course_id": course.id,  # noqa: F821
        "campus_year_id": year.id, "campus_term_id": term.id, "start_date": year_start, "end_date": year_end, "company_id": company.id})
    plans = {}
    for quota in ["gq", "mq"]:
        lines = []
        for due in [today - timedelta(days=45), today + timedelta(days=30)]:
            for name, fraction in [("Tuition fee", .8), ("Examination fee", .12), ("Library fee", .08)]:
                lines.append({"product_id": heads[name].id, "amount": round(row[quota]*fraction/2, 2), "date": str(due)})
        plan = env["op.fees.terms"].browse(ui.save_plan({"name": row["code"] + " · " + quota.upper() + " · " + year.name, "year_id": year.id,  # noqa: F821
            "course_id": course.id, "quota": quota, "study_year": 1, "effective": str(year_start), "lines": lines}))
        ui.plan_action(plan.id, "review")
        if row[quota + "_state"] == "published":
            ui.plan_action(plan.id, "publish")
        plans[quota] = plan
    for position, quota in enumerate(["gq", "mq", False]):
        first, last = names[index] if position == 0 else ("Sample", row["code"] + (" MQ learner" if position == 1 else " unassigned learner"))
        partner = env["res.partner"].create({"name": first + " " + last, "company_id": company.id, "property_account_receivable_id": receivable.id})  # noqa: F821
        student = env["op.student"].create({"first_name": first, "last_name": last, "gender": "o", "birth_date": "2007-01-01",  # noqa: F821
            "gr_no": f"FEE26{row['code']}{position+1:03d}", "company_id": company.id, "partner_id": partner.id})
        enrolment = env["op.student.course"].create({"student_id": student.id, "course_id": course.id, "batch_id": batch.id,  # noqa: F821
            "academic_years_id": year.id, "academic_term_id": term.id, "state": "running", "campus_date_from": year_start, "campus_fee_quota": quota})
        if not quota or plans[quota].campus_plan_state != "published":
            continue
        env["campus.fee.assignment.wizard"].with_user(owner).create({"enrolment_id": enrolment.id, "structure_id": plans[quota].id, "date_from": today}).action_assign()  # noqa: F821
        charges = env["op.student.fees.details"].search([("student_id", "=", student.id), ("company_id", "=", company.id)], order="id")  # noqa: F821
        for charge in charges:
            charge.get_invoice()
            charge.invoice_id.write({"invoice_date": year_start + timedelta(days=5)})
            charge.with_user(owner).action_campus_post()
        if position == 0:
            payment_date = min(today, date(year_start.year, 4 + index, 20))
            for charge in charges:
                wizard = env["campus.fee.payment.wizard"].with_user(owner).create({"invoice_id": charge.invoice_id.id, "amount": charge.invoice_id.amount_residual,  # noqa: F821
                    "journal_id": cash.id, "method": "cash", "date": payment_date})
                wizard.action_pay()
        elif index != 3:
            draft = ui.prepare_payment({"invoice_id": charges[0].invoice_id.id, "amount": 6000, "method": "upi", "reference": "SAMPLE-UPI-" + row["code"], "journal_id": bank.id})
            ui.post_payment(draft)
        overdue = charges.filtered(lambda f: f.invoice_id.amount_residual > 0 and f.date < today)[:1]
        if overdue:
            ui.log_contact({"invoice_id": overdue.invoice_id.id, "channel": "phone", "outcome": "Synthetic completed contact for local preview",
                "next_action": "Confirm the student's payment plan", "next_date": str(today + timedelta(days=3)), "promise": index % 2 == 0})

vendor = env["res.partner"].create({"name": "Sample campus services supplier", "company_id": company.id, "property_account_payable_id": payable.id})  # noqa: F821
for offset in range(min(7, (today.year-year_start.year)*12+today.month-year_start.month+1)):
    payment_date = min(today, date(year_start.year+(year_start.month+offset-1)//12, (year_start.month+offset-1)%12+1, 10))
    payment = env["account.payment"].create({"payment_type": "outbound", "partner_type": "supplier", "partner_id": vendor.id, "journal_id": bank.id,  # noqa: F821
        "amount": 6000+offset*500, "date": payment_date, "currency_id": company.currency_id.id})
    payment.action_post()
env["account.move"].create({"move_type": "in_invoice", "partner_id": vendor.id, "company_id": company.id, "invoice_date": today,  # noqa: F821
    "invoice_line_ids": [(0, 0, {"name": "Synthetic maintenance bill", "account_id": expense.id, "quantity": 1, "price_unit": 5500})]})
owner.action_id = env.ref("ideastone_erp.action_owner_fees_overview").id  # noqa: F821
env["ir.config_parameter"].sudo().set_param("report.url", "http://127.0.0.1:8069")  # noqa: F821
env.cr.commit()  # noqa: F821
print("Synthetic fee preview seeded:", company.id, owner.login, "year", year.id)
