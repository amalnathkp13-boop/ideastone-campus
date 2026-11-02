"""Synthetic transport records for the isolated local Accountant preview."""
from datetime import date

assert env.cr.dbname == "accountant_ui_preview", "Use only the isolated local preview database."
company = env["res.company"].browse(13)
assert company.currency_id.name == "INR"
e = env(context=dict(env.context, allowed_company_ids=company.ids))
marker = e["ir.config_parameter"].sudo()
if marker.get_param("accountant_transport_sample"):
    print("Transport samples already exist")
else:
    accountant = e["res.users"].search([("login", "=", "college.accountant")], limit=1)
    supervisor = e["res.users"].with_context(no_reset_password=True).create({
        "name": "Transport preview supervisor", "login": "transport.preview.supervisor",
        "company_id": company.id, "company_ids": [(6, 0, company.ids)],
        "groups_id": [(6, 0, [e.ref("ideastone_erp.group_manager").id])]})
    year = e["op.academic.year"].search([("company_id", "=", company.id)], limit=1)
    students = e["op.student"].search([("company_id", "=", company.id)], limit=8)
    assert len(students) == 8 and year
    income = e["account.account"].search([("company_id", "=", company.id), ("code", "=", "QA1301")], limit=1)
    expense = e["account.account"].search([("company_id", "=", company.id), ("code", "=", "QA1305")], limit=1)
    payable = e["account.account"].search([("company_id", "=", company.id), ("code", "=", "QA1303")], limit=1)
    cash = e["account.journal"].search([("company_id", "=", company.id), ("code", "=", "QCA")], limit=1)
    cash.outbound_payment_method_line_ids.payment_account_id = cash.default_account_id
    product = e["product.product"].create({"name": "Annual transport fee", "type": "service",
        "company_id": company.id, "campus_fee_head": True, "property_account_income_id": income.id,
        "taxes_id": [(5, 0, 0)]})
    routes = []
    for index, (name, registration, driver, status) in enumerate([
        ("R-04 · Perundurai", "TN 56 AB 1042", "R. Kumar", "operational"),
        ("R-02 · Erode Central", "TN 56 AB 1088", "S. Mani", "operational"),
        ("R-07 · Bhavani", "TN 56 AC 2015", "M. Selvam", "maintenance"),
        ("R-11 · Gobichettipalayam", "TN 56 AB 1130", "P. Raj", "operational"),
        ("R-15 · Kangeyam", "TN 56 AC 2044", "K. Anand", "reserve"),
    ]):
        driver_partner = e["res.partner"].create({"name": driver, "company_id": company.id,
            "property_account_payable_id": payable.id})
        route = e["campus.transport.route"].with_user(accountant).create({
            "name": name, "year_id": year.id, "vehicle_registration": registration, "capacity": 60,
            "driver": driver, "driver_code": f"DRV-{index + 1:03}", "driver_partner_id": driver_partner.id,
            "staff_riders": 2 if status != "reserve" else 0, "fleet_status": status,
            "service_due": "2026-11-20" if status == "maintenance" else False, "maintenance_reserve": 10000})
        stop = e["campus.transport.stop"].create({"name": "Town centre", "route_id": route.id,
            "fee": 30000, "fee_product_id": product.id})
        routes.append((route, stop))
    for index, student in enumerate(students):
        route, stop = routes[index % 4]
        allocation = e["campus.transport.allocation"].create({
            "name": f"Sample rider · {student.name}", "student_id": student.id, "stop_id": stop.id})
        allocation.action_submit()
        allocation.with_user(supervisor).action_approve()
        allocation.with_user(accountant).action_invoice()
        allocation.invoice_id.action_post()
        e["campus.fee.payment.wizard"].with_user(accountant).create({
            "invoice_id": allocation.invoice_id.id, "amount": 25000, "journal_id": cash.id}).action_pay()
    vendor = e["res.partner"].search([("company_id", "=", company.id), ("name", "=", "Campus Services and Events")], limit=1)
    for category, amount, index, posted in [("fuel", 18500, 0, True), ("maintenance", 42000, 2, True),
                                          ("insurance", 18000, 0, True), ("fuel", 6500, 1, False)]:
        bill = e["account.move"].with_user(accountant).create({
            "move_type": "in_invoice", "partner_id": vendor.id, "invoice_date": "2026-11-01",
            "ref": {"fuel": "Diesel expense", "maintenance": "Preventive maintenance", "insurance": "Fleet permits"}[category],
            "campus_transport_route_id": routes[index][0].id, "campus_transport_category": category,
            "campus_spend_category": "maintenance",
            "invoice_line_ids": [(0, 0, {"name": category.title(), "account_id": expense.id,
                "quantity": 1, "price_unit": amount, "tax_ids": [(5, 0, 0)]})]})
        if posted:
            bill.action_post()
    for index in range(4):
        route = routes[index][0]
        salary = e["campus.transport.payroll"].with_user(accountant).create({
            "name": f"November driver salary · {route.driver}", "route_id": route.id,
            "partner_id": route.driver_partner_id.id, "month": date(2026, 11, 1),
            "base": 28000 + index * 500, "allowance": 3500, "deductions": index * 500,
            "expense_account_id": expense.id})
        if index < 3:
            salary.action_bill()
            salary.invoice_id.action_post()
        if index < 2:
            e["account.payment.register"].with_context(active_model="account.move", active_ids=salary.invoice_id.ids).create({
                "journal_id": cash.id, "amount": salary.net, "payment_date": "2026-11-02"})._create_payments()
    marker.set_param("accountant_transport_sample", "2026-11-02")
    e.cr.commit()
    print("Transport sample fleet, riders, receipts, expenses and salaries saved")

