/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PAGE_SIZE = 5;

export class StaffODManagement extends Component {
    static template = "ideastone_erp.StaffODManagement";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, saving: false, error: "", data: null, classKey: "",
            search: "", page: 1, period: "week", note: "", selectedId: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.staff.od.ui", "get_page_data", [this.state.classKey || null]);
            this.state.data = data;
            this.state.classKey = data.class_key;
            if (!data.rows.some((row) => row.id === this.state.selectedId)) {
                this.state.selectedId = data.rows.find((row) => row.can_review)?.id || data.rows[0]?.id || null;
            }
            this.state.page = Math.min(this.state.page, Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE)));
        } catch (error) {
            this.state.error = error.data?.message || "Mentor OD requests could not be loaded. Please try again.";
        } finally {
            this.state.loading = false;
        }
    }

    async changeClass(event) {
        this.state.classKey = event.target.value;
        this.state.page = 1;
        this.state.selectedId = null;
        await this.load();
    }

    changeSearch(event) {
        this.state.search = event.target.value;
        this.state.page = 1;
    }

    get filteredRows() {
        const query = this.state.search.trim().toLowerCase();
        const rows = this.state.data?.rows || [];
        return query ? rows.filter((row) =>
            `${row.reference} ${row.student} ${row.name} ${row.purpose}`.toLowerCase().includes(query)
        ) : rows;
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE));
    }

    get pageRows() {
        return this.filteredRows.slice((this.state.page - 1) * PAGE_SIZE, this.state.page * PAGE_SIZE);
    }

    get selectedRow() {
        return this.state.data?.rows.find((row) => row.id === this.state.selectedId) || null;
    }

    get chartRows() {
        return this.state.period === "week" ? this.state.data?.week_activity || [] : this.state.data?.month_activity || [];
    }

    chartHeight(value) {
        const max = Math.max(1, ...this.chartRows.map((row) => row.count));
        return `${Math.round(value * 100 / max)}%`;
    }

    formatDate(value) {
        if (!value) return "—";
        const date = new Date(`${value.slice(0, 10)}T00:00:00`);
        return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(date);
    }

    get workflowStep() {
        const state = this.selectedRow?.state;
        return ({ draft: 1, returned: 1, pending_mentor: 2, pending_hod: 3,
            withheld: 4, proof_review: 4, completed: 5, rejected: 2, invalid: 4 })[state] || 0;
    }

    selectRow(row) {
        if (this.state.selectedId !== row.id) {
            this.state.note = "";
        }
        this.state.selectedId = row.id;
    }

    setPage(page) {
        this.state.page = Math.max(1, Math.min(page, this.pageCount));
    }

    async review(row, decision) {
        if (this.state.saving || !row.can_review) return;
        if (this.state.selectedId !== row.id) {
            this.state.selectedId = row.id;
            if (this.state.note.trim()) {
                this.state.note = "";
                this.notification.add("The previous request's review note was cleared. Review this request before deciding.", { type: "info" });
                return;
            }
        }
        const note = this.state.note.trim();
        if (decision === "return" && !note) {
            this.state.selectedId = row.id;
            this.notification.add("Add a review note before returning this request to the student.", { type: "warning" });
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("campus.staff.od.ui", "review_request", [row.id, decision, note]);
            this.state.note = "";
            this.state.selectedId = row.id;
            await this.load();
            this.notification.add(decision === "forward" ? "Request forwarded to HOD." : "Request returned to the student.", { type: "success" });
        } catch (error) {
            this.notification.add(error.data?.message || "The decision could not be saved. Refresh and try again.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    exportActivity() {
        const rows = this.chartRows;
        const csv = ["Period,OD requests", ...rows.map((row) => `${row.label} ${row.sub},${row.count}`)].join("\n");
        const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = `mentor-od-activity-${this.state.period}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.staff_od_management", StaffODManagement);
