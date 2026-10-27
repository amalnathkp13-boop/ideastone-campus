/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FacultyHome extends Component {
    static template = "ideastone_erp.FacultyHome";
    static props = [];
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.notification = useService("notification");
        this.state = useState({data: null, loading: true, error: "", history: false});
        this.request = 0;
        onWillStart(() => this.load());
    }
    async load() {
        const request = ++this.request;
        this.state.loading = true; this.state.error = "";
        try { const data = await this.orm.call("campus.faculty.home", "get_home", []); if (request === this.request) this.state.data = data; }
        catch (error) { if (request === this.request) this.state.error = error.data?.message || "Your faculty dashboard could not be loaded. Please retry."; }
        finally { if (request === this.request) this.state.loading = false; }
    }
    get d() { return this.state.data; }
    get c() { return this.d.counts; }
    async open(kind, id = 0) {
        try { await this.action.doAction(await this.orm.call("campus.faculty.home", "get_action", [kind, id])); }
        catch (error) { this.notification.add(error.data?.message || "This faculty workspace could not be opened.", {type: "danger"}); }
    }
    number(value) { return new Intl.NumberFormat("en-IN", {maximumFractionDigits: 1}).format(value); }
    percent(value) { return value === null ? "—" : this.number(value) + "%"; }
    width(value) { return `${Math.min(100, Math.max(0, value || 0))}%`; }
    date(value, full = false) {
        if (!value) return "—";
        return new Date(`${value.slice(0,10)}T12:00:00Z`).toLocaleDateString("en-GB", full ? {weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC"} : {day: "2-digit", month: "short", timeZone: "UTC"});
    }
    get statusLabels() { return {done: "✓ Completed", next: "▶ Next class", upcoming: "◷ Upcoming", elapsed: "◷ Elapsed"}; }
    get lowestAttendance() { return this.d.attendance.filter(r => r.rate !== null).sort((a,b) => a.rate - b.rate)[0]; }
    get recentAssessment() { return this.d.assessments.slice().sort((a,b) => a.average - b.average)[0]; }
    get stats() {
        return [
            {label: "Classes scheduled", value: this.c.classes, icon: "▦", tag: "Today", foot: `${this.c.completed} completed · ${this.c.remaining} remaining`, tone: "positive"},
            {label: "Students taught", value: this.c.students, icon: "♙", tag: "Assigned", foot: `Across ${this.c.subjects} assigned subjects`, tone: ""},
            {label: "Attendance pending", value: this.c.pending, icon: "☑", tag: "Action needed", foot: "Elapsed class sessions to submit", tone: "warn"},
            {label: "Tasks due", value: this.c.tasks, icon: "⚑", tag: "Open", foot: `${this.c.due_today} due today · ${this.c.upcoming} upcoming${this.c.overdue ? ' · ' + this.c.overdue + ' overdue' : ''}`, tone: "warn"},
        ];
    }
}

export class FacultyDepartments extends Component {
    static template = "ideastone_erp.FacultyDepartments";
    static props = [];
    setup() {
        this.orm = useService("orm"); this.state = useState({data: null, loading: true, error: "", department: 0, year: 0, section: 0});
        this.request = 0;
        onWillStart(() => this.load());
    }
    async load(department = this.state.department, year = this.state.year, section = this.state.section) {
        const request = ++this.request;
        this.state.loading = true; this.state.error = "";
        try {
            const data = await this.orm.call("campus.faculty.home", "get_directory", [department, year, section]);
            if (request === this.request) Object.assign(this.state, {data, department, year, section});
        } catch (error) { if (request === this.request) this.state.error = error.data?.message || "The allocated class directory could not be loaded. Please retry."; }
        finally { if (request === this.request) this.state.loading = false; }
    }
    get d() { return this.state.data; }
    get title() { return this.state.section ? this.d.selected.section : this.state.year ? this.yearLabel : this.state.department ? this.d.selected.department : "Departments allocated to you"; }
    get yearLabel() { return this.state.year > 0 ? `Year ${this.state.year}` : "Year not recorded"; }
    get description() { return this.state.section ? "Students enrolled in your allocated section." : this.state.year ? "Choose an allocated section to view its students." : this.state.department ? "Choose a year of study from your teaching allocations." : "Select a department to see the years and sections you teach."; }
    back() { return this.state.section ? this.load(this.state.department,this.state.year,0) : this.state.year ? this.load(this.state.department,0,0) : this.load(0,0,0); }
    initials(value) { return value.trim().split(/\s+/).slice(0,2).map(word => word[0]).join("").toUpperCase(); }
    departmentIcon(code) { return {ECE: "⌁", CSE: "⌘", EEE: "ϟ"}[code] || "▦"; }
}
