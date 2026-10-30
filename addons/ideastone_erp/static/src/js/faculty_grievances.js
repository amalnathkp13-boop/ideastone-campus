/** @odoo-module **/
import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PAGE_SIZE = 8;
const freshForm = () => ({subject: "", category: "", priority: "medium", incident_date: "", description: "", contact: ""});

export class FacultyGrievances extends Component {
    static template = "ideastone_erp.FacultyGrievances";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.modalRef = useRef("modal");
        this.state = useState({loading: true, saving: false, error: "", rows: [], today: "", company: "",
            search: "", category: "all", status: "all", tab: "all", page: 1, modal: "", selected: null,
            form: freshForm()});
        onWillStart(() => this.load());
        useEffect(() => {
            if (this.state.modal) this.modalRef.el?.querySelector(this.state.modal === "new" ? "input" : "button")?.focus();
        }, () => [this.state.modal]);
        useExternalListener(window, "keydown", (event) => {
            if (!this.state.modal) return;
            if (event.key === "Escape") this.closeModal();
            if (event.key !== "Tab") return;
            const focusable = [...this.modalRef.el?.querySelectorAll("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)") || []];
            if (!focusable.length) return;
            const next = event.shiftKey ? focusable.at(-1) : focusable[0];
            if (document.activeElement === (event.shiftKey ? focusable[0] : focusable.at(-1))) {
                event.preventDefault();
                next.focus();
            }
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.service.request", "faculty_grievance_snapshot", []);
            this.state.rows = data.rows;
            this.state.today = data.today;
            this.state.company = data.company;
            this.state.page = Math.min(this.state.page, this.pageCount);
        } catch (error) {
            this.state.error = error.data?.message || "Grievances could not be loaded. Check your access and retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get counts() {
        const rows = this.state.rows;
        return {total: rows.length, open: rows.filter((row) => row.tone === "open").length,
            progress: rows.filter((row) => row.tone === "progress").length,
            resolved: rows.filter((row) => row.tone === "resolved").length};
    }

    get categories() { return [...new Set(this.state.rows.map((row) => row.category))].sort(); }

    get filteredRows() {
        const search = this.state.search.trim().toLowerCase();
        return this.state.rows.filter((row) =>
            (this.state.tab === "all" || row.status === this.state.tab) &&
            (this.state.status === "all" || row.status === this.state.status) &&
            (this.state.category === "all" || row.category === this.state.category) &&
            (!search || `${row.reference} ${row.subject} ${row.category}`.toLowerCase().includes(search))
        );
    }

    get pageCount() { return Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE)); }
    get pageRows() { return this.filteredRows.slice((this.state.page - 1) * PAGE_SIZE, this.state.page * PAGE_SIZE); }
    changeFilter() { this.state.page = 1; }
    setTab(tab) { this.state.tab = tab; this.state.status = "all"; this.state.page = 1; }
    setPage(page) { this.state.page = Math.min(this.pageCount, Math.max(1, page)); }
    formatDate(value) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric"}) : "—"; }
    openNew() { this.returnFocus = document.activeElement; this.state.form = freshForm(); this.state.modal = "new"; }
    openDetails(row) { this.returnFocus = document.activeElement; this.state.selected = row; this.state.modal = "details"; }
    closeModal() { this.state.modal = ""; this.state.selected = null; this.returnFocus?.focus(); }
    backdrop(event) { if (event.target === event.currentTarget) this.closeModal(); }

    async submit() {
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            await this.orm.call("campus.service.request", "faculty_grievance_submit", [{...this.state.form}]);
            this.closeModal();
            this.setTab("all");
            this.state.category = "all";
            this.state.search = "";
            await this.load();
            this.notification.add("Your grievance was submitted to the campus team.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || "The grievance could not be submitted.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("ideastone_erp.faculty_grievances", FacultyGrievances);
