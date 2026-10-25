/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useRef, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PAGES = {
    overview: ["ACADEMIC OPERATIONS", "Examinations", "Plan exams, track outcomes and keep question papers organized.", "Create exam", "marks"],
    sessions: ["EXAMINATION SETUP", "Exam sessions", "One place to manage internal, university and external examinations.", "New session", "sessions"],
    marks: ["SCHEDULING & ASSESSMENT", "Schedule & marks entry", "Coordinate subject-level schedules and monitor marks submission before results are published.", "Add exam slot", "marks"],
    grades: ["ASSESSMENT CONFIGURATION", "Grade rules", "Maintain approved grade bands and pass criteria by programme or examination scheme.", "Add grade band", "grades"],
    results: ["RESULTS & QUALITY REVIEW", "Results & missing entries", "Identify incomplete marks, review pass/fail patterns and prepare results for approval.", "Review publication", "marks"],
    papers: ["QUESTION PAPER CONTROL", "Question papers", "Browse examination question sets, PDF files and update timestamps by department.", "Add question paper", "papers"],
};
const FEATURES = [
    ["sessions", "▤", "Exam sessions", "Create and manage internal tests, semester exams and other campus-supported examinations.", "Manage sessions", ""],
    ["marks", "✎", "Schedule & marks entry", "Build subject-wise schedules, assign faculty, enter marks and track submission status.", "Open workspace", "green"],
    ["grades", "A", "Grade rules", "Maintain approved grading bands, minimum pass criteria and assessment rules.", "Manage grade rules", "purple"],
    ["results", "▥", "Results & missing entries", "Review pass/fail trends, missing marks and department performance.", "Review results", "amber"],
    ["papers", "PDF", "Question papers", "Browse upcoming and previous question sets, PDF files and update timestamps by department.", "View question papers", "rose"],
    ["reports", "▥", "Exam analytics & reports", "Summaries for pass percentage, failure rate, subject outcomes and result publication.", "Preview reports", ""],
];

export class ExaminationsWorkspace extends Component {
    static template = "ideastone_erp.ExaminationsWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.router = useService("router");
        this.notification = useService("notification"); this.content = useRef("content");
        this.view = this.props.action.params?.view || "overview"; this.request = 0;
        this.state = useState({data: null, error: "", loading: true, query: "", page: 0,
            filters: {year_id: this.props.action.context?.exams_year_id ?? this.router.current.hash.exams_year_id ?? 0, session_id: 0, type_id: 0, department_id: 0, status: "", paper_department_id: "", paper_period: "all"},
            department: null, paperFilter: "all"});
        onWillStart(() => this.load());
        onWillUnmount(() => { clearTimeout(this.searchTimer); ++this.request; });
    }
    get page() { return PAGES[this.view]; }
    get c() { return this.state.data.counts; }
    get features() { return FEATURES; }
    departmentTheme(department) {
        const code = (department.code || "").toUpperCase();
        const name = department.name.toLowerCase();
        if (code === "CSE" || name.includes("computer science")) return {order:0, icon:"⌘", tone:""};
        if (code === "ECE" || name.includes("communication")) return {order:1, icon:"⌁", tone:""};
        if (code === "EEE" || name.includes("electrical")) return {order:2, icon:"ϟ", tone:"amber"};
        if (code === "MECH" || name.includes("mechanical")) return {order:3, icon:"⚙", tone:"green"};
        if (code === "CIVIL" || name.includes("civil")) return {order:4, icon:"⌂", tone:"purple"};
        if (code === "BME" || name.includes("biomedical")) return {order:5, icon:"✚", tone:"red"};
        return {order:6, icon:"▤", tone:""};
    }
    get departments() { return [...this.state.data.departments].sort((a,b) => this.departmentTheme(a).order - this.departmentTheme(b).order || a.name.localeCompare(b.name)); }
    percent(value) { return value == null ? "—" : `${value.toFixed(1)}%`; }
    get stats() {
        const c = this.c;
        const item = (label, value, detail, icon = "▤", tone = "") => ({label, value, detail, icon, tone});
        return {
            overview: [item("Upcoming examinations", c.upcoming, "Next 30 days · selected academic scope"), item("Overall pass percentage", this.percent(c.pass_rate), "Latest per department · evaluated entries", "✓", "green"), item("Students requiring follow-up", c.followup, "Failed published results or missing entries", "!", "amber"), item("Question papers approved", "—", `${c.papers} saved papers · HOD approval not configured`, "▧", "purple")],
            sessions: [item("Total sessions", c.sessions, "Across configured examination types"), item("Upcoming", c.upcoming, "Next 30 days", "◷", "amber"), item("Scheduled sessions", c.scheduled_sessions, "Saved session scheduling status", "✓", "green"), item("Exam types in use", c.types, "Types assigned to the selected sessions", "↗", "purple")],
            marks: [item("Scheduled papers", c.exams, "Saved managed examination records", "▦"), item("Marks submitted", `${c.submitted} / ${c.exams}`, "Submitted, locked or published", "✓", "green"), item("Rooms allocated", "—", "Room allocation is not recorded on exams", "▣", "amber"), item("Faculty assignments", c.faculty, `${c.unassigned} papers have no assigned faculty`, "♟", "purple")],
            grades: [item("Grade bands", c.grades, "Configured college grading bands", "A"), item("Minimum pass mark", c.pass_mark == null ? "Per exam" : `${c.pass_mark}%`, "Configured on the selected examinations", "✓", "green"), item("Exams using rules", c.grade_uses, "Examinations with an assigned grade scale", "▤", "purple"), item("Protected grade bands", c.locked_grades, "Used by locked or published results", "!", "amber")],
            results: [item("Pass percentage", this.percent(c.pass_rate), "Latest per department · evaluated entries", "✓", "green"), item("Failure percentage", this.percent(c.failure_rate), "Latest per department · evaluated entries", "×", "red"), item("Missing mark entries", c.missing, `Across ${c.missing_exams} examinations`, "◷", "amber"), item("Absent / withheld", "—", "Not classified in the current marks roster", "!", "purple")],
            papers: [item("Question sets", c.papers, "Saved files visible to your account", "▧"), item("Approved by HOD", "—", "Approval evidence is not stored yet", "✓", "green"), item("Awaiting approval", "—", "HOD approval workflow is not configured", "◷", "amber"), item("Previous papers", c.previous_papers, "Linked examinations that have ended", "PDF", "purple")],
        }[this.view];
    }
    get tableTitle() { return {sessions:"All examination sessions",marks:"Schedule and marks tracker",grades:"Percentage-to-grade mapping",results:"Result records"}[this.view]; }
    get tableDescription() { return {sessions:"Filter by examination type, status or session name.",marks:"Subject, class, faculty and marks submission status.",grades:"Saved college scale. Passing marks are configured on each examination.",results:"Published result entries grouped by department and session."}[this.view]; }
    get columns() { return {
        sessions:["Exam session","Type","Audience","Exam window","Academic year","Status","Action"],
        marks:["Exam / subject","Class / batch","Date & time","Room","Faculty / examiner","Marks status","Action"],
        grades:["Result to display","Minimum %","Maximum %","Exams using band","Protection","Company / scope","Action"],
        results:["Department","Exam","Evaluated entries","Passed","Failed","Missing","Pass rate","Status"],
    }[this.view]; }
    get tableRows() {
        const cell = (text, sub = "", tone = "") => ({text, sub, tone});
        return this.state.data.rows.map(r => ({...r, cells: {
            sessions: [cell(r.name,r.code),cell(r.type),cell(r.audience,r.section),cell(r.start,r.end),cell(r.year),cell(r.status,"",r.tone)],
            marks: [cell(r.name,`${r.session} · ${r.code}`),cell(r.section,r.department),cell(r.start,r.end),cell("Not recorded"),cell(r.faculty),cell(r.status,`${r.entered} / ${r.total} entered`,r.tone)],
            grades: [cell(r.name),cell(r.minimum),cell(r.maximum),cell(r.uses),cell(r.locked ? "Protected" : "Validated on save","",r.locked ? "amber" : "blue"),cell(r.company)],
            results: [cell(r.name,r.code),cell(r.exam),cell(r.appeared),cell(r.passed),cell(r.failed),cell(r.missing),cell(this.percent(r.rate)),cell(r.status,"",r.tone)],
        }[this.view]}));
    }
    get statuses() { return this.view === "sessions" ? [["draft","Draft"],["schedule","Scheduled"],["held","Held"],["done","Done"],["cancel","Cancelled"]] : [["draft","Draft"],["entry","Entry in progress"],["submitted","Submitted"],["locked","Locked / approved"],["published","Published"],["missing","Missing marks"]]; }
    get performance() { return this.departments.filter(d => d.appeared); }
    get paperRows() { return this.state.data.rows; }
    async load() {
        const request = ++this.request; this.state.loading = true; this.state.error = "";
        try {
            const data = await this.orm.call("campus.examinations.ui", "get_workspace", [this.view, this.state.filters, this.state.query, this.state.page]);
            if (request !== this.request) return;
            this.state.data = data; this.state.filters = {...data.filters};
            this.props.action.context.exams_year_id = data.filters.year_id;
            this.router.pushState({exams_year_id: data.filters.year_id});
        } catch (e) { if (request === this.request) this.state.error = e.data?.message || "Examination data could not be loaded. Retry or check your permissions."; }
        finally { if (request === this.request) this.state.loading = false; }
    }
    async filter() { this.state.page = 0; await this.load(); }
    search() { clearTimeout(this.searchTimer); this.searchTimer = setTimeout(() => this.filter(), 250); }
    async paginate(delta) { this.state.page += delta; await this.load(); }
    async show(view) {
        if (view === "reports") return this.openReport();
        await this.action.doAction(`ideastone_erp.action_examinations_${view}`, {additionalContext:{exams_year_id:this.state.filters.year_id}});
    }
    async open(kind, id = null) {
        try {
            const action = await this.orm.call("campus.examinations.ui", "get_record_action", [kind, id]);
            action.context.exams_year_id = this.state.filters.year_id;
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (e) { this.notification.add(e.data?.message || "This record could not be opened.", {type:"danger"}); }
    }
    async openRow(row) { return this.view === "results" ? this.reviewPublication(row.session_id) : this.open(this.view, row.id); }
    async primary() { return this.view === "results" ? this.reviewPublication() : this.open(this.page[4]); }
    async reviewPublication(sessionId = 0) {
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.mvp_exams"]);
            action.context.exams_year_id = this.state.filters.year_id;
            if (sessionId) action.domain.push(["session_id", "=", sessionId]);
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (e) { this.notification.add(e.data?.message || "The publication workflow could not be opened.", {type:"danger"}); }
    }
    async openReport() {
        try { await this.action.doAction(await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.mvp_report_results"])); }
        catch (e) { this.notification.add(e.data?.message || "Result reporting permission is required.", {type:"warning"}); }
    }
    async chooseDepartment(department) {
        this.state.department = department.id; this.state.filters.paper_department_id = department.id;
        this.state.query = ""; this.state.paperFilter = "all"; this.state.filters.paper_period = "all"; await this.filter();
        this.content.el?.querySelector(".department-papers")?.scrollIntoView({block:"start",behavior:"smooth"});
    }
    async paperPeriod(period) { this.state.paperFilter = period; this.state.filters.paper_period = period; await this.filter(); }
    async allDepartments() { this.state.department = null; this.state.filters.paper_department_id = ""; this.state.filters.paper_period = "all"; this.state.query = ""; await this.filter(); }
}
registry.category("actions").add("ideastone_erp.examinations", ExaminationsWorkspace);
