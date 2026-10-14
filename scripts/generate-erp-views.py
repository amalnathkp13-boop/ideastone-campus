import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

root = Path(__file__).resolve().parents[1]
module = root / "addons/ideastone_erp"
# (model, title, operator, group, listing, form, measures, extra buttons, own faculty field)
schemas = [
    (
        "digital.resource",
        "Digital library",
        "academic",
        "Academics",
        "author resource_type subject_id state",
        "subject_id author resource_type batch_ids document filename description",
        "",
        [],
        None,
    ),
    (
        "teaching.plan",
        "Lesson plans",
        "academic",
        "Academics",
        "faculty_id subject_id planned_date planned_hours actual_hours variance",
        "faculty_id subject_id batch_id term_id planned_date unit topic planned_hours teaching_aid learning_aid co_level reference execution_date actual_hours notes attachment_ids",
        "planned_hours actual_hours variance",
        [],
        "faculty_id",
    ),
    (
        "faculty.detail",
        "Staff qualifications and documents",
        "people",
        "Staff",
        "faculty_id kind name institution verification",
        "faculty_id kind specialization institution university year result designation date_from date_to nature can_read can_write can_speak reference document filename verification reviewer_id next_action",
        "year",
        [("action_verify", "Verify document", None)],
        "faculty_id",
    ),
    (
        "faculty.achievement",
        "Faculty development and appraisal",
        "people",
        "Staff",
        "faculty_id kind date_from organizer state",
        "faculty_id kind date_from date_to organizer venue level reference description evidence filename score reviewer_notes",
        "score",
        [],
        "faculty_id",
    ),
    (
        "hostel.room",
        "Hostel rooms",
        "services",
        "Campus services",
        "building name capacity occupied vacancy",
        "building capacity air_conditioned attached_bathroom facilities warden_id allocation_ids",
        "capacity",
        [],
        None,
    ),
    (
        "hostel.allocation",
        "Hostel residents",
        "services",
        "Campus services",
        "student_id room_id date_from date_to food_preference state",
        "student_id room_id date_from date_to food_preference dietary_notes emergency_phone",
        "",
        [],
        None,
    ),
    (
        "hostel.attendance",
        "Hostel attendance",
        "services",
        "Campus services",
        "student_id date present remarks",
        "allocation_id student_id date present remarks",
        "",
        [],
        None,
    ),
    (
        "gate.entry",
        "Hostel and library gate",
        "services",
        "Campus services",
        "area student_id faculty_id entered_on exited_on",
        "area student_id faculty_id entered_on exited_on reason",
        "",
        [("action_exit", "Record exit", "exited_on")],
        None,
    ),
    (
        "transport.route",
        "Bus routes",
        "services",
        "Campus services",
        "year_id vehicle_registration capacity driver",
        "year_id vehicle_registration capacity driver driver_phone stop_ids",
        "capacity",
        [],
        None,
    ),
    (
        "transport.stop",
        "Boarding points",
        "services",
        "Campus services",
        "route_id sequence pickup_time fee",
        "route_id sequence pickup_time fee",
        "fee",
        [],
        None,
    ),
    (
        "transport.allocation",
        "Transport allocations",
        "services",
        "Campus services",
        "student_id route_id stop_id year_id state invoice_id",
        "student_id stop_id route_id year_id invoice_id",
        "",
        [("action_invoice", "Create or open fee demand", "state != 'approved'")],
        None,
    ),
    (
        "transport.trip",
        "Trips and fuel",
        "services",
        "Campus services",
        "route_id date distance fuel_litres mileage fuel_cost other_expense",
        "route_id date odometer_start odometer_end fuel_litres fuel_cost other_expense distance mileage notes",
        "distance fuel_litres fuel_cost other_expense",
        [],
        None,
    ),
    (
        "visitor",
        "Visitor register",
        "services",
        "Campus services",
        "host_id organization entered_on exited_on",
        "organization phone host_id purpose entered_on exited_on closing_notes follow_up_date",
        "",
        [("action_exit", "Close visit", "exited_on")],
        None,
    ),
    (
        "counseling",
        "Mentor counseling",
        "academic",
        "Academics",
        "student_id mentor_id date kind follow_up_date",
        "student_id mentor_id date kind discussion outcome shared_remarks follow_up_date future_plan",
        "",
        [],
        "mentor_id",
    ),
    (
        "circular",
        "Circulars",
        "academic",
        "Academics",
        "reference audience date_from date_to state",
        "reference audience date_from date_to body attachment_ids",
        "",
        [],
        None,
    ),
    (
        "feedback",
        "Institutional feedback",
        "outreach",
        "Engagement",
        "kind respondent_id period faculty_id score",
        "respondent_id student_id faculty_id kind period score comments",
        "score",
        [],
        None,
    ),
    (
        "service.request",
        "Service requests",
        "services",
        "Campus services",
        "requester_id kind date amount state",
        "requester_id kind student_id faculty_id replacement_id department_id requested_course_id date date_from date_to amount description resolution document filename",
        "amount",
        [],
        "requester_id",
    ),
    (
        "placement.drive",
        "Recruitment drives",
        "outreach",
        "Engagement",
        "recruiter_id kind interview_on location state",
        "recruiter_id representative_id spoc_id kind interview_on location min_percentage max_standing_arrears course_ids job_description candidate_ids",
        "",
        [],
        None,
    ),
    (
        "placement.candidate",
        "Placement candidates",
        "outreach",
        "Engagement",
        "drive_id student_id percentage standing_arrears eligible state",
        "drive_id student_id percentage standing_arrears ever_had_arrears eligible state interview_notes offer_reference offered_salary",
        "offered_salary",
        [],
        None,
    ),
    (
        "alumni.chapter",
        "Alumni chapters",
        "outreach",
        "Engagement",
        "location coordinator_id",
        "location coordinator_id description",
        "",
        [],
        None,
    ),
    (
        "alumni",
        "Alumni profiles",
        "outreach",
        "Engagement",
        "student_id graduation_year chapter_id employer designation",
        "student_id graduation_year chapter_id employer designation location higher_studies family_information contact_email contact_phone photo job_opportunities",
        "",
        [],
        None,
    ),
    (
        "asset",
        "Fixed asset register",
        "purchasing",
        "Purchase and accounts",
        "asset_code department_id custodian_id location condition acquisition_value",
        "asset_code serial_number department_id custodian_id acquisition_date acquisition_value location equipment_id condition verified_on notes",
        "acquisition_value",
        [],
        None,
    ),
    (
        "purchase.request",
        "Purchase indents",
        "purchasing",
        "Purchase and accounts",
        "requester_id department_id product_id quantity total state",
        "requester_id department_id product_id quantity vendor_id unit_price total required_on justification comparative_quote department_reviewer_id finance_reviewer_id purchase_id",
        "quantity total",
        [
            ("action_department_review", "Department review", "state != 'submitted'"),
            ("action_finance_review", "Finance review", "state != 'submitted'"),
            ("action_purchase", "Create or open purchase order", "state != 'approved'"),
        ],
        None,
    ),
    (
        "stock.inspection",
        "Goods receipt inspections",
        "purchasing",
        "Purchase and accounts",
        "picking_id product_id received_quantity accepted_quantity rejected_quantity state",
        "picking_id product_id received_quantity accepted_quantity rejected_quantity quality_notes inspected_on",
        "received_quantity accepted_quantity rejected_quantity",
        [],
        None,
    ),
    (
        "salary.agreement",
        "Salary agreements",
        "people",
        "Staff",
        "employee_id date_from date_to basic allowance state",
        "employee_id date_from date_to basic allowance fixed_deduction tds pf_rate esi_rate pf_base esi_base daily_hours bank_reference",
        "basic allowance",
        [],
        None,
    ),
    (
        "payslip",
        "Monthly payroll",
        "people",
        "Staff",
        "employee_id date_from date_to gross deductions net state",
        "agreement_id employee_id date_from date_to working_days paid_leave_days advance_deduction worked_days gross pf esi tds deductions net computed_on payment_reference",
        "gross pf esi tds deductions net",
        [("action_compute", "Compute payroll", "state != 'draft'")],
        None,
    ),
    (
        "biometric.event",
        "Device attendance imports",
        "people",
        "Staff",
        "device external_reference employee_id check_in check_out attendance_id",
        "device external_reference employee_id check_in check_out attendance_id",
        "",
        [("action_import", "Import attendance", "attendance_id")],
        None,
    ),
    (
        "exam.review",
        "Mark reviews and revaluation",
        "academic",
        "Academics",
        "student_id kind evaluator_id original_marks revised_marks state published",
        "result_id student_id kind original_marks revised_marks evaluator_id dummy_number packet_number reason published",
        "revised_marks",
        [("action_publish", "Publish reviewed marks", "state != 'approved' or published or kind == 'malpractice'")],
        "evaluator_id",
    ),
]
approval = {
    "digital.resource",
    "faculty.achievement",
    "hostel.allocation",
    "transport.allocation",
    "circular",
    "service.request",
    "placement.drive",
    "purchase.request",
    "stock.inspection",
    "salary.agreement",
    "payslip",
    "exam.review",
}
binary = {"document", "evidence"}
fields_groups = {"reviewer_notes": "ideastone_erp.group_manager", "bank_reference": "ideastone_erp.group_people"}
views = ["<odoo>"]
rules = ["<odoo>"]
acl = [["id", "name", "model_id:id", "group_id:id", "perm_read", "perm_write", "perm_create", "perm_unlink"]]
nav = []
menus = [
    "<odoo>",
    '<record id="action_dashboard" model="ir.actions.client"><field name="name">Campus overview</field><field name="tag">ideastone_erp.dashboard</field></record>',
    '<menuitem id="menu_operations" name="Campus Operations" sequence="2" web_icon="ideastone_campus,static/description/icon.png"/>',
    '<menuitem id="menu_overview" name="Campus overview" parent="menu_operations" sequence="1" action="action_dashboard"/>',
]
categories = list(dict.fromkeys(s[3] for s in schemas))
for i, category in enumerate(categories):
    menus.append(
        f'<menuitem id="menu_category_{i}" name="{escape(category)}" parent="menu_operations" sequence="{10 + i}"/>'
    )

for model, title, operator, category, listing, form, measures, buttons, own in schemas:
    slug = model.replace(".", "_")
    fullname = "campus." + model
    is_approval = model in approval
    has_state = is_approval or model == "placement.candidate"
    nav.append({"model": fullname, "label": title, "group": category, "action": "ideastone_erp.action_" + slug})
    xml_fields = list(dict.fromkeys(["name"] + listing.split()))
    views.append(
        f'<record id="view_{slug}_tree" model="ir.ui.view"><field name="name">{fullname}.tree</field><field name="model">{fullname}</field><field name="arch" type="xml"><tree string="{escape(title)}">'
        + "".join(f'<field name="{f}"/>' for f in xml_fields)
        + "</tree></field></record>"
    )
    header = []
    if is_approval:
        for method, label, condition, manager in [
            ("action_submit", "Submit", "state != 'draft'", False),
            ("action_approve", "Approve", "state != 'submitted'", True),
            ("action_done", "Complete", "state != 'approved'", True),
            ("action_cancel", "Cancel", "state not in ('draft','submitted','approved')", False),
            ("action_reset", "Revise", "state != 'cancelled'", True),
        ]:
            groups = ' groups="ideastone_erp.group_manager"' if manager else ""
            header.append(
                f'<button name="{method}" type="object" string="{label}" invisible="{escape(condition)}"{groups}/>'
            )
    for method, label, condition in buttons:
        attrs = f' invisible="{escape(condition)}"' if condition else ""
        if method == "action_verify":
            attrs += ' groups="ideastone_erp.group_people"'
        if method == "action_publish":
            attrs += ' groups="ideastone_erp.group_manager"'
        header.append(f'<button name="{method}" type="object" string="{escape(label)}"{attrs}/>')
    if is_approval:
        header.append('<field name="state" widget="statusbar" statusbar_visible="draft,submitted,approved,done"/>')
    form_fields = []
    for f in form.split():
        attrs = ""
        if f == "attachment_ids":
            attrs += ' widget="many2many_binary"'
        if f in {"course_ids", "batch_ids"}:
            attrs += ' widget="many2many_tags"'
        if f in binary:
            attrs += ' filename="filename"'
        if f == "filename":
            attrs += ' invisible="True"'
        if f in fields_groups:
            attrs += f' groups="{fields_groups[f]}"'
        if is_approval and f not in {"payment_reference", "invoice_id", "purchase_id"}:
            attrs += " readonly=\"state in ('approved', 'done')\""
        form_fields.append(f'<field name="{f}"{attrs}/>')
    if is_approval:
        form_fields += ['<field name="approved_by"/>', '<field name="approved_on"/>']
    views.append(
        f'<record id="view_{slug}_form" model="ir.ui.view"><field name="name">{fullname}.form</field><field name="model">{fullname}</field><field name="arch" type="xml"><form string="{escape(title)}"><header>'
        + "".join(header)
        + '</header><sheet><div class="oe_title"><h1><field name="name" placeholder="Record title"/></h1></div><group><field name="company_id"/><field name="currency_id" invisible="True"/>'
        + "".join(form_fields)
        + '</group><field name="active" invisible="True"/></sheet><div class="oe_chatter"><field name="message_follower_ids"/><field name="activity_ids"/><field name="message_ids"/></div></form></field></record>'
    )
    searchable = ["name"] + [
        f
        for f in xml_fields
        if f.endswith("_id")
        or f in {"reference", "asset_code", "period", "building", "organization", "external_reference"}
    ]
    search = "".join(f'<field name="{f}"/>' for f in searchable)
    search += '<filter name="archived" string="Archived" domain="[(\'active\',\'=\',False)]"/>'
    if has_state:
        search += '<filter name="by_state" string="Status" context="{\'group_by\':\'state\'}"/>'
    if is_approval:
        search += "<filter name=\"pending\" string=\"Awaiting approval\" domain=\"[('state','=','submitted')]\"/>"
    for f in searchable[1:4]:
        search += f'<filter name="group_{f}" string="By {escape(f[:-3].replace("_", " ").title())}" context="{{\'group_by\':\'{f}\'}}"/>'
    views.append(
        f'<record id="view_{slug}_search" model="ir.ui.view"><field name="name">{fullname}.search</field><field name="model">{fullname}</field><field name="arch" type="xml"><search>{search}</search></field></record>'
    )
    modes = "tree,form"
    if measures:
        modes += ",pivot,graph"
        row = "state" if has_state else next((f for f in searchable if f.endswith("_id")), "company_id")
        for mode in ["pivot", "graph"]:
            chart = (
                f'<{mode} string="{escape(title)}"><field name="{row}" type="row"/>'
                + "".join(f'<field name="{f}" type="measure"/>' for f in measures.split())
                + f"</{mode}>"
            )
            views.append(
                f'<record id="view_{slug}_{mode}" model="ir.ui.view"><field name="name">{fullname}.{mode}</field><field name="model">{fullname}</field><field name="arch" type="xml">{chart}</field></record>'
            )
    views.append(
        f'<record id="action_{slug}" model="ir.actions.act_window"><field name="name">{escape(title)}</field><field name="res_model">{fullname}</field><field name="view_mode">{modes}</field><field name="search_view_id" ref="view_{slug}_search"/><field name="help" type="html"><p class="o_view_nocontent_smiling_face">Create the first {escape(title.lower())} record</p><p>Records are saved to the campus database. Use the search bar to filter, group or find records.</p></field></record>'
    )
    menus.append(
        f'<menuitem id="menu_{slug}" name="{escape(title)}" parent="menu_category_{categories.index(category)}" action="action_{slug}"/>'
    )
    for group in ["manager", operator]:
        acl.append(
            [
                f"access_{slug}_{group}",
                f"{fullname} {group}",
                f"model_campus_{slug}",
                f"ideastone_erp.group_{group}",
                1,
                1,
                1,
                1,
            ]
        )
    rules.append(
        f'<record id="rule_{slug}_company" model="ir.rule"><field name="name">{escape(title)} company boundary</field><field name="model_id" ref="model_campus_{slug}"/><field name="domain_force">[(\'company_id\',\'in\',company_ids)]</field><field name="global" eval="True"/></record>'
    )
    for group in ["manager", operator]:
        rules.append(
            f'<record id="rule_{slug}_{group}" model="ir.rule"><field name="name">{escape(title)} operator</field><field name="model_id" ref="model_campus_{slug}"/><field name="domain_force">[(1,\'=\',1)]</field><field name="groups" eval="[(4, ref(\'ideastone_erp.group_{group}\'))]"/></record>'
        )
    if own:
        acl.append(
            [
                f"access_{slug}_faculty",
                f"{fullname} faculty",
                f"model_campus_{slug}",
                "openeducat_core.group_op_faculty",
                1,
                1,
                1,
                0,
            ]
        )
        domain = "[('requester_id','=',user.id)]" if own == "requester_id" else f"[('{own}.user_id','=',user.id)]"
        rules.append(
            f'<record id="rule_{slug}_faculty" model="ir.rule"><field name="name">Own {escape(title)}</field><field name="model_id" ref="model_campus_{slug}"/><field name="domain_force">{escape(domain)}</field><field name="groups" eval="[(4,ref(\'openeducat_core.group_op_faculty\'))]"/></record>'
        )
    if model == "purchase.request":
        acl.append(
            [
                f"access_{slug}_finance",
                fullname + " finance",
                f"model_campus_{slug}",
                "ideastone_erp.group_finance",
                1,
                1,
                0,
                0,
            ]
        )
        rules.append(
            f'<record id="rule_{slug}_finance" model="ir.rule"><field name="name">Finance purchase review</field><field name="model_id" ref="model_campus_{slug}"/><field name="domain_force">[(1,\'=\',1)]</field><field name="groups" eval="[(4,ref(\'ideastone_erp.group_finance\'))]"/></record>'
        )

menus.append(
    '<record id="ideastone_lms.action_campus_home" model="ir.actions.client"><field name="tag">ideastone_erp.dashboard</field></record><menuitem id="menu_library_standard" name="Library" parent="menu_operations" sequence="20"/><menuitem id="menu_admissions_standard" name="Admissions and leads" parent="menu_operations" sequence="8"/><record id="action_subjects" model="ir.actions.act_window"><field name="name">Subjects</field><field name="res_model">op.subject</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_subjects" name="Subjects" parent="menu_category_0" action="action_subjects"/><record id="action_results" model="ir.actions.act_window"><field name="name">Results</field><field name="res_model">op.result.line</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_results" name="Results" parent="menu_category_0" action="action_results"/><record id="action_circulation" model="ir.actions.act_window"><field name="name">Library circulation</field><field name="res_model">op.media.movement</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_circulation" name="Library circulation" parent="menu_library_standard" action="action_circulation"/><record id="action_fee_invoices" model="ir.actions.act_window"><field name="name">Fee invoices</field><field name="res_model">account.move</field><field name="view_mode">tree,form</field><field name="domain">[(\'move_type\',\'in\',[\'out_invoice\',\'out_refund\'])]</field><field name="context">{\'default_move_type\':\'out_invoice\'}</field></record><menuitem id="menu_standard_fee_invoices" name="Fee invoices" parent="menu_category_4" action="action_fee_invoices"/><record id="action_ledger" model="ir.actions.act_window"><field name="name">Accounting entries</field><field name="res_model">account.move</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_ledger" name="Accounting entries" parent="menu_category_4" action="action_ledger"/><record id="action_orders" model="ir.actions.act_window"><field name="name">Purchase orders</field><field name="res_model">purchase.order</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_orders" name="Purchase orders" parent="menu_category_4" action="action_orders"/><record id="action_stock" model="ir.actions.act_window"><field name="name">Goods receipts and stock movements</field><field name="res_model">stock.picking</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_stock" name="Goods receipts and stock movements" parent="menu_category_4" action="action_stock"/><record id="action_maintenance" model="ir.actions.act_window"><field name="name">Work and service orders</field><field name="res_model">maintenance.request</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_maintenance" name="Work and service orders" parent="menu_category_2" action="action_maintenance"/><record id="action_leave" model="ir.actions.act_window"><field name="name">Staff leave</field><field name="res_model">hr.leave</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_leave" name="Staff leave" parent="menu_category_1" action="action_leave"/><record id="action_staff_attendance" model="ir.actions.act_window"><field name="name">Staff attendance</field><field name="res_model">hr.attendance</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_staff_attendance" name="Staff attendance" parent="menu_category_1" action="action_staff_attendance"/><record id="action_leads" model="ir.actions.act_window"><field name="name">Admission leads and agents</field><field name="res_model">crm.lead</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_leads" name="Admission leads and agents" parent="menu_admissions_standard" action="action_leads"/><record id="action_surveys" model="ir.actions.act_window"><field name="name">Feedback surveys</field><field name="res_model">survey.survey</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_surveys" name="Feedback surveys" parent="menu_category_3" action="action_surveys"/><record id="action_events" model="ir.actions.act_window"><field name="name">Events and clubs</field><field name="res_model">event.event</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_events" name="Events and clubs" parent="menu_category_3" action="action_events"/><record id="action_forums" model="ir.actions.act_window"><field name="name">Alumni forums</field><field name="res_model">forum.forum</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_forums" name="Alumni forums" parent="menu_category_3" action="action_forums"/><record id="action_payment_providers" model="ir.actions.act_window"><field name="name">Payment providers</field><field name="res_model">payment.provider</field><field name="view_mode">tree,form</field></record><menuitem id="menu_standard_payment_providers" name="Payment providers" parent="menu_category_4" action="action_payment_providers"/>'
)
views.append("</odoo>")
rules.append("</odoo>")
menus.append("</odoo>")
(module / "views").mkdir(exist_ok=True)
(module / "views/operations.xml").write_text("\n".join(views), encoding="utf-8")
(module / "views/menus.xml").write_text("\n".join(menus), encoding="utf-8")
(module / "security/rules.xml").write_text("\n".join(rules), encoding="utf-8")
with (module / "security/ir.model.access.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(acl)
(module / "models/navigation.json").write_text(json.dumps(nav, indent=2), encoding="utf-8")
print("Created views, actions and permissions for", len(schemas), "persistent models")
