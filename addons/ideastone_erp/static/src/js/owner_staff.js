/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FacultyLeavePage } from "@ideastone_erp/js/faculty_leave";
import { PayrollHistoryPage } from "@ideastone_erp/js/payroll_history";

export class OwnerStaffDirectory extends Component {
    static template = "ideastone_erp.OwnerStaffDirectory";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.company = useService("company");
        this.state = useState({loading: true, error: "", data: null, screen: "overview", department: "",
            category: "teaching", person: "", query: "", designation: "", status: ""});
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.owner.staff.ui", "get_directory", []);
            if (this.state.department && !this.department) this.state.screen = "overview";
            if (this.state.screen === "profile" && !this.selectedPerson) this.state.screen = "list";
        } catch (error) {
            this.state.error = error.data?.message || "Staff records could not be loaded. Please retry.";
        } finally { this.state.loading = false; }
    }
    get rows() { return this.state.data?.rows || []; }
    get department() { return this.state.data?.departments.find((item) => item.key === this.state.department); }
    get selectedPerson() { return this.rows.find((item) => item.key === this.state.person); }
    get teaching() { return this.rows.filter((item) => item.category === "teaching").length; }
    get active() { return this.rows.filter((item) => item.status === "Active").length; }
    get categoryLabel() { return this.state.category === "teaching" ? "Teaching staff" : "Non-teaching staff"; }
    get categoryRows() { return this.rows.filter((item) => item.department_key === this.state.department && item.category === this.state.category); }
    get designations() { return [...new Set(this.categoryRows.map((item) => item.designation))].sort(); }
    get filteredRows() {
        const query = this.state.query.trim().toLocaleLowerCase();
        return this.categoryRows.filter((item) => (!this.state.designation || item.designation === this.state.designation) &&
            (!this.state.status || item.status === this.state.status) &&
            (!query || [item.name, item.code, item.designation, item.email].some((value) => value.toLocaleLowerCase().includes(query))));
    }
    selectDepartment(department) { this.state.department = department.key; this.state.screen = "categories"; }
    selectCategory(category) {
        Object.assign(this.state, {category, screen: "list", query: "", designation: "", status: ""});
    }
    openProfile(person) { this.state.person = person.key; this.state.screen = "profile"; }
    initials(name) { return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase(); }
    percent(department) { return department.total ? Math.round(100 * department.teaching / department.total) : 0; }
    departmentIcon(department) {
        return "fa " + ({CSE: "fa-code", ECE: "fa-signal", EEE: "fa-bolt", MECH: "fa-cogs",
            CIVIL: "fa-building-o", IT: "fa-server", BME: "fa-heartbeat", ADMIN: "fa-th-large"}[department.code] || "fa-university");
    }
    date(value) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric"}) : "—"; }
    get profileSections() {
        const person = this.selectedPerson;
        if (!person) return [];
        return [{title: "Personal details", fields: [["Full name", person.name], ["Staff category", this.categoryLabel],
            ["Gender", person.gender], ["Date of birth", this.date(person.birth_date)]]},
        {title: "Work & contact", fields: [["Department", person.department], ["Designation", person.designation],
            ["Email", person.email], ["Phone", person.phone], ["Employment type", person.employment],
            ["Joining date", this.date(person.joining_date)]]}];
    }
    manageStaff() {
        return this.action.doAction({type: "ir.actions.act_window", name: "Staff records", res_model: "op.faculty",
            views: [[false, "tree"], [false, "form"]], domain: [["company_id", "in", [false, this.company.currentCompany.id]]],
            context: {campus_module: "staff", default_company_id: this.company.currentCompany.id}});
    }
    openRecord() {
        return this.action.doAction({type: "ir.actions.act_window", name: this.selectedPerson.name, res_model: this.selectedPerson.model,
            res_id: this.selectedPerson.id, views: [[false, "form"]], context: {campus_module: "staff"}});
    }
}

export class OwnerStaffLeave extends FacultyLeavePage {
    static template = "ideastone_erp.OwnerStaffLeave";
    setup() {
        super.setup();
        this.action = useService("action");
        this.review = useState({rows: [], error: "", busy: false});
    }
    async load() {
        await super.load();
        this.review.error = "";
        try { this.review.rows = await this.orm.call("campus.owner.staff.ui", "get_leave_queue", []); }
        catch (error) { this.review.error = error.data?.message || "The approval queue could not be loaded."; }
    }
    async decide(record, decision) {
        if (this.review.busy) return;
        this.review.busy = true;
        try {
            await this.orm.call("campus.owner.staff.ui", "review_leave", [record.id, decision]);
            await this.load();
            this.notification.add(decision === "approve" ? "Leave approval recorded." : "Leave refusal recorded.", {type: "success"});
        } catch (error) { this.notification.add(error.data?.message || "The decision could not be saved.", {type: "danger"}); }
        finally { this.review.busy = false; }
    }
    reviewRecord(record) {
        return this.action.doAction({type: "ir.actions.act_window", name: "Leave request", res_model: "hr.leave",
            res_id: record.id, views: [[false, "form"]], target: "new"});
    }
}

export class OwnerStaffPayroll extends PayrollHistoryPage {
    static template = "ideastone_erp.OwnerStaffPayroll";
    get reportTitle() { return this.state.mode === "salary" ? "Salary Summary" : this.state.mode === "deductions" ? "Deductions Summary" : "Payroll History"; }
    changeMode(event) { this.state.mode = event.target.value; }
    exportCsv() {
        const columns = [["Staff", () => this.state.employeeName], ["Month", row => this.rowMonth(row)], ["Year", row => this.rowYear(row)]];
        if (this.state.mode !== "deductions") columns.push([`Net Salary (${this.state.currencyCode})`, row => row.net]);
        if (this.state.mode !== "salary") columns.push(["Late Days", row => row.late_days],
            [`Late Deduction (${this.state.currencyCode})`, row => row.late_deduction],
            [`PF (${this.state.currencyCode})`, row => row.pf], [`TDS (${this.state.currencyCode})`, row => row.tds]);
        const rows = [columns.map(([label]) => label), ...this.visibleRows.map(row => columns.map(([_label, value]) => value(row)))];
        const csv = "\ufeff" + rows.map(row => row.map(value => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = `payroll-${this.state.mode}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.owner_staff_directory", OwnerStaffDirectory);
registry.category("actions").add("ideastone_erp.owner_staff_leave", OwnerStaffLeave);
registry.category("actions").add("ideastone_erp.owner_staff_payroll", OwnerStaffPayroll);
