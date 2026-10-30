/** @odoo-module **/
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const PAGES = {
    service: {title: "Campus services", sub: "Submit and track campus support requests, approvals, and maintenance issues.", hero: "Support services, clearly tracked", text: "Create requests, monitor progress, and follow up with the responsible campus team from one workspace.", table: "Service request register", desc: "Track service needs and see the latest owner, priority, and expected completion date.", columns: ["Request ID", "Subject", "Category", "Submitted", "Assigned team", "Priority", "Status", "Due date"]},
    leave: {title: "Student leave approvals", sub: "Review student leave applications and record mentor or department decisions.", hero: "Student leave approval desk", text: "Review application details, check dates and supporting notes, and record an auditable decision.", table: "Leave approval register", desc: "Applications assigned to you for advisor, HOD, or principal review.", columns: ["Application ID", "Student", "Programme", "Leave from", "Leave to", "Advisor", "Status", "Action"]},
    maintenance: {title: "Maintenance", sub: "Track campus work orders, responsible teams, and expected completion dates.", hero: "Maintenance and work order tracking", text: "Monitor facility issues from assignment through completion, with clear ownership and priority.", table: "Maintenance work orders", desc: "Work orders you raised for classrooms, labs, and shared campus facilities.", columns: ["Work order", "Issue / subject", "Location", "Assigned team", "Opened", "Priority", "Stage", "Target date"]},
    complaint: {title: "Register complaint on student", sub: "Record a student-related concern confidentially and route it to the authorised department.", hero: "Student concern and complaint register", text: "Capture the incident factually, protect sensitive information, and follow the college review process.", table: "Student complaint register", desc: "Only your own concerns are displayed here.", columns: ["Complaint ID", "Student / subject", "Concern category", "Reported on", "Reported by", "Priority", "Review status", "Next review"]},
};

export class FacultyCampusServices extends Component {
    static template = "ideastone_erp.FacultyCampusServices";
    static props = ["page"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({page: this.props.page.replace("campus-services-", ""), rows: [], company: "", today: "", busy: false, error: "", form: false, query: "", categoryFilter: "all", statusFilter: "all", quickFilter: "all", subject: "", category: "", priority: "normal", location: "", needed_by: "", contact: "", description: "", student_number: "", complaint_category: "", decisionId: 0, decisionReason: ""});
        onWillStart(() => this.load());
        onWillUpdateProps(async (next) => {
            const page = next.page.replace("campus-services-", "");
            if (page !== this.state.page) {
                this.state.page = page;
                this.resetFilters();
                await this.load();
            }
        });
    }
    get config() { return PAGES[this.state.page] || PAGES.service; }
    get rows() {
        const s = this.state;
        const q = s.query.toLowerCase().trim();
        return s.rows.filter(r => (!q || [r.code, r.subject, r.category, r.team, r.student, r.requester].join(" ").toLowerCase().includes(q))
            && (s.categoryFilter === "all" || r.category === s.categoryFilter)
            && (s.statusFilter === "all" || r.status === s.statusFilter)
            && (s.quickFilter === "all" || (s.quickFilter === "closed" ? ["Resolved", "Approved", "Rejected"].includes(r.status)
                : s.quickFilter === "progress" ? ["In progress", "HOD review", "Principal review"].includes(r.status)
                    : !["Resolved", "Approved", "Rejected", "Cancelled"].includes(r.status))));
    }
    get categories() { return [...new Set(this.state.rows.map(r => r.category).filter(Boolean))].sort(); }
    get statuses() { return [...new Set(this.state.rows.map(r => r.status).filter(Boolean))].sort(); }
    get stats() {
        const rows = this.state.rows;
        return [
            {icon: "fa-list-alt", label: this.state.page === "leave" ? "Applications" : this.state.page === "maintenance" ? "Work orders" : this.state.page === "complaint" ? "Complaints" : "Service requests", value: rows.length, tone: "blue", note: "Records in this workspace"},
            {icon: "fa-clock-o", label: "Awaiting action", value: rows.filter(r => ["Submitted", "Pending approval", "Advisor review", "HOD review", "Principal review"].includes(r.status)).length, tone: "amber", note: "Require review or assignment"},
            {icon: "fa-cog", label: "In progress", value: rows.filter(r => r.status === "In progress").length, tone: "violet", note: "Being handled by a team"},
            {icon: "fa-check", label: "Resolved", value: rows.filter(r => ["Resolved", "Approved"].includes(r.status)).length, tone: "green", note: "Marked complete"},
        ];
    }
    get assignedPct() { return Math.round(this.state.rows.filter(r => r.team && r.team !== "Awaiting assignment").length / Math.max(this.state.rows.length, 1) * 100); }
    get resolvedPct() { return Math.round(this.stats[3].value / Math.max(this.state.rows.length, 1) * 100); }
    statusTone(status) { return ["Resolved", "Approved"].includes(status) ? "green" : ["In progress", "HOD review"].includes(status) ? "blue" : ["Pending approval", "Advisor review", "Principal review"].includes(status) ? "violet" : status === "Cancelled" || status === "Rejected" ? "red" : "amber"; }
    priorityTone(priority) { return priority === "Urgent" ? "red" : priority === "High" ? "amber" : priority === "Low" ? "green" : "blue"; }
    async load() {
        this.state.busy = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.faculty.services.ui", "get_page_data", [this.state.page]);
            Object.assign(this.state, data);
        } catch (error) { this.state.error = error.data?.message || "Campus services could not be loaded."; }
        finally { this.state.busy = false; }
    }
    resetFilters() { Object.assign(this.state, {query: "", categoryFilter: "all", statusFilter: "all", quickFilter: "all", form: false, decisionId: 0}); }
    async go(page) { await this.action.doAction("ideastone_erp.action_dashboard", {additionalContext: {campus_module: "services", campus_page: `campus-services-${page}`}}); }
    async refresh() { this.resetFilters(); await this.load(); }
    openForm() { this.state.form = true; this.state.decisionId = 0; }
    closeForm() { this.state.form = false; this.state.decisionId = 0; }
    async submit(event) {
        event.preventDefault();
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            const fields = ["subject", "category", "priority", "location", "needed_by", "contact", "description", "student_number", "complaint_category"];
            const payload = Object.fromEntries(fields.map(key => [key, this.state[key]]));
            const result = await this.orm.call("campus.faculty.services.ui", "submit_request", [this.state.page, payload]);
            this.closeForm();
            for (const key of fields) this.state[key] = "";
            this.state.priority = "normal";
            this.notification.add(`${result.code} submitted`, {type: "success"});
            await this.load();
        } catch (error) { this.state.error = error.data?.message || "The request could not be submitted."; }
        finally { this.state.busy = false; }
    }
    review(row) { this.state.decisionId = row.id; this.state.decisionReason = ""; this.state.form = false; }
    async decide(decision) {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            await this.orm.call("campus.faculty.services.ui", "decide_leave", [this.state.decisionId, decision, this.state.decisionReason]);
            this.state.decisionId = 0;
            this.notification.add(`Leave ${decision === "approve" ? "approved" : "rejected"}`, {type: "success"});
            await this.load();
        } catch (error) { this.state.error = error.data?.message || "The decision could not be saved."; }
        finally { this.state.busy = false; }
    }
}
