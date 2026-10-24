/** @odoo-module **/
import { Component, onWillStart, useRef, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StudentsDirectoryWorkspace extends Component {
    static template = "ideastone_erp.StudentsDirectoryWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.router = useService("router"); this.notification = useService("notification");
        this.content = useRef("content"); this.request = 0;
        this.view = this.props.action.params?.view || "directory";
        const hash = this.router.current.hash;
        const filters = {};
        for (const key of ["year_id", "department_id", "batch_id"]) {
            if (hash["students_" + key] !== undefined) filters[key] = hash["students_" + key];
        }
        this.state = useState({screen: this.view === "enrolments" ? "enrolments" : ["all", "department"].includes(hash.students_screen) ? hash.students_screen : "directory",
            data: null, loading: true, error: "", filters, filterOpen: false, query: "", page: 0});
        onWillStart(() => this.load());
    }
    get title() { return {directory: "Student directory", all: "All students", department: this.department?.name || "Department workspace", enrolments: "Enrolments & Transfers"}[this.state.screen]; }
    get c() { return this.state.data.counts; }
    get department() { return this.state.data?.departments.find(r => r.id === Number(this.state.filters.department_id)); }
    get sections() { return this.state.data.sections.filter(r => (!this.state.filters.department_id || r.department_id === Number(this.state.filters.department_id)) && (!this.state.filters.study_year || r.study_year === Number(this.state.filters.study_year))); }
    get studyYears() { return [...new Set(this.state.data.sections.filter(r => r.department_id === Number(this.state.filters.department_id)).map(r => r.study_year).filter(Boolean))].sort((a,b) => a-b); }
    get departments() {
        const f = this.state.filters;
        return this.state.data.departments.filter(r => (!f.department_id || r.id === Number(f.department_id)) &&
            (!f.capacity || r.fill !== null && (f.capacity === "under80" ? r.fill < 80 : f.capacity === "80to89" ? r.fill >= 80 && r.fill < 90 : r.fill >= 90)) &&
            (!f.section_size || (f.section_size === "small" ? r.sections >= 2 && r.sections <= 4 : r.sections >= 5)));
    }
    get leadingSections() { return [...this.state.data.sections].sort((a,b) => b.count-a.count || a.name.localeCompare(b.name)).slice(0,4); }
    get stats() {
        return this.state.screen === "enrolments" ? [
            {label: "Running enrolments", value: this.c.running, icon: "check", detail: "Saved placements in the selected academic scope"},
            {label: "Placements needing details", value: this.c.incomplete, icon: "clock-o", detail: "Academic year, semester or section missing", warn: true},
            {label: "Movement history", value: this.c.history, icon: "exchange", detail: "Placements with an end date or recorded reason"},
            {label: "New enrolments", value: this.c.new_enrolments, icon: "arrow-up", detail: "Created in the selected academic year"},
        ] : [
            {label: "Total students", value: this.c.total, icon: "users", detail: "Saved student records in this academic scope"},
            {label: "Currently active", value: this.c.active, icon: "check", detail: `${this.percent(this.c.total ? this.c.active / this.c.total * 100 : null)} of scoped student records`},
            {label: this.state.data.new_label, value: this.c.new, icon: "star-o", detail: "Students with a recorded admission date"},
            {label: "Records needing attention", value: this.c.attention, icon: "exclamation", detail: "Review contact, registration or placement details", warn: true},
        ];
    }
    async load() {
        const request = ++this.request;
        this.state.loading = true; this.state.error = "";
        try {
            const data = await this.orm.call("campus.students.ui", "get_workspace", [this.view, this.state.filters, this.state.query, this.state.page]);
            if (request !== this.request) return;
            this.state.data = data; this.state.filters = {...data.filters};
            this.router.pushState({students_screen: this.state.screen, students_year_id: data.filters.year_id,
                students_department_id: data.filters.department_id, students_batch_id: data.filters.batch_id});
        } catch (error) {
            if (request === this.request) this.state.error = error.data?.message || "The student directory could not be loaded. Please retry.";
        } finally { if (request === this.request) this.state.loading = false; }
    }
    async show(screen, department = 0) {
        this.state.screen = screen; this.state.query = ""; this.state.page = 0; this.state.filterOpen = false;
        Object.assign(this.state.filters, {department_id: department, batch_id: 0, status: "", study_year: 0, attention: false, capacity: "", section_size: ""});
        await this.load(); if (this.content.el) this.content.el.scrollTop = 0;
    }
    async filter() { this.state.page = 0; await this.load(); }
    async applyEnrolmentFilters() { await this.filter(); this.state.filterOpen = false; }
    async yearChanged() { this.state.filters.batch_id = 0; this.state.filters.study_year = 0; await this.filter(); }
    async departmentChanged() { this.state.filters.batch_id = 0; await this.filter(); }
    async chooseSection(section) {
        this.state.filters.batch_id = section.id; await this.filter();
        this.content.el?.querySelector(".roster-heading")?.scrollIntoView({block: "start", behavior: "smooth"});
    }
    async showSection(section) {
        await this.show("department", section.department_id);
        await this.chooseSection(section);
    }
    async reviewProfiles() { await this.show("all"); this.state.filters.attention = true; await this.filter(); }
    async resetFilters() {
        Object.assign(this.state.filters, {department_id: this.state.screen === "department" ? this.state.filters.department_id : 0,
            batch_id: 0, study_year: 0, status: "", attention: false, capacity: "", section_size: "", record_type: "", submitted: ""});
        this.state.query = ""; await this.filter();
    }
    async paginate(delta) { this.state.page += delta; await this.load(); }
    async open(kind, recordId = null, create = false) {
        try {
            const action = await this.orm.call("campus.students.ui", "get_record_action", [kind, recordId, create]);
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || "This record is unavailable. Check your access and retry.", {type: "danger"}); }
    }
    number(value) { return value === null || value === undefined ? "—" : new Intl.NumberFormat("en-IN", {maximumFractionDigits: 1}).format(value); }
    percent(value) { return value === null || value === undefined ? "—" : this.number(value) + "%"; }
    bar(value) { return `width:${Math.min(100, Math.max(0, Number(value) || 0))}%`; }
    initials(name) { return String(name || "").trim().split(/\s+/).slice(0,2).map(word => word[0] || "").join(""); }
    async exportRows(kind = "students") {
        try {
            let columns, rows, filename;
            if (kind === "departments") {
                columns = ["Department", "Code", "Students", "Capacity", "Active", "Inactive / review", "Seats available", "Sections", "Capacity filled (%)"];
                rows = this.departments.map(r => [r.name, r.code, r.count, r.capacity || "", r.active, r.inactive, r.available, r.sections, r.fill]);
                filename = "department-strength.csv";
            } else {
                const data = await this.orm.call("campus.students.ui", "get_workspace", [this.view, this.state.filters, this.state.query, 0], {export: true});
                if (this.view === "enrolments") {
                    columns = ["Record", "Student", "Register number", "Type", "Programme", "Section", "Academic year", "Effective from", "Effective until", "Created", "Status", "Reason"];
                    rows = data.rows.map(r => [r.reference,r.name,r.register,r.type,r.programme,r.section,r.year,r.effective,r.until,r.submitted,r.status,r.reason]);
                    filename = "enrolments-and-transfers.csv";
                } else {
                    columns = ["Student", "Register number", "Department", "Programme", "Academic year", "Semester", "Section", "Email", "Status", "Last updated"];
                    rows = data.rows.map(r => [r.name,r.register,r.department,r.programme,r.year,r.semester,r.section,r.email,r.status,r.updated]);
                    filename = this.state.screen === "department" ? "student-roster.csv" : "student-directory.csv";
                }
            }
            const quote = value => '"' + String(value ?? "").replace(/^[\s]*[=+@-]/, text => "'" + text).replaceAll('"', '""') + '"';
            const csv = "\uFEFF" + [columns, ...rows].map(row => row.map(quote).join(",")).join("\r\n");
            const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
            const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) { this.notification.add(error.data?.message || "This export could not be prepared.", {type: "danger"}); }
    }
}
registry.category("actions").add("ideastone_erp.students_directory", StudentsDirectoryWorkspace);
