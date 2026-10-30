/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const ACTIONS = {
    overview: "ideastone_erp.action_owner_communication_overview",
    notices: "ideastone_erp.action_owner_communication_notices",
    requests: "ideastone_erp.action_owner_communication_requests",
};
const LABELS = {overview: "Communication overview", notices: "Notices & audiences", requests: "Student requests & support"};
const EMPTY_NOTICE = {name: "", category: "General", audience: "student", course_id: "", batch_id: "", group_id: "", publish_at: "", body: ""};
const EMPTY_REQUEST = {student_id: "", type_id: "", category: "other", name: "", description: "", office: "auto", priority: "normal", due_at: ""};

export class OwnerCommunication extends Component {
    static template = "ideastone_erp.OwnerCommunication";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.view = this.props.action.params?.view || "overview";
        this.state = useState({data: null, loading: true, busy: false, error: "", period: "month", search: "",
            category: "", status: "", audience: "", priority: "", editor: null, noticeId: 0,
            requestEditor: null, requestId: 0, reply: "", nextState: ""});
        if (this.props.action.context?.communication_compose === "notice") this.newNotice();
        onWillStart(() => this.load());
    }

    get label() { return LABELS[this.view]; }
    get c() { return this.state.data?.counts || {}; }
    get noticeRows() {
        const query = this.state.search.trim().toLowerCase();
        return (this.state.data?.notices || []).filter(row =>
            (!query || [row.reference, row.name, row.owner, row.audience].join(" ").toLowerCase().includes(query)) &&
            (!this.state.category || row.category === this.state.category) &&
            (!this.state.status || row.status_code === this.state.status) &&
            (!this.state.audience || row.audience_code === this.state.audience));
    }
    get requestRows() {
        const query = this.state.search.trim().toLowerCase();
        return (this.state.data?.requests || []).filter(row =>
            (!query || [row.reference, row.student, row.student_number, row.name].join(" ").toLowerCase().includes(query)) &&
            (!this.state.category || row.category === this.state.category) &&
            (!this.state.priority || row.priority_code === this.state.priority) &&
            (!this.state.status || row.state_code === this.state.status));
    }
    get schedule() {
        return (this.state.data?.notices || []).filter(r => ["scheduled", "attention", "draft"].includes(r.status_code))
            .sort((a,b) => (a.publish_at || a.date).localeCompare(b.publish_at || b.date)).slice(0, 4);
    }
    get queue() {
        const rank = {time_sensitive: 0, deadline: 1, normal: 2};
        return (this.state.data?.requests || []).filter(r => !["done", "rejected", "cancelled"].includes(r.state_code))
            .sort((a, b) => (rank[a.priority_code] ?? 3) - (rank[b.priority_code] ?? 3) || b.updated.localeCompare(a.updated)).slice(0, 4);
    }
    get recent() { return (this.state.data?.notices || []).slice(0, 6); }
    get noticeCategories() { return [...new Set((this.state.data?.notices || []).map(r => r.category))].sort(); }
    get requestCategories() { return [...new Set((this.state.data?.requests || []).map(r => r.category))].sort(); }
    get selectedBatches() { return (this.state.data?.batches || []).filter(r => String(r.course_id) === String(this.state.editor?.course_id)); }

    async load() {
        this.state.loading = true; this.state.error = "";
        try { this.state.data = await this.orm.call("campus.owner.communication.ui", "snapshot", [this.state.period]); }
        catch (e) { this.state.error = e.data?.message || "Communication records could not be loaded."; }
        finally { this.state.loading = false; }
    }
    async show(view, compose = false) {
        await this.action.doAction(ACTIONS[view], {additionalContext: compose ? {communication_compose: "notice"} : {}});
    }
    newNotice() { this.state.noticeId = 0; this.state.editor = {...EMPTY_NOTICE}; }
    editNotice(row) {
        if (row.status_code !== "draft") return;
        this.state.noticeId = row.id;
        const doc = new DOMParser().parseFromString(row.body, "text/html");
        this.state.editor = {name: row.name, category: row.category,
            audience: row.course_id ? "department" : row.group_id ? "group" : row.audience_code,
            course_id: row.course_id || "", batch_id: row.batch_id || "", group_id: row.group_id || "",
            publish_at: row.publish_at ? this.localDatetime(row.publish_at) : "", body: doc.body.textContent || ""};
    }
    localDatetime(value) {
        const d = new Date(value.replace(" ", "T") + "Z");
        const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
        return local.toISOString().slice(0, 16);
    }
    async saveNotice(submit) {
        if (!this.state.editor?.name.trim() || !this.state.editor?.body.trim()) {
            this.notification.add("Enter a notice title and message.", {type: "warning"}); return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("campus.owner.communication.ui", "save_notice", [this.state.editor, this.state.noticeId || false, submit]);
            this.state.editor = null;
            await this.load();
            this.notification.add(submit ? "Notice submitted for approval." : "Draft saved.", {type: "success"});
        } catch (e) { this.notification.add(e.data?.message || "The notice could not be saved.", {type: "danger"}); }
        finally { this.state.busy = false; }
    }
    async publish(row) {
        this.state.busy = true;
        try { await this.orm.call("campus.owner.communication.ui", "publish_notice", [row.id]); await this.load();
              this.notification.add("Notice approved for portal publication.", {type: "success"}); }
        catch (e) { this.notification.add(e.data?.message || "The notice could not be approved.", {type: "danger"}); }
        finally { this.state.busy = false; }
    }
    newRequest() { this.state.requestId = 0; this.state.requestEditor = {...EMPTY_REQUEST}; }
    inspectRequest(row) { this.state.requestEditor = null; this.state.requestId = row.id; this.state.reply = row.reply || ""; this.state.nextState = row.state_code; }
    get selectedRequest() { return (this.state.data?.requests || []).find(r => r.id === this.state.requestId); }
    async logRequest() {
        this.state.busy = true;
        try { await this.orm.call("campus.owner.communication.ui", "log_request", [this.state.requestEditor]);
              this.state.requestEditor = null; await this.load(); this.notification.add("Student request logged.", {type: "success"}); }
        catch (e) { this.notification.add(e.data?.message || "The request could not be logged.", {type: "danger"}); }
        finally { this.state.busy = false; }
    }
    async respond() {
        this.state.busy = true;
        try { await this.orm.call("campus.owner.communication.ui", "respond_request", [this.state.requestId, this.state.reply, this.state.nextState]);
              this.state.requestId = 0; await this.load(); this.notification.add("Request updated.", {type: "success"}); }
        catch (e) { this.notification.add(e.data?.message || "The request could not be updated.", {type: "danger"}); }
        finally { this.state.busy = false; }
    }
    exportRows(kind) {
        const rows = kind === "notices" ? this.noticeRows : this.requestRows;
        const keys = kind === "notices" ? ["reference", "name", "category", "audience", "date", "owner", "reach", "status"] :
            ["reference", "student", "student_number", "category", "name", "office", "updated", "priority", "state"];
        const quote = value => `"${String(value ?? "").replaceAll('"', '""')}"`;
        const csv = [keys.map(quote).join(","), ...rows.map(row => keys.map(key => quote(row[key])).join(","))].join("\r\n");
        const url = URL.createObjectURL(new Blob(["\ufeff", csv], {type: "text/csv;charset=utf-8"}));
        const a = document.createElement("a"); a.href = url; a.download = `communication-${kind}.csv`; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    date(value) {
        if (!value) return "—";
        const d = new Date(value.includes(" ") ? value.replace(" ", "T") + "Z" : value + "T00:00:00");
        return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat(undefined, {day:"2-digit", month:"short", year:"numeric"}).format(d);
    }
    dateTime(value) {
        const d = new Date(value.replace(" ", "T") + "Z");
        return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat(undefined,
            {day:"2-digit", month:"short", year:"numeric", hour:"numeric", minute:"2-digit"}).format(d);
    }
    statusTone(code) { return ({published:"green", scheduled:"blue", attention:"amber", draft:"amber", done:"green", rejected:"red", information:"amber", submitted:"blue", time_sensitive:"red", deadline:"amber"})[code] || ""; }
}

registry.category("actions").add("ideastone_erp.owner_communication", OwnerCommunication);
