/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const META = {
    overview: ["Academics", "A clear view of academic delivery, curriculum progress and what needs attention."],
    years: ["Academic years", "Manage academic-year timelines and identify the active year at a glance."],
    departments: ["Departments", "Review department strength, capacity and academic structure in one place."],
    programmes: ["Programmes", "Browse the academic programmes offered across departments and review their structure at a glance."],
    semesters: ["Semesters", "Track academic periods, semester structure and setup readiness in one place."],
    sections: ["Sections", "Review class sections, programme links and academic-year mapping in one place."],
    curriculum: ["Subjects & curriculum", "Manage subject records and review how curriculum is distributed across departments and semesters."],
};
const AREAS = [["engineering", "Engineering & technology"], ["science", "Science & humanities"], ["management", "Business & management"], ["health", "Health sciences"], ["other", "Other"]];
const LEVELS = [["undergraduate", "Undergraduate"], ["postgraduate", "Postgraduate"], ["diploma", "Diploma / other"]];
const LABELS = {years: "academic year", departments: "department", programmes: "programme", semesters: "semester", sections: "section", curriculum: "subject"};
const FIELDS = {
    years: [["name", "Academic year"], ["code", "Code"], ["start_date", "Start date", "date"], ["end_date", "End date", "date"], ["term_structure", "Term structure", "structure"], ["campus_current", "Current academic year", "checkbox"], ["active", "Active", "checkbox"]],
    departments: [["name", "Department name"], ["code", "Department code"], ["campus_academic_area", "Academic area", "area"], ["active", "Active", "checkbox"]],
    programmes: [["name", "Programme name"], ["code", "Programme code"], ["department_id", "Department", "departments"], ["campus_level", "Programme level", "level"], ["campus_duration", "Duration (semesters)", "number"], ["campus_award", "Award / programme type"], ["active", "Active", "checkbox"]],
    semesters: [["name", "Semester name"], ["academic_year_id", "Academic year", "years"], ["campus_course_id", "Programme", "programmes"], ["campus_sequence", "Semester number", "number"], ["term_start_date", "Start date", "date"], ["term_end_date", "End date", "date"]],
    sections: [["name", "Section name"], ["code", "Section code"], ["course_id", "Programme", "programmes"], ["campus_year_id", "Academic year", "years"], ["campus_term_id", "Semester", "semesters"], ["start_date", "Start date", "date"], ["end_date", "End date", "date"], ["active", "Active", "checkbox"]],
    curriculum: [["name", "Subject name"], ["code", "Subject code"], ["department_id", "Department", "departments"], ["campus_term_id", "Semester", "semesters"], ["campus_credits", "Credits", "number"], ["type", "Teaching type", "teaching"], ["subject_type", "Subject type", "subject"], ["active", "Active", "checkbox"]],
};

class AcademicRecord extends Component {
    static template = "ideastone_erp.AcademicRecord";
    static components = { Dialog };
    static props = ["view", "record", "data", "saved", "close"];
    setup() {
        this.orm = useService("orm");
        const current = this.props.data.current;
        const defaults = {name: "", code: "", active: true, campus_current: false, term_structure: "two_sem", campus_duration: 8,
            campus_sequence: 1, campus_credits: 0, type: "theory", subject_type: "compulsory", academic_year_id: current?.id || "",
            campus_year_id: current?.id || "", start_date: current?.start || this.props.data.today, end_date: current?.end || "",
            term_start_date: current?.start || this.props.data.today, term_end_date: current?.end || ""};
        this.state = useState({editing: !this.props.record, busy: false, error: "",
            values: Object.fromEntries(FIELDS[this.props.view].map(([key]) => [key, this.props.record?.values[key] ?? defaults[key] ?? ""]))});
    }
    get title() { return this.props.record ? this.props.record.name : `Add ${LABELS[this.props.view]}`; }
    get fields() {
        const enums = {area: AREAS, level: LEVELS, structure: [["two_sem", "Two semesters"], ["two_sem_qua", "Two semesters subdivided by quarters"], ["two_sem_final", "Two semesters with quarters and final exams"], ["three_sem", "Three trimesters"], ["four_Quarter", "Four quarters"], ["final_year", "Final year grades with quarters"], ["others", "Other / custom schedule"]],
            teaching: [["theory", "Theory"], ["practical", "Practical"], ["both", "Both"], ["other", "Other"]], subject: [["compulsory", "Compulsory"], ["elective", "Elective"]]};
        return FIELDS[this.props.view].map(([key, label, type = "text"]) => {
            let options = enums[type];
            if (this.props.data.rows[type]) {
                let records = this.props.data.rows[type];
                if (type === "semesters" && this.props.view === "sections") records = records.filter(r =>
                    String(r.year_id) === String(this.state.values.campus_year_id) && (!r.programme_id || String(r.programme_id) === String(this.state.values.course_id)));
                options = records.map(r => [r.id, r.name]);
            }
            return {key, label, type: options ? "select" : type, options: options || [],
                required: ["name", "code", "start_date", "end_date", "term_start_date", "term_end_date", "academic_year_id", "course_id", "term_structure"].includes(key)};
        });
    }
    display(field) {
        const value = this.state.values[field.key];
        if (field.type === "select") return field.options.find(([id]) => String(id) === String(value))?.[1] || "Not specified";
        if (field.type === "checkbox") return value ? "Yes" : "No";
        return value || (value === 0 ? "0" : "Not specified");
    }
    change(field, event) {
        this.state.values[field.key] = field.type === "checkbox" ? event.target.checked : event.target.value;
        if (this.props.view === "sections" && ["course_id", "campus_year_id"].includes(field.key)) this.state.values.campus_term_id = "";
    }
    async save() {
        if (this.state.busy) return;
        this.state.busy = true; this.state.error = "";
        const values = {...this.state.values};
        for (const [key, , type] of FIELDS[this.props.view]) {
            if (["years", "departments", "programmes", "semesters"].includes(type)) values[key] = values[key] ? Number(values[key]) : false;
            else if (type === "number") values[key] = Number(values[key]);
            else if (!values[key] && type && type !== "checkbox") values[key] = false;
        }
        try {
            await this.orm.call("campus.academics.ui", "save_record", [this.props.view, values, this.props.record?.id || false]);
            await this.props.saved(); this.props.close();
        } catch (error) { this.state.error = error.data?.message || "The academic record was not saved. Check the form and retry."; }
        finally { this.state.busy = false; }
    }
}

export class AcademicsWorkspace extends Component {
    static template = "ideastone_erp.AcademicsWorkspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.dialog = useService("dialog");
        this.view = this.props.action.params?.view || "overview";
        this.state = useState({data: null, loading: false, error: "", query: "", filtersOpen: false, filters: {}, trend: "progress"});
        this.request = 0;
        onWillStart(() => this.load());
    }
    async load() {
        const request = ++this.request;
        this.state.loading = true; this.state.error = "";
        try {
            const data = await this.orm.call("campus.academics.ui", "get_workspace", []);
            if (request === this.request) this.state.data = data;
        } catch (error) { if (request === this.request) this.state.error = error.data?.message || "Academics could not be loaded. Retry to refresh the records."; }
        finally { if (request === this.request) this.state.loading = false; }
    }
    get title() { return META[this.view][0]; }
    get subtitle() { return META[this.view][1]; }
    get d() { return this.state.data; }
    get c() { return this.d.counts; }
    get current() { return this.d.current; }
    get addLabel() { return this.view === "years" ? "New academic year" : `Add ${LABELS[this.view]}`; }
    get areas() { return AREAS; }
    get levels() { return LEVELS; }
    get rows() {
        const f = this.state.filters, query = this.state.query.trim().toLowerCase();
        return this.d.rows[this.view]?.filter(r => [r.name, r.code, r.department, r.programme, r.year, r.semester].filter(Boolean).join(" ").toLowerCase().includes(query) &&
            (!f.status || (f.status === "active" ? r.active : r.status === f.status)) && (!f.area || r.area === f.area) &&
            (!f.department || String(r.department_id) === f.department) && (!f.level || r.level === f.level) &&
            (!f.duration || r.duration === Number(f.duration)) && (!f.year || (f.year === "missing" ? !r.year_id : String(r.year_id) === f.year)) &&
            (!f.period || r.period_type === f.period) && (!f.mapping || r.mapped === (f.mapping === "mapped")) &&
            (!f.credits || (f.credits === "positive" ? r.credits > 0 : r.credits <= 0)) && (!f.from || Number(r.start?.slice(0,4)) >= Number(f.from))) || [];
    }
    clearFilters() { this.state.filters = {}; this.state.query = ""; }
    open(record = null) {
        this.dialog.add(AcademicRecord, {view: this.view, record, data: this.d, saved: () => this.load()});
    }
    number(value, digits = 0) { return value === null || value === undefined ? "—" : new Intl.NumberFormat("en-IN", {maximumFractionDigits: digits, minimumFractionDigits: digits}).format(value); }
    percent(value) { return value === null || value === undefined ? "—" : this.number(value, value % 1 ? 1 : 0) + "%"; }
    date(value) { return value ? new Date(`${value}T12:00:00Z`).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric", timeZone: "UTC"}) : "Not specified"; }
    month(value) { return new Date(`${value}T12:00:00Z`).toLocaleDateString("en-GB", {month: "short", timeZone: "UTC"}); }
    initials(value) { return String(value || "").split(/\s+/).slice(0,2).map(w => w[0]).join("").toUpperCase(); }
    width(value) { return `${Math.min(100, Math.max(0, value || 0))}%`; }
    get stats() {
        return [{name: "Active programmes", value: this.number(this.c.programmes), icon: "▤", tint: "#eaf3ff", accent: "#1769e8", foot: "Enabled in the academic directory"},
            {name: "Curriculum coverage", value: this.percent(this.c.coverage), icon: "✓", tint: "#eaf5ef", accent: "#579477", foot: "Recorded delivery / planned lesson hours due"},
            {name: "Active class sections", value: this.number(this.c.sections), icon: "▦", tint: "#f0edff", accent: "#8172c8", foot: "Across the current academic year"},
            {name: "Items needing attention", value: this.number(this.c.checks), icon: "!", tint: "#fff4e2", accent: "#b8832d", foot: "Credits, subject, semester and section mapping checks"}];
    }
    get insights() {
        return [{title: "Confirm approved curriculum credits", text: `${this.c.missing_credits} active subjects have zero credit values. Confirm approved credits and review applied-learning opportunities with the curriculum committee.`, tag: "Curriculum opportunity", icon: "↗", tint: "#eaf3ff", accent: "#1769e8"},
            {title: "Review syllabus pacing in mid-semester", text: this.c.coverage === null ? "No lesson hours are recorded as due in the current year. Add teaching plans and execution records to measure delivery pace." : `Recorded delivery covers ${this.percent(this.c.coverage)} of lesson hours due. Review unfinished plans with department coordinators.`, tag: "Needs review", icon: "!", tint: "#fff4e2", accent: "#b8832d"},
            {title: "Complete academic mappings", text: `${this.c.missing_subjects} active subjects lack semester links; ${this.c.missing_sections} active sections lack year or semester mappings. Verify these before scheduling.`, tag: "Academic setup", icon: "＋", tint: "#eaf5ef", accent: "#579477"}];
    }
    get chart() {
        const max = Math.max(1, ...this.d.trend.flatMap(r => [r.classes, r.scheduled]));
        return this.d.trend.map(r => ({...r, actual: this.state.trend === "classes" ? r.classes * 100 / max : r.progress,
            planned: this.state.trend === "classes" ? r.scheduled * 100 / max : r.target}));
    }
    get distribution() {
        const entries = Object.entries(this.d.distribution).sort((a,b) => b[1] - a[1]);
        const max = Math.max(1, ...entries.map(r => r[1]));
        return entries.map(([name, count]) => ({name, count, width: this.width(count * 100 / max)}));
    }
    get sectionDistribution() {
        const groups = new Map();
        for (const row of this.d.rows.sections) groups.set(row.programme, (groups.get(row.programme) || 0) + 1);
        const max = Math.max(1, ...groups.values());
        return [...groups].sort((a,b) => b[1] - a[1]).slice(0,5).map(([name, count]) => ({name, count, width: this.width(count * 100 / max)}));
    }
    count(view, key, value) { return this.d.rows[view].filter(r => r[key] === value).length; }
    get programmeDepartments() { return new Set(this.d.rows.programmes.map(r => r.department_id).filter(Boolean)).size; }
    get creditTotal() { return this.d.rows.curriculum.reduce((sum, row) => sum + row.credits, 0); }
    get nextYear() { return this.d.rows.years.filter(r => r.status === "upcoming").sort((a,b) => a.start.localeCompare(b.start))[0]; }
    get prefix() { return {departments: "dept", programmes: "programme", semesters: "semester", sections: "section", curriculum: "curriculum"}[this.view]; }
    get summary() {
        return {
            departments: [["Departments", this.d.rows.departments.length, "Listed in the academic directory", "▤"], ["Active departments", this.count("departments", "active", true), "Currently enabled", "✓"], ["Students enrolled", this.c.students, "Across the current academic year", "♙"], ["Class sections", this.c.sections, "Across the current academic year", "▦"]],
            programmes: [["Programme records", this.d.rows.programmes.length, "Records in the academic directory", "▤"], ["Departments represented", this.programmeDepartments, "Across academic disciplines", "⌂"], ["Undergraduate", this.count("programmes", "level", "undergraduate"), "Programmes with a recorded undergraduate level", "♙"], ["Postgraduate & other", this.count("programmes", "level", "postgraduate") + this.count("programmes", "level", "diploma"), "Programmes with a recorded postgraduate or other level", "▦"]],
            semesters: [["Semester records", this.d.rows.semesters.length, "Current directory records", "▤"], ["Current academic year", this.current?.name || "Not set", this.current ? `${this.date(this.current.start)} – ${this.date(this.current.end)}` : "Set the approved current year", "◷"], ["Standard programme length", "8 semesters", "Typical four-year undergraduate path", "▦"], ["Setup checks", this.c.missing_terms, "Programme mapping needs review", "!"]],
            sections: [["Section records", this.d.rows.sections.length, "Records in the academic directory", "▦"], ["Programmes represented", new Set(this.d.rows.sections.map(r => r.programme_id)).size, "Across the academic directory", "▤"], ["Academic year mapped", this.d.rows.sections.filter(r => r.year_id).length, "Sections with a recorded academic year", "◷"], ["Mapping to verify", this.c.missing_sections, "Active sections missing a year or semester", "!"]],
            curriculum: [["Subject records", this.d.rows.curriculum.length, "Records in the subject directory", "▤"], ["Departments represented", new Set(this.d.rows.curriculum.map(r => r.department_id).filter(Boolean)).size, "Across academic disciplines", "⌂"], ["Credit values shown", this.number(this.creditTotal, 2), "Total recorded credits in this directory", "◈"], ["Curriculum checks", this.c.missing_credits || this.c.missing_subjects ? "Review" : "Ready", "Verify credits and semester mapping", "✓"]],
        }[this.view] || [];
    }
}
registry.category("actions").add("ideastone_erp.academics", AcademicsWorkspace);
