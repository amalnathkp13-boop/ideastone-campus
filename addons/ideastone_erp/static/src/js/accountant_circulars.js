/** @odoo-module **/
import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const CATEGORIES = [{key: "fees", label: "Fees"}, {key: "exam", label: "Examination"}, {key: "event", label: "Event"}, {key: "general", label: "General"}];
const AUDIENCES = [{key: "student", label: "Students"}, {key: "student_parent", label: "Students & guardians"}, {key: "faculty", label: "Staff"}];
const STATUSES = [{key: "all", label: "All"}, {key: "draft", label: "Draft"}, {key: "scheduled", label: "Scheduled"}, {key: "published", label: "Published"}, {key: "archived", label: "Archived"}];

export class AccountantFeeCirculars extends Component {
    static template = "ideastone_erp.AccountantFeeCirculars";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.router = useService("router");
        this.modalRef = useRef("feeModal"); this.registerRef = useRef("circularRegister"); this.newRef = useRef("newCircularButton");
        const filter = this.router.current.hash.fee_status;
        this.state = useState({data: {rows: [], counts: {}, departments: [], year: "", today: "", timezone: ""},
            query: "", audience: "", category: "", status: STATUSES.some(s => s.key === filter) ? filter : "all",
            page: 0, loading: false, error: "", modal: false, form: {}, detail: null, saving: false, formError: "", success: ""});
        onWillStart(() => this.load());
        useEffect(() => {
            if (this.state.modal) this.modalRef.el?.querySelector("input")?.focus();
        }, () => [this.state.modal]);
        useEffect(() => {
            if (!this.state.success) return;
            const timer = setTimeout(() => { this.state.success = ""; }, 3000);
            return () => clearTimeout(timer);
        }, () => [this.state.success]);
        useExternalListener(window, "keydown", event => {
            if (!this.state.modal) return;
            if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); this.closeModal(); }
            if (event.key === "Tab") {
                const controls = [...this.modalRef.el.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)')];
                const first = controls[0], last = controls[controls.length - 1];
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
            }
        }, {capture: true});
    }
    get categories() { return CATEGORIES; }
    get audiences() {
        return [...AUDIENCES, ...[{key: "parent", label: "Guardians"}, {key: "all", label: "Everyone"}]
            .filter(a => this.state.form.audience === a.key || this.state.data.rows.some(row => row.audience === a.key))];
    }
    get statuses() { return STATUSES; }
    get readonly() { return !!this.state.detail && this.state.detail.status !== "draft"; }
    get rows() {
        const s = this.state, query = s.query.trim().toLowerCase();
        return s.data.rows.filter(row => (s.status === "all" || row.status === s.status)
            && (!s.audience || row.audience === s.audience) && (!s.category || row.category === s.category)
            && (!query || [row.name, row.reference, row.summary, row.scope_label, row.academic_scope].join(" ").toLowerCase().includes(query)));
    }
    get pageCount() { return Math.max(1, Math.ceil(this.rows.length / 10)); }
    get pageRows() { return this.rows.slice(this.state.page * 10, this.state.page * 10 + 10); }
    get cards() {
        const c = this.state.data.counts;
        return [{label: "Total circulars", value: c.total || 0, note: "Across current academic year", tone: ""},
            {label: "Published", value: c.published || 0, note: "Visible to selected audiences", tone: "blue"},
            {label: "Scheduled", value: c.scheduled || 0, note: "Queued for future release", tone: "amber"},
            {label: "Drafts", value: c.draft || 0, note: "Not yet published", tone: ""}];
    }
    get activity() {
        const c = this.state.data.counts;
        return [{key: "published", label: "Published circulars", color: "#1769e8"},
            {key: "scheduled", label: "Scheduled for release", color: "#e4a23c"},
            {key: "draft", label: "Drafts awaiting review", color: "#8d9db1"}].map(row => ({...row,
                count: c[row.key] || 0, style: `width:${c.total ? (c[row.key] || 0) / c.total * 100 : 0}%;background:${row.color}`}));
    }
    tone(status) { return {published: "green", scheduled: "amber", draft: "gray", archived: "gray"}[status] || "gray"; }
    statusLabel(status) { return STATUSES.find(s => s.key === status)?.label || status; }
    date(value) { return value ? new Intl.DateTimeFormat("en-GB", {day: "2-digit", month: "short", year: "numeric"}).format(new Date(value + "T12:00:00Z")) : "—"; }
    async load() {
        this.state.loading = true; this.state.error = "";
        try { this.state.data = await this.orm.call("campus.dashboard", "get_fee_circulars", []); this.state.page = Math.min(this.state.page, this.pageCount - 1); }
        catch (error) { this.state.error = error.data?.message || "Fee circulars could not be loaded. Please retry."; }
        finally { this.state.loading = false; }
    }
    filterChanged() { this.state.page = 0; }
    setStatus(status) { this.state.status = status; this.state.page = 0; this.router.pushState({fee_status: status}); }
    reset() { Object.assign(this.state, {query: "", audience: "", category: ""}); this.setStatus("all"); }
    archiveView() { this.reset(); this.setStatus("archived"); this.scrollRegister(); }
    scrollRegister() { this.registerRef.el?.scrollIntoView({behavior: "smooth", block: "start"}); }
    page(delta) { this.state.page = Math.max(0, Math.min(this.pageCount - 1, this.state.page + delta)); this.scrollRegister(); }
    open(row = null) {
        this.returnFocus = document.activeElement;
        this.state.detail = row;
        this.state.form = row ? {...row} : {name: "", reference: "", category: "fees", audience: "student", scope: "all",
            academic_scope: "", effective_from: this.state.data.today, due_date: "", body: "", status: "draft", publish_at: ""};
        this.state.formError = ""; this.state.success = ""; this.state.modal = true;
    }
    async closeModal(event) {
        if (event && event.target !== event.currentTarget || this.state.saving) return;
        this.state.modal = false; this.state.detail = null;
        await this.load();
        if (this.returnFocus?.isConnected) this.returnFocus.focus(); else this.newRef.el?.focus();
    }
    async save(event) {
        event.preventDefault();
        if (this.state.saving || this.readonly) return;
        this.state.saving = true; this.state.formError = "";
        try {
            await this.orm.call("campus.dashboard", "save_fee_circular", [this.state.form, this.state.detail?.id || false]);
            this.state.modal = false; this.state.detail = null; this.reset();
            this.state.success = "Circular saved.";
            await this.load(); this.newRef.el?.focus();
        } catch (error) { this.state.formError = error.data?.message || "The circular could not be saved. Check the details and retry."; }
        finally { this.state.saving = false; }
    }
    async archive() {
        if (this.state.saving || !this.state.detail) return;
        this.state.saving = true; this.state.formError = "";
        try {
            await this.orm.call("campus.dashboard", "archive_fee_circular", [this.state.detail.id]);
            this.state.modal = false; this.state.detail = null; this.state.success = "Circular archived.";
            await this.load(); this.newRef.el?.focus();
        } catch (error) { this.state.formError = error.data?.message || "The circular could not be archived."; }
        finally { this.state.saving = false; }
    }
}
registry.category("actions").add("ideastone_erp.accountant_fee_circulars", AccountantFeeCirculars);
