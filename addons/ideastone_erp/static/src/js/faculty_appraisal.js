/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SECTIONS = [
    { key: "research", label: "Research", kind: "mphil", title: "Students Register for M.Phil under your supervision", kinds: ["mphil", "paper", "patent"] },
    { key: "reviews", label: "Reviews, Editorial, Participation, Consultancy", kind: "review", title: "Reviews, editorial and consultancy", kinds: ["review", "mou", "award", "appraisal"] },
    { key: "training", label: "Training Programmes", kind: "training", title: "Training programmes", kinds: ["training", "fdp"] },
    { key: "vacation", label: "Summer / Winter Vacation Course attended", kind: "vacation", title: "Vacation courses attended", kinds: ["vacation"] },
    { key: "mooc", label: "MOOC", kind: "mooc", title: "MOOC courses", kinds: ["mooc"] },
    { key: "qualified", label: "Qualified Courses", kind: "qualified", title: "Qualified courses", kinds: ["qualified"] },
    { key: "guest", label: "Guest Lecture/Participation", kind: "guest", title: "Guest lectures and participation", kinds: ["guest"] },
    { key: "resource", label: "Resource Personnel", kind: "resource", title: "Resource personnel activities", kinds: ["resource"] },
];

const today = () => new Date().toISOString().slice(0, 10);
const emptyForm = () => ({ id: null, kind: "", name: "", date: today(), remarks: "" });
const relationId = (value) => Array.isArray(value) ? value[0] : value;

export class FacultyAppraisal extends Component {
    static template = "ideastone_erp.FacultyAppraisal";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loading: true, saving: false, error: "", staff: [], records: [],
            section: "research", companyId: "", departmentId: "", facultyId: "", form: emptyForm(),
        });
        onWillStart(() => this.load());
    }

    get sections() { return SECTIONS; }
    get activeSection() { return SECTIONS.find((item) => item.key === this.state.section) || SECTIONS[0]; }
    get companies() {
        const seen = new Map();
        for (const staff of this.state.staff) if (Array.isArray(staff.company_id)) seen.set(staff.company_id[0], staff.company_id[1]);
        return [...seen].map(([id, name]) => ({ id, name }));
    }
    get departments() {
        const seen = new Map();
        for (const staff of this.state.staff) {
            if (this.state.companyId && String(relationId(staff.company_id)) !== this.state.companyId) continue;
            if (Array.isArray(staff.main_department_id)) seen.set(staff.main_department_id[0], staff.main_department_id[1]);
        }
        return [...seen].map(([id, name]) => ({ id, name }));
    }
    get visibleStaff() {
        return this.state.staff.filter((staff) =>
            (!this.state.companyId || String(relationId(staff.company_id)) === this.state.companyId) &&
            (!this.state.departmentId || String(relationId(staff.main_department_id)) === this.state.departmentId));
    }
    get selectedStaff() { return this.state.staff.find((staff) => String(staff.id) === this.state.facultyId); }
    get rows() {
        return this.state.records.filter((record) =>
            this.activeSection.kinds.includes(record.kind) &&
            (!this.state.facultyId || String(relationId(record.faculty_id)) === this.state.facultyId));
    }
    get portfolio() {
        const records = this.state.records.filter((record) =>
            !this.state.facultyId || String(relationId(record.faculty_id)) === this.state.facultyId);
        const publications = records.filter((record) => ["paper", "patent"].includes(record.kind)).length;
        const conferences = records.filter((record) => ["guest", "review", "resource"].includes(record.kind)).length;
        const courses = records.filter((record) => ["fdp", "training", "vacation", "mooc", "qualified"].includes(record.kind)).length;
        const evidenced = records.filter((record) => record.filename).length;
        return { publications, conferences, courses, evidenced, total: records.length,
            score: records.length ? Math.round(100 * evidenced / records.length) : 0 };
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const [staff, records] = await Promise.all([
                this.orm.searchRead("op.faculty", [["active", "=", true]],
                    ["display_name", "company_id", "main_department_id"], { order: "display_name" }),
                this.orm.searchRead("campus.faculty.achievement", [],
                    ["name", "faculty_id", "kind", "date_from", "description", "filename", "state"],
                    { order: "date_from desc, id desc", limit: 500 }),
            ]);
            this.state.staff = staff;
            this.state.records = records;
            if (!staff.some((item) => String(item.id) === this.state.facultyId)) {
                this.state.facultyId = staff.length ? String(staff[0].id) : "";
            }
        } catch (error) {
            this.state.error = error.data?.message || "Appraisal records could not be loaded. Check your access and try again.";
        } finally { this.state.loading = false; }
    }

    selectSection(key) { this.state.section = key; this.state.form = emptyForm(); }
    selectCompany(event) {
        this.state.companyId = event.target.value;
        this.state.departmentId = "";
        this.state.facultyId = String(this.visibleStaff[0]?.id || "");
        this.state.form = emptyForm();
    }
    selectDepartment(event) {
        this.state.departmentId = event.target.value;
        this.state.facultyId = String(this.visibleStaff[0]?.id || "");
        this.state.form = emptyForm();
    }
    selectFaculty(event) { this.state.facultyId = event.target.value; this.state.form = emptyForm(); }
    selectRecord(id) {
        const record = this.state.records.find((item) => item.id === id);
        if (record?.state !== "draft") {
            this.notification.add("Only draft records can be edited here. Open Records to review this entry.", { type: "warning" });
            return;
        }
        if (record) this.state.form = { id, kind: record.kind, name: record.name, date: record.date_from, remarks: record.description || "" };
    }
    async save(event) {
        event.preventDefault();
        const form = this.state.form;
        if (!this.state.facultyId || !form.name.trim() || !form.date) {
            this.notification.add("Choose a staff member and enter a name and date.", { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            const values = { name: form.name.trim(), faculty_id: Number(this.state.facultyId),
                kind: form.kind || this.activeSection.kind, date_from: form.date, description: form.remarks.trim() };
            if (form.id) await this.orm.write("campus.faculty.achievement", [form.id], values);
            else await this.orm.create("campus.faculty.achievement", [values]);
            this.state.form = emptyForm();
            await this.load();
            this.notification.add("Appraisal record saved.", { type: "success" });
        } catch (error) {
            this.notification.add(error.data?.message || "The record could not be saved.", { type: "danger" });
        } finally { this.state.saving = false; }
    }
    refresh() { this.state.form = emptyForm(); return this.load(); }
    openRecords() { return this.action.doAction("ideastone_erp.action_faculty_achievement"); }
}

registry.category("actions").add("ideastone_erp.faculty_appraisal", FacultyAppraisal);
