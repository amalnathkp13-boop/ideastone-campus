/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const FACULTY_FIELDS = [
    "display_name", "partner_id", "main_department_id", "write_date", "blood_group", "campus_staff_code",
    "campus_designation", "campus_category", "campus_service_type", "campus_joining_date",
    "campus_reporting_id", "campus_work_location", "campus_community", "campus_caste",
    "campus_caste_certificate_name", "campus_religion", "campus_alternate_mobile",
    "campus_father_name", "campus_mother_name", "campus_spouse_name", "campus_blood_donor",
    "campus_anniversary", "campus_registration_reference", "campus_residence_location",
    "campus_emergency_phone", "campus_marital_status", "campus_alternate_email",
    "campus_travel_mode", "campus_communication_address", "campus_previous_education",
    "campus_notes", "campus_pan_reference", "campus_aadhaar_last4", "campus_passport_reference",
    "campus_pf_reference", "campus_esi_reference", "campus_identification_marks",
];

const DETAIL_FIELDS = [
    "display_name", "faculty_id", "kind", "specialization", "institution", "university", "year",
    "result", "designation", "date_from", "date_to", "nature", "can_read", "can_write",
    "can_speak", "reference", "filename", "verification", "reviewer_id", "next_action", "write_date",
];

const labelFor = (value) => value || "Not provided";
const relationLabel = (value) => Array.isArray(value) ? value[1] : labelFor(value);
const dateLabel = (value) => {
    if (!value) return "Not provided";
    const normalized = value.includes(" ") ? value.replace(" ", "T") : `${value}T00:00:00`;
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? "Not provided" : date.toLocaleDateString();
};

export class CampusFacultyProfile extends Component {
    static template = "ideastone_erp.FacultyProfile";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");
        this.company = useService("company");
        this.state = useState({
            loading: true, loadingProfile: false, error: "", staff: [], selectedId: null,
            profile: null, partner: null, details: [], canManage: false, activeSection: "overview",
        });
        onWillStart(() => this.loadStaff());
    }

    async loadStaff() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.canManage = await this.user.hasGroup("ideastone_erp.group_people");
            const fields = FACULTY_FIELDS.filter((name) => this.state.canManage || ![
                "campus_pan_reference", "campus_aadhaar_last4", "campus_passport_reference",
                "campus_pf_reference", "campus_esi_reference", "campus_identification_marks",
            ].includes(name));
            this.facultyFields = fields;
            this.state.staff = await this.orm.searchRead("op.faculty", [["active", "=", true], ["company_id", "=", this.company.currentCompany.id]], fields, {
                order: "display_name",
            });
            if (this.state.staff.length) {
                const selected = this.state.staff.find((item) => item.id === this.state.selectedId) || this.state.staff[0];
                await this.loadProfile(selected.id);
            }
        } catch (error) {
            this.state.error = "Staff profiles could not be loaded. Check your access permissions and try again.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadProfile(id) {
        if (!id) return;
        this.state.loadingProfile = true;
        this.state.selectedId = Number(id);
        this.state.error = "";
        this.state.profile = null;
        this.state.partner = null;
        this.state.details = [];
        try {
            const profile = this.state.staff.find((item) => item.id === this.state.selectedId);
            if (!profile) return;
            this.state.profile = profile;
            const partnerId = Array.isArray(profile.partner_id) ? profile.partner_id[0] : profile.partner_id;
            const [partners, details] = await Promise.all([
                partnerId ? this.orm.searchRead("res.partner", [["id", "=", partnerId]], [
                    "name", "email", "phone", "mobile", "street", "street2", "city", "zip", "state_id", "country_id",
                ], { limit: 1 }) : Promise.resolve([]),
                this.orm.searchRead("campus.faculty.detail", [["faculty_id", "=", this.state.selectedId]], DETAIL_FIELDS, {
                    order: "kind, year desc, write_date desc",
                }),
            ]);
            this.state.partner = partners[0] || {};
            this.state.details = details;
        } catch (error) {
            this.state.error = "This staff profile could not be loaded. Check your access permissions and try again.";
        } finally {
            this.state.loadingProfile = false;
        }
    }

    onFacultyChange(event) {
        this.loadProfile(Number(event.currentTarget.value));
    }

    setSection(section) {
        this.state.activeSection = section;
        document.getElementById(`staff-profile-${section}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    printProfile() { window.print(); }

    get qualifications() { return this.state.details.filter((item) => item.kind === "qualification"); }
    get experience() { return this.state.details.filter((item) => item.kind === "experience"); }
    get languages() { return this.state.details.filter((item) => item.kind === "language"); }
    get documents() { return this.state.details.filter((item) => item.kind === "document"); }
    get verifiedDocuments() { return this.documents.filter((item) => item.verification === "verified").length; }
    get pendingDocuments() { return this.documents.filter((item) => item.verification === "pending").length; }
    get missingDocuments() { return this.documents.filter((item) => item.verification === "missing").length; }
    get pendingActions() { return this.pendingDocuments + this.missingDocuments; }
    get verificationPercent() { return this.documents.length ? Math.round(this.verifiedDocuments / this.documents.length * 100) : 0; }
    get recentActivity() { return [...this.state.details].sort((a, b) => (b.write_date || "").localeCompare(a.write_date || "")).slice(0, 4); }
    relationLabel(value) { return relationLabel(value); }
    dateLabel(value) { return dateLabel(value); }
    labelFor(value) { return labelFor(value); }

    get completion() {
        if (!this.state.profile) return 0;
        const p = this.state.profile;
        const contact = this.state.partner || {};
        const values = [
            p.display_name, p.campus_staff_code, p.campus_designation, p.campus_category,
            p.campus_service_type, p.campus_joining_date, contact.email, contact.mobile || contact.phone,
            contact.street || p.campus_communication_address, p.campus_work_location,
        ];
        return Math.round(values.filter(Boolean).length / values.length * 100);
    }

    get identityItems() {
        const p = this.state.profile || {};
        return [
            ["Staff name", labelFor(p.display_name)], ["Staff code", labelFor(p.campus_staff_code)],
            ["Department", relationLabel(p.main_department_id)], ["Designation", labelFor(p.campus_designation)],
            ["Employee category", relationLabel(p.campus_category)], ["Service type", relationLabel(p.campus_service_type)],
            ["Date of joining", dateLabel(p.campus_joining_date)], ["Blood group", labelFor(p.blood_group)],
            ["Community", labelFor(p.campus_community)], ["Caste", labelFor(p.campus_caste)],
            ["Caste name in certificate", labelFor(p.campus_caste_certificate_name)], ["Marital status", relationLabel(p.campus_marital_status)],
            ["Religion", labelFor(p.campus_religion)], ["Blood donor", p.campus_blood_donor ? "Yes" : "No"],
        ];
    }

    get contactItems() {
        const p = this.state.profile || {};
        const d = this.state.partner || {};
        const address = [d.street, d.street2, d.city, d.zip, relationLabel(d.state_id), relationLabel(d.country_id)]
            .filter((value) => value && value !== "Not provided").join(", ");
        return [
            ["Official email", labelFor(d.email)], ["Alternate email", labelFor(p.campus_alternate_email)],
            ["Mobile", labelFor(d.mobile || d.phone)], ["Alternate mobile", labelFor(p.campus_alternate_mobile)],
            ["Emergency contact", labelFor(p.campus_emergency_phone)], ["Residence", labelFor(p.campus_residence_location)],
            ["Residential address", address || "Not provided"], ["Communication address", labelFor(p.campus_communication_address)],
            ["Travel mode", labelFor(p.campus_travel_mode)], ["Father's name", labelFor(p.campus_father_name)],
            ["Mother's name", labelFor(p.campus_mother_name)], ["Spouse's name", labelFor(p.campus_spouse_name)],
        ];
    }

    get employmentItems() {
        const p = this.state.profile || {};
        const items = [
            ["Staff code", p.campus_staff_code], ["Designation", p.campus_designation],
            ["Employee category", relationLabel(p.campus_category)], ["Service type", relationLabel(p.campus_service_type)],
            ["Joining date", dateLabel(p.campus_joining_date)], ["Work location", p.campus_work_location],
            ["Reporting to", relationLabel(p.campus_reporting_id)], ["Registration reference", p.campus_registration_reference],
        ];
        if (this.state.canManage) items.push(
            ["PAN reference", p.campus_pan_reference], ["Aadhaar last four", p.campus_aadhaar_last4],
            ["Passport reference", p.campus_passport_reference], ["PF reference", p.campus_pf_reference],
            ["ESI reference", p.campus_esi_reference], ["Identification marks", p.campus_identification_marks],
        );
        return items.map(([label, value]) => [label, labelFor(value)]);
    }

    get extraItems() {
        const p = this.state.profile || {};
        return [["Anniversary", dateLabel(p.campus_anniversary)], ["Previous education", p.campus_previous_education], ["Notes", p.campus_notes]];
    }

    get reportingItems() {
        const p = this.state.profile || {};
        return [["Reporting to", relationLabel(p.campus_reporting_id)], ["Reporting department", relationLabel(p.main_department_id)],
            ["Work location", labelFor(p.campus_work_location)], ["Joining date", dateLabel(p.campus_joining_date)],
            ["Employment nature", relationLabel(p.campus_service_type)], ["Registration reference", labelFor(p.campus_registration_reference)]];
    }

    get previousEducationItems() {
        const p = this.state.profile || {};
        return [["Previous school / college / university details", labelFor(p.campus_previous_education)]];
    }

    get organizationItems() {
        const p = this.state.profile || {};
        return [["Department", relationLabel(p.main_department_id)], ["Work location", labelFor(p.campus_work_location)],
            ["Anniversary", dateLabel(p.campus_anniversary)], ["Notes / remarks", labelFor(p.campus_notes)]];
    }

    openFaculty() {
        return this.action.doAction({
            type: "ir.actions.act_window", name: "Staff profile", res_model: "op.faculty",
            res_id: this.state.selectedId, views: [[false, "form"]], target: "current",
        });
    }

    openRegister(kind = false) {
        return this.action.doAction({
            type: "ir.actions.act_window", name: "Staff qualifications and documents",
            res_model: "campus.faculty.detail", views: [[false, "tree"], [false, "form"]],
            domain: [["faculty_id", "=", this.state.selectedId], ...(kind ? [["kind", "=", kind]] : [])],
            context: { default_faculty_id: this.state.selectedId, ...(kind ? { default_kind: kind } : {}) },
            target: "current",
        });
    }

    openDetail(record) {
        return this.action.doAction({
            type: "ir.actions.act_window", name: record.display_name || "Staff record",
            res_model: "campus.faculty.detail", res_id: record.id, views: [[false, "form"]], target: "current",
        });
    }
}

registry.category("actions").add("ideastone_erp.faculty_profile", CampusFacultyProfile);
