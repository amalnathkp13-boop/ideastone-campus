/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const PAGES = {
    opac: ["Library & learning", "Access the college catalogue, review your loans, and open approved learning resources.", "Faculty library access", "Search library holdings, check availability, track issued items and access digital learning resources through your staff account."],
    catalogue: ["Library catalogue", "Browse the collection by title, subject, call number and availability.", "Find library materials", "Use catalogue details to locate books and confirm shelf availability before visiting."],
    circulation: ["Library circulation", "Review issued books, due dates, return history and renewal eligibility.", "Your library circulation", "Check due dates and track your staff loan records. Request renewals through the library circulation desk."],
    learning: ["Learning platform", "Open digital learning resources and review staff access information.", "Learning resources for staff", "Access approved digital library resources and faculty learning materials using your institutional account."],
};

class LibraryAssistance extends Component {
    static template = "ideastone_erp.LibraryAssistance";
    static components = { Dialog };
    static props = ["close", "onSaved"];
    setup() {
        this.orm = useService("orm");
        this.state = useState({note: "", busy: false, error: ""});
    }
    async save(ev) {
        ev.preventDefault();
        if (this.state.busy) return;
        this.state.busy = true; this.state.error = "";
        try {
            await this.orm.call("campus.faculty.library", "request_assistance", [this.state.note]);
            this.props.onSaved(); this.props.close();
        } catch (error) { this.state.error = error.data?.message || "Your enquiry could not be saved. Please retry."; }
        finally { this.state.busy = false; }
    }
}

export class FacultyLibrary extends Component {
    static template = "ideastone_erp.FacultyLibrary";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action");
        this.notification = useService("notification"); this.dialog = useService("dialog");
        this.view = this.props.action.params?.view || "opac";
        if (!PAGES[this.view]) this.view = "opac";
        this.state = useState({data: null, loading: true, error: "", busy: 0, page: 0,
            query: "", searchBy: "all", availability: "all", department: "all", status: "all", materials: false});
        onWillStart(() => this.load());
    }
    get page() { return PAGES[this.view]; }
    get counts() { return this.state.data.counts; }
    get departments() { return [...new Set(this.state.data.books.map(book => book.department))].sort(); }
    get stats() {
        const c = this.counts;
        return this.view === "opac" ? [
            {icon: "▤", tone: "", label: "Total catalogue records", value: this.number(c.total), detail: "College library collection"},
            {icon: "✓", tone: "green", label: "Available titles", value: this.number(c.available), detail: "Titles with a copy available"},
            {icon: "▣", tone: "amber", label: "Currently issued", value: this.number(c.issued), detail: "Across the library"},
            {icon: "◷", tone: "violet", label: "Your active loans", value: this.number(c.own), detail: `${c.due} ${c.due === 1 ? 'item' : 'items'} due within 7 days`},
        ] : [
            {icon: "▤", tone: "", label: "Books issued to you", value: this.number(c.own), detail: "Active loan records"},
            {icon: "◷", tone: "amber", label: "Due within 7 days", value: this.number(c.due), detail: "Plan your return"},
            {icon: "↻", tone: "green", label: "Renewal requests", value: this.number(c.pending), detail: c.pending ? "Awaiting library review" : "No request currently pending"},
            {icon: "₹", tone: "violet", label: "Outstanding fine", value: this.money(c.fine), detail: "Recorded library balance"},
        ];
    }
    get filteredRows() {
        const s = this.state, query = s.query.trim().toLowerCase();
        if (this.view === "circulation") return s.data.loans.filter(loan => (s.status === "all" || loan.status === s.status)
            && (!query || [loan.title, loan.code].join(" ").toLowerCase().includes(query)));
        return s.data.books.filter(book => (s.availability === "all" || book.status === s.availability)
            && (this.view !== "catalogue" || s.department === "all" || book.department === s.department)
            && (!query || (this.view === "opac" && s.searchBy !== "all"
                ? s.searchBy === "subject" ? [book.department, book.subject].join(" ") : book[s.searchBy]
                : [book.title, book.author, book.code, book.publisher, book.department, book.subject].join(" "))
                .toLowerCase().includes(query)));
    }
    get rows() { return this.filteredRows.slice(this.state.page * 20, (this.state.page + 1) * 20); }
    get start() { return this.filteredRows.length ? this.state.page * 20 + 1 : 0; }
    get end() { return Math.min((this.state.page + 1) * 20, this.filteredRows.length); }
    number(value) { return new Intl.NumberFormat("en-IN").format(value); }
    money(value) { return new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR"}).format(value); }
    date(value) { return value ? new Date(`${value}T12:00:00`).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric"}) : "—"; }
    statusClass(value) { return value === "Available" || value === "Returned" ? "available" : value === "Issued" ? "issued" : "pending"; }
    filter() { this.state.page = 0; }
    reset() { Object.assign(this.state, {query: "", searchBy: "all", availability: "all", department: "all", status: "all", page: 0}); }
    async refresh() { this.reset(); await this.load(); }
    paginate(delta) { this.state.page += delta; }
    async load() {
        this.state.loading = true; this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.faculty.library", "get_workspace", []);
            if (this.state.page * 20 >= this.filteredRows.length) this.state.page = 0;
        } catch (error) { this.state.error = error.data?.message || "Library records could not be loaded. Please retry."; }
        finally { this.state.loading = false; }
    }
    async renew(loan) {
        if (this.state.busy) return;
        this.state.busy = loan.id;
        try {
            await this.orm.call("campus.faculty.library", "request_renewal", [loan.id]);
            await this.load();
            this.notification.add("Renewal request saved for library review. Your current due date remains in effect.", {type: "success"});
        } catch (error) { this.notification.add(error.data?.message || "The renewal request could not be saved.", {type: "danger"}); }
        finally { this.state.busy = 0; }
    }
    assistance() {
        this.dialog.add(LibraryAssistance, {onSaved: () => this.notification.add("Your enquiry was saved for the library desk.", {type: "success"})});
    }
    async opac() { await this.action.doAction("ideastone_erp.action_faculty_library_opac"); }
    async openDesk() {
        await this.action.doAction("ideastone_erp.action_dashboard", {additionalContext: {campus_module: "library", campus_page: "library"}});
    }
}
registry.category("actions").add("ideastone_erp.faculty_library", FacultyLibrary);
