/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const PAGE_SIZE = 5;

export class MentorODReview extends Component {
    static template = "ideastone_erp.MentorODReview";
    static components = { Dialog };
    static props = ["workspace", "close"];
}

export class StaffODManagement extends Component {
    static template = "ideastone_erp.StaffODManagement";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            loading: true, saving: false, error: "", data: null, classKey: "",
            search: "", page: 1, period: "week", note: "", selectedId: null,
            types: {}, approvedPage: 1, withheldPage: 1, approvedAll: false, withheldAll: false, hodDialog: null,
            pendingAll: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        const request = this.loadRequest = (this.loadRequest || 0) + 1;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.staff.od.ui", "get_page_data", [this.state.classKey || null]);
            if (request !== this.loadRequest) return;
            this.state.data = data;
            this.state.classKey = data.class_key;
            if (data.role === "hod") {
                for (const row of data.rows) this.state.types[row.id] = row.category === "undetermined" ? "" : row.category;
            }
            if (!data.rows.some((row) => row.id === this.state.selectedId)) {
                this.state.note = "";
                this.closeReview?.();
                this.state.selectedId = data.rows.find((row) => row.can_review)?.id || data.rows[0]?.id || null;
            }
            this.state.page = Math.min(this.state.page, Math.max(1, Math.ceil(this.filteredRows.length / PAGE_SIZE)));
        } catch (error) {
            if (request === this.loadRequest) {
                this.state.error = error.data?.message || "Mentor OD requests could not be loaded. Please try again.";
            }
        } finally {
            if (request === this.loadRequest) this.state.loading = false;
        }
    }

    async changeClass(event) {
        this.state.classKey = event.target.value;
        this.state.page = 1;
        this.state.selectedId = null;
        this.state.note = "";
        this.closeReview?.();
        this.state.pendingAll = false;
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

    get approvedRows() {
        const rows = this.state.data?.approved_rows || [];
        return this.state.approvedAll ? rows : rows.slice((this.state.approvedPage - 1) * PAGE_SIZE, this.state.approvedPage * PAGE_SIZE);
    }

    get withheldRows() {
        const rows = this.state.data?.withheld_rows || [];
        return this.state.withheldAll ? rows : rows.slice((this.state.withheldPage - 1) * PAGE_SIZE, this.state.withheldPage * PAGE_SIZE);
    }

    get selectedRow() {
        return this.state.data?.rows.find((row) => row.id === this.state.selectedId) || null;
    }

    get chartRows() {
        return this.state.period === "week" ? this.state.data?.week_activity || [] : this.state.data?.month_activity || [];
    }

    get hasActivity() {
        return this.chartRows.some((row) => row.count > 0);
    }

    get pendingRows() {
        return (this.state.data?.rows || []).filter((row) => row.can_review)
            .sort((first, second) => first.date_from.localeCompare(second.date_from) || first.id - second.id);
    }

    get pendingActions() {
        return this.state.pendingAll ? this.pendingRows : this.pendingRows.slice(0, 4);
    }

    get insights() {
        const data = this.state.data;
        return [
            { key: "repeated", tone: "violet", title: "1. Repeated OD Asking Students", value: data.repeated_students,
                note: data.repeated_students ? "Students with more than one OD request this semester. Check their request history before deciding." : "No students flagged for repeated OD requests this semester." },
            { key: "overlap", tone: "amber", title: "2. Overlapping Date Students", value: data.overlapping_students,
                note: data.overlapping_students ? "Students with overlapping active OD dates. Check class coverage before forwarding." : "No overlapping active OD dates found among students in this class." },
            { key: "urgent", tone: "teal", title: "3. Urgent Reviews", value: data.urgent_reviews,
                note: data.urgent_reviews ? "Pending requests with an event in the next two days or an event date already passed." : "No pending requests need review for an event within the next two days." },
        ];
    }

    datePart(value, part) {
        return new Intl.DateTimeFormat("en-IN", part === "day" ? { day: "2-digit" } : { month: "short" })
            .format(new Date(`${value}T00:00:00`));
    }

    dueStatus(row) {
        const date = Date.parse(`${row.date_from}T00:00:00Z`);
        const today = Date.parse(`${this.state.data.today}T00:00:00Z`);
        const days = Math.round((date - today) / 86400000);
        if (days < 0) return { label: "Event passed", tone: "overdue" };
        if (days === 0) return { label: "Due today", tone: "urgent" };
        if (days === 1) return { label: "Due tomorrow", tone: "pending" };
        return { label: days <= 2 ? "Due soon" : "Upcoming", tone: days <= 2 ? "pending" : "upcoming" };
    }

    mentorStatus(row) {
        return row.state === "pending_mentor" ? "Pending" : row.state === "completed" ? "Approved" : row.status;
    }

    formatTimestamp(value) {
        return value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short",
            timeZone: this.state.data.timezone || "UTC" }).format(new Date(`${value.replace(" ", "T")}Z`)) : "—";
    }

    openMentorRequest(row) {
        this.selectRow(row);
        this.closeReview?.();
        this.closeReview = this.dialog.add(MentorODReview, { workspace: this }, {
            onClose: () => { this.closeReview = null; },
        });
    }

    closeMentorDialog() {
        if (!this.state.saving) this.closeReview?.();
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

    setListPage(kind, page) {
        const key = kind === "approved" ? "approvedPage" : "withheldPage";
        const count = this.state.data?.[`${kind}_rows`]?.length || 0;
        this.state[key] = Math.max(1, Math.min(page, Math.max(1, Math.ceil(count / PAGE_SIZE))));
    }

    toggleListAll(kind) {
        const key = kind === "approved" ? "approvedAll" : "withheldAll";
        this.state[key] = !this.state[key];
        this.setListPage(kind, 1);
    }

    setHodType(row, event) {
        this.state.types[row.id] = event.target.value;
    }

    openHodDecision(row, decision) {
        this.state.selectedId = row.id;
        this.state.hodDialog = {
            id: row.id, reference: row.reference, decision,
            category: this.state.types[row.id] || (row.category === "undetermined" ? "" : row.category),
            note: "", requirements: row.proof_requirements || "",
            deadline: row.proof_deadline || "",
        };
    }

    async downloadHodProof() {
        const id = this.state.hodDialog?.id;
        if (!id) return;
        try {
            const proof = await this.orm.call("campus.hod.od.ui", "get_proof", [id]);
            const bytes = Uint8Array.from(atob(proof.content), (char) => char.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([bytes], {type: proof.mimetype}));
            const link = document.createElement("a");
            link.href = url;
            link.download = proof.filename;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) {
            this.notification.add(error.data?.message || "The submitted proof could not be opened.", {type: "danger"});
        }
    }

    async submitHodDecision() {
        const dialog = this.state.hodDialog;
        if (!dialog || this.state.saving) return;
        this.state.saving = true;
        try {
            await this.orm.call("campus.hod.od.ui", "decide", [
                dialog.id, dialog.decision, dialog.category, dialog.note,
                dialog.requirements, dialog.deadline,
            ]);
            this.state.hodDialog = null;
            await this.load();
            this.notification.add("HOD decision saved.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || "The HOD decision could not be saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
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
            this.closeReview?.();
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
        link.download = `${this.state.data?.role === "hod" ? "hod" : "mentor"}-od-activity-${this.state.period}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.staff_od_management", StaffODManagement);
