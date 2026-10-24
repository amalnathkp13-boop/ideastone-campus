/** @odoo-module **/
import { Component, onWillStart, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const VIEWS = {
    overview: {title: "Admissions", description: "One clear view of your recruitment funnel, applicant readiness and next actions."},
    enquiries: {title: "Enquiry studio", description: "Capture interest, qualify prospects and make every follow-up count."},
    applications: {title: "Applications & review", description: "A structured review queue with clear ownership, readiness checks and transparent decisions."},
    documents: {title: "Document verification desk", description: "Track evidence, spot missing files and keep a clear audit trail for every verification."},
    register: {title: "Admission register", description: "Manage programme capacity, application windows, offers and confirmed seats in one structured register."},
};

class AdmissionsFilters extends Component {
    static template = "ideastone_erp.AdmissionsFilters";
    static components = { Dialog };
    static props = ["filters", "years", "programmes", "apply", "close"];
    setup() { this.state = useState({...this.props.filters, busy: false, error: ""}); }
    async apply() {
        this.state.busy = true;
        try {
            this.state.error = await this.props.apply({year_id: this.state.year_id, course_id: this.state.course_id});
            if (!this.state.error) this.props.close();
        } finally { this.state.busy = false; }
    }
}

export class AdmissionsWorkspace extends Component {
    static template = "ideastone_erp.AdmissionsWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.router = useService("router"); this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.view = this.props.action.params?.view || "overview";
        const hash = this.router.current.hash;
        this.state = useState({loading: true, error: "", data: null, query: "", status: "", page: 0,
            filters: {year_id: hash.admissions_year || "", course_id: hash.admissions_course || ""}});
        this.request = 0;
        onWillStart(() => this.load());
    }
    get meta() { return VIEWS[this.view]; }
    get columns() {
        return {overview: ["Applicant", "Programme", "Application stage", "Last activity", "Owner", "Action"],
            enquiries: ["Prospect", "Programme interest", "Source", "Lead score", "Status", "Next follow-up", "Owner"],
            applications: ["Application", "Programme", "Submitted", "Completeness", "Review stage", "Assigned to", "Action"],
            documents: ["Applicant", "Document", "Uploaded", "File check", "Verification", "Verified by", "Action"],
            register: ["Admission cycle", "Programme", "Academic year", "Application window", "Seat capacity", "Confirmed", "Status", "Action"]}[this.view];
    }
    get c() { return this.state.data.counts; }
    get scope() {
        const d = this.state.data, f = this.state.filters;
        return [d.years.find(r => String(r.id) === String(f.year_id))?.name || "All academic years",
            d.programmes.find(r => String(r.id) === String(f.course_id))?.name || "All programmes"].join(" · ");
    }
    async load(filters = this.state.filters) {
        const request = ++this.request;
        this.state.loading = true; this.state.error = "";
        try {
            const data = await this.orm.call("campus.admissions.ui", "get_workspace", [this.view, filters, this.state.query, this.state.status, this.state.page]);
            if (request !== this.request) return "";
            this.state.data = data; this.state.filters = {...filters};
            this.router.pushState({admissions_year: filters.year_id, admissions_course: filters.course_id});
            return "";
        } catch (error) {
            const message = error.data?.message || "Admissions could not be loaded. Check your access and retry.";
            if (request === this.request) this.state.error = message;
            return message;
        } finally { if (request === this.request) this.state.loading = false; }
    }
    refresh() { return this.load(); }
    filters() {
        const d = this.state.data;
        this.dialog.add(AdmissionsFilters, {filters: {...this.state.filters}, years: d.years, programmes: d.programmes,
            apply: async filters => {
                const page = this.state.page; this.state.page = 0;
                const error = await this.load(filters);
                if (error) { this.state.page = page; this.state.error = ""; }
                return error;
            }});
    }
    async search() { this.state.page = 0; await this.load(); }
    async paginate(delta) { this.state.page += delta; await this.load(); }
    async go(view) {
        try { await this.action.doAction(await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.action_admissions_" + view])); }
        catch (error) { this.notification.add(error.data?.message || "This workspace is unavailable.", {type: "danger"}); }
    }
    async open(kind, id = null, create = false) {
        try {
            const action = await this.orm.call("campus.admissions.ui", "get_action", [kind, id, create, this.state.filters]);
            if (!action.views) action.views = (action.view_mode || "tree,form").split(",").map(mode => [false, mode]);
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || "The admissions record could not be opened.", {type: "danger"}); }
    }
    get stats() {
        return [{label: "New enquiries", value: this.c.enquiries, icon: "envelope-o", view: "enquiries", detail: "Saved college enquiries"},
            {label: "Applications started", value: this.c.applications, icon: "files-o", view: "applications", detail: "Managed applications"},
            {label: "Awaiting review", value: this.c.review, icon: "clock-o", view: "applications", detail: "Submitted, documents or review"},
            {label: "Confirmed enrolments", value: this.c.enrolled, icon: "check", view: "applications", detail: "Converted through approval"}];
    }
    get tasks() {
        return [{title: "Follow up on scheduled activities", detail: `${this.c.follow_up} ${this.c.follow_up === 1 ? 'enquiry' : 'enquiries'} · Due today or earlier`, value: this.c.follow_up, icon: "phone", view: "enquiries", label: "Due"},
            {title: "Verify pending certificates", detail: `${this.c.pending_documents} uploaded ${this.c.pending_documents === 1 ? 'document' : 'documents'} · Awaiting verification`, value: this.c.pending_documents, icon: "file-text-o", view: "documents", label: "Review"},
            {title: "Review open offers", detail: `${this.c.offers} approved ${this.c.offers === 1 ? 'application' : 'applications'} · Not yet enrolled`, value: this.c.offers, icon: "envelope-o", view: "applications", label: "Open"}]
            .filter(item => this.state.data.allowed[item.view]);
    }
    get brief() {
        return `${this.c.follow_up} ${this.c.follow_up === 1 ? 'enquiry has' : 'enquiries have'} a scheduled follow-up due. ${this.c.pending_documents} uploaded ${this.c.pending_documents === 1 ? 'document is' : 'documents are'} awaiting verification. Review these saved records with the responsible admissions staff.`;
    }
    get departmentInsight() {
        const rows = this.state.data.departments.filter(r => r.applications);
        if (!rows.length) return "Department signals will appear as applications and admission cycles are recorded.";
        const top = [...rows].sort((a,b) => b.confirmed - a.confirmed || b.applications - a.applications)[0];
        return `${top.name} has ${top.applications} managed applications, ${top.confirmed} confirmed enrolments and ${top.waiting} waitlisted applications in this scope. Review the recorded capacity before planning the next round.`;
    }
    get strip() {
        return {
            enquiries: {title: "Follow-up intelligence", text: "Use scheduled activities, programme interest and the contacted flag to prioritise follow-ups. Automated lead scores are not configured.", button: "Open enquiry register", kind: "enquiries"},
            applications: {title: "Review assist · Explainable checks", text: `${this.c.ready} applications have verified required documents and matching intake placement. Staff retain responsibility for eligibility and admission decisions.`, button: "Review queue", kind: "applications"},
            documents: {title: "Document verification assistant", text: "This desk shows uploaded files and recorded staff verification. Scan quality and authenticity must be checked by authorised staff; automated image-quality checks are not configured.", button: "Verification register", kind: "documents"},
            register: {title: "Seat planning signal", text: "Capacity and confirmed counts use configured intakes and managed enrolments. Review college allocation rules before changing seat availability.", button: "Capacity planner", kind: "register"},
        }[this.view];
    }
    initials(value) { return String(value || "").trim().split(/\s+/).slice(0,2).map(word => word[0] || "").join("").toUpperCase() || "—"; }
    number(value) { return value === null || value === undefined ? "—" : new Intl.NumberFormat(undefined, {maximumFractionDigits: 1}).format(value); }
    percent(value) { return value === null || value === undefined ? "—" : this.number(value) + "%"; }
    width(count, total) { return Math.min(100, Math.max(0, total ? count * 100 / total : 0)) + "%"; }
    print() { window.print(); }
    exportRows() {
        const columns = {
            enquiries: ["name", "reference", "programme", "source", "status", "follow_up", "owner"],
            applications: ["reference", "name", "programme", "submitted", "completeness", "status", "owner"],
            documents: ["name", "reference", "document", "uploaded", "file_status", "status", "owner"],
            register: ["name", "programme", "year", "window", "capacity", "confirmed", "status"],
        }[this.view];
        const quote = value => {
            let text = String(value ?? "");
            if (/^[\s]*[=+\-@]/.test(text)) text = "'" + text;
            return `"${text.replaceAll('"', '""')}"`;
        };
        const csv = "\ufeff" + [columns, ...this.state.data.rows.map(row => columns.map(key => row[key]))].map(row => row.map(quote).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a"); link.href = url; link.download = `admissions-${this.view}-page-${this.state.page+1}.csv`; link.click(); URL.revokeObjectURL(url);
    }
}
registry.category("actions").add("ideastone_erp.admissions", AdmissionsWorkspace);
