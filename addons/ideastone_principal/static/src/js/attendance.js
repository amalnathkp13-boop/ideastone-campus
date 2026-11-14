/** @odoo-module **/

import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const fields = ["date", "name", "number", "department", "programme", "year", "section",
    "category", "designation", "status", "check_in", "check_out", "hours", "rate", "source"];
const titles = {
    overview: ["Attendance Overview", "Institution-wide attendance performance, exceptions and trends."],
    faculty: ["Faculty Attendance", "Review staff attendance by department, category and individual staff member."],
    students: ["Student Attendance", "Review students by department, academic year, section and attendance record."],
};
const levels = { faculty: ["department_key", "category"], students: ["department_key", "year", "section"] };
const groupNames = { department_key: "department", category: "category", year: "year", section: "section" };
const statusTone = { Present: "green", Absent: "red", Late: "amber", "On Duty": "blue", Leave: "amber" };
const along = (start, end) => Math.max(1, (Date.parse(end) - Date.parse(start)) / 86400000 + 1);
const dateKey = date => date.toISOString().slice(0, 10);
let savedScope;

function counts(rows) {
    return {
        total: rows.length,
        present: rows.filter(row => ["Present", "Late"].includes(row.status)).length,
        absent: rows.filter(row => row.status === "Absent").length,
        late: rows.filter(row => row.status === "Late").length,
        duty: rows.filter(row => row.status === "On Duty").length,
        leave: rows.filter(row => row.status === "Leave").length,
    };
}

function percentage(present, total) {
    return total ? Math.round(present * 1000 / total) / 10 : null;
}

export class PrincipalAttendance extends Component {
    static template = "ideastone_principal.Attendance";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        const user = useService("user");
        const company = useService("company");
        this.filterScope = `${user.userId}:${company.currentCompany.id}`;
        this.tab = this.props.action.params?.tab || "overview";
        this.state = useState({ data: null, loading: true, error: "", filterOpen: false, filters: {},
            draft: {}, path: this.readPath(), dialog: "", period: "daily" });
        this.dialog = useRef("dialog");
        this.filterButton = useRef("filterButton");
        this.main = useRef("main");
        useEffect(dialog => {
            if (dialog && !dialog.open) dialog.showModal();
        }, () => [this.dialog.el]);
        useExternalListener(window, "popstate", () => { this.state.path = this.readPath(); });
        useExternalListener(document, "pointerdown", event => {
            if (this.state.filterOpen && !this.filterButton.el?.parentNode.contains(event.target)) this.closeFilters();
        });
        onWillStart(() => this.load(savedScope?.key === this.filterScope ? savedScope.filters : {}));
    }

    async load(filters = {}) {
        this.state.loading = true;
        this.state.error = "";
        try {
            const { year_id, department, date_from, date_to } = filters;
            const data = await this.orm.call("ideastone.principal.attendance", "get_workspace", [{
                year_id, department, date_from, date_to,
            }]);
            this.state.data = data;
            this.state.filters = { type: "", search: "", status: "", department: "", quick: "month", ...filters,
                year_id: data.year_id, date_from: data.date_from, date_to: data.date_to };
            savedScope = { key: this.filterScope, filters: { ...this.state.filters } };
        } catch (error) {
            this.state.error = error.data?.message || "Attendance could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get title() { return titles[this.tab][0]; }
    get subtitle() {
        if (!this.state.path.length) return titles[this.tab][1];
        const last = this.state.path.at(-1).label;
        if (this.depth === this.keys.length) return `${last} · Attendance records.`;
        return `${last} · ${this.groupCopy[1]}`;
    }
    get depth() { return this.state.path.length; }
    get keys() { return levels[this.tab] || []; }

    readPath() {
        const hash = new URLSearchParams(location.hash.slice(1));
        if (hash.get("pa_tab") !== this.tab) return [];
        try {
            const path = JSON.parse(hash.get("pa_path"));
            return Array.isArray(path) && path.length <= (levels[this.tab]?.length || 0)
                ? path.filter(item => typeof item?.key === "string" && typeof item.label === "string") : [];
        } catch { return []; }
    }

    go(path, replace = false) {
        const url = new URL(location.href);
        const hash = new URLSearchParams(url.hash.slice(1));
        hash.delete("pa_path");
        hash.delete("pa_tab");
        if (path.length) {
            hash.set("pa_tab", this.tab);
            hash.set("pa_path", JSON.stringify(path));
        }
        url.hash = hash.toString();
        if (replace) history.replaceState(history.state, "", url);
        else history.pushState(history.state, "", url);
        this.state.path = path;
        this.main.el?.scrollTo({ top: 0 });
    }
    back() { this.go(this.state.path.slice(0, -1)); }

    toggleFilters() {
        if (this.state.filterOpen) return this.closeFilters();
        this.state.draft = { ...this.state.filters };
        this.state.filterOpen = true;
    }
    closeFilters() { this.state.filterOpen = false; }
    setPeriod(event) {
        const today = new Date(`${this.state.data.today}T00:00:00Z`);
        const start = new Date(today);
        this.state.draft.quick = event.target.value;
        if (event.target.value === "custom") return;
        if (event.target.value === "month") start.setUTCDate(1);
        if (event.target.value === "week") start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
        this.state.draft.date_from = dateKey(start);
        this.state.draft.date_to = dateKey(today);
    }
    async apply() {
        await this.load({ ...this.state.draft });
        if (!this.state.error) {
            this.closeFilters();
            this.go([], true);
            this.filterButton.el?.focus();
        }
    }
    async reset() {
        await this.load();
        this.closeFilters();
        this.go([], true);
        this.filterButton.el?.focus();
    }
    onKey(event) {
        if (event.key === "Escape" && this.state.dialog) {
            event.preventDefault();
            event.stopPropagation();
            this.dialog.el?.close();
            this.closeDialog();
            return;
        }
        if (event.key === "Escape" && this.state.filterOpen) {
            this.closeFilters();
            this.filterButton.el?.focus();
        }
    }

    rows(scope) {
        const filters = this.state.filters;
        if (filters.type && filters.type !== scope) return [];
        const query = filters.search.trim().toLowerCase();
        return (this.state.data[scope] || []).filter(row => (!filters.status || row.status === filters.status)
            && (!query || `${row.name} ${row.number} ${row.department}`.toLowerCase().includes(query)));
    }
    onDate(rows) { return rows.filter(row => row.date === this.state.data.as_of); }
    get staff() { return this.rows("staff"); }
    get students() { return this.rows("students"); }
    get fleet() { return this.state.data.fleet; }
    get fleetTotals() {
        return this.fleet.reduce((sum, row) => ({ students: sum.students + row.students, staff: sum.staff + row.staff }),
            { students: 0, staff: 0 });
    }
    get lateShare() { return percentage(this.lateRows.length, this.staffToday.total); }
    get staffToday() { return counts(this.onDate(this.staff)); }
    get studentToday() { return counts(this.onDate(this.students)); }
    get snapshot() {
        const rows = [...this.onDate(this.staff), ...this.onDate(this.students)];
        return [
            ["Present", counts(rows).present, "green"], ["Absent", counts(rows).absent, "red"],
            ["On duty", counts(rows).duty, "blue"], ["On leave", counts(rows).leave, "amber"],
        ].map(([label, value, tone]) => ({ label, value, tone, share: percentage(value, rows.length) }));
    }
    get lateRows() { return this.onDate(this.staff).filter(row => row.status === "Late"); }
    get repeatLate() {
        const days = new Map();
        for (const row of this.staff.filter(item => item.status === "Late")) {
            days.set(row.person_id, (days.get(row.person_id) || 0) + 1);
        }
        return [...days.values()].filter(total => total > 1).length;
    }
    get shortage() {
        const people = new Map();
        for (const row of this.students) {
            if (row.rate !== null && row.rate < this.state.data.threshold) people.set(`${row.person_id}:${row.class_key}`, row);
        }
        return [...people.values()].sort((a, b) => a.rate - b.rate || a.name.localeCompare(b.name));
    }
    get critical() { return this.shortage.filter(row => row.rate < Math.min(this.state.data.threshold, 65)).length; }
    get missing() { return this.onDate(this.staff).filter(row => row.missing).length; }
    get categories() {
        const presentRate = rows => percentage(counts(rows).present, rows.length);
        return [
            ["Student attendance", this.percent(presentRate(this.onDate(this.students))), "blue"],
            ["Staff attendance", this.percent(presentRate(this.onDate(this.staff))), "green"],
            ["Teaching staff", this.percent(presentRate(this.onDate(this.staff).filter(row => row.category === "Teaching"))), ""],
            ["Non-teaching staff", this.percent(presentRate(this.onDate(this.staff).filter(row => row.category === "Non-teaching"))), ""],
            ["Classes with low attendance", new Set(this.shortage.map(row => row.class_key)).size, "red"],
        ];
    }
    get departments() {
        const buckets = new Map();
        for (const row of [...this.students, ...this.staff]) {
            const bucket = buckets.get(row.department_key) || { key: row.department_key, name: row.department, attended: 0, held: 0 };
            if (["Present", "Late"].includes(row.status)) bucket.attended++;
            bucket.held++;
            buckets.set(row.department_key, bucket);
        }
        return [...buckets.values()].map(item => ({ ...item, rate: percentage(item.attended, item.held) }))
            .sort((a, b) => a.name.localeCompare(b.name));
    }

    get chart() {
        const { effective_from: start, as_of: end } = this.state.data;
        const span = along(start, end);
        const step = this.state.period === "weekly" ? 7 : 1;
        const bins = Array.from({ length: Math.ceil(span / step) }, () => ({ students: [], staff: [] }));
        for (const [scope, rows] of [["students", this.students], ["staff", this.staff]]) {
            for (const row of rows) {
                const index = Math.floor((along(start, row.date) - 1) / step);
                bins[index][scope].push(row);
            }
        }
        const x = index => 54 + 634 * index / Math.max(1, bins.length - 1);
        const y = value => 200 - value * 1.76;
        const coordinates = scope => bins.flatMap((bin, index) => {
            const rows = bin[scope];
            return rows.length ? [{ x: x(index), y: y(percentage(counts(rows).present, rows.length)) }] : [];
        });
        return {
            grid: [100, 75, 50, 25, 0].map(value => ({ value, y: y(value) })),
            labels: [...new Set([0, Math.floor((bins.length - 1) / 2), bins.length - 1])].map(index => ({
                x: x(index), date: this.date(dateKey(new Date(Date.parse(start) + index * step * 86400000)), false),
            })),
            lines: ["students", "staff"].map(scope => {
                const points = coordinates(scope);
                return { scope, points, polyline: points.map(point => `${point.x},${point.y}`).join(" "),
                    area: points.length > 1 ? `M${points.map(point => `${point.x},${point.y}`).join(" L")} L${points.at(-1).x},200 L${points[0].x},200 Z` : "" };
            }),
            target: y(95),
        };
    }

    get visibleRows() {
        const source = this.tab === "faculty" ? this.staff : this.students;
        return source.filter(row => this.state.path.every((item, index) => String(row[this.keys[index]]) === item.key));
    }
    get groupCopy() {
        if (this.tab === "faculty") return [
            ["Department-wise faculty overview", "Select a department to view teaching and non-teaching staff categories."],
            ["Staff categories", "Choose a category to view its staff attendance records."],
            ["Faculty records", "Individual attendance, check-in/out and basic staff details."],
        ][this.depth];
        return [
            ["Department-wise student overview", "Select a department to view academic years."],
            ["Academic years", "Select an academic year to view its sections."],
            ["Sections", "Select a section to view its student attendance list."],
            ["Student attendance records", "Present/absent status, register details and attendance percentage."],
        ][this.depth];
    }
    get groups() {
        const key = this.keys[this.depth];
        const grouped = new Map();
        for (const row of this.visibleRows) {
            const id = String(row[key]);
            if (!grouped.has(id)) grouped.set(id, { key: id, label: row[groupNames[key]], rows: [] });
            grouped.get(id).rows.push(row);
        }
        return [...grouped.values()].map(group => ({ key: group.key, label: group.label, ...counts(group.rows) }))
            .sort((a, b) => a.label.localeCompare(b.label));
    }
    get listKpis() {
        const faculty = this.tab === "faculty";
        const today = faculty ? this.staffToday : this.studentToday;
        const people = new Set((faculty ? this.staff : this.students).map(row => row.person_id)).size;
        return [
            { label: faculty ? "Total faculty" : "Total students", value: people, icon: faculty ? "staff" : "students", tone: "blue", note: "In the selected view" },
            { label: this.state.data.as_of === this.state.data.today ? "Present today" : "Present", value: today.present, icon: "present", tone: "teal", valueTone: "green", note: "Includes recorded late check-ins" },
            { label: faculty ? "Absent / on leave" : this.state.data.as_of === this.state.data.today ? "Absent today" : "Absent", value: today.absent + (faculty ? today.leave : 0), icon: "absent", tone: "rose", valueTone: "red", note: "Approved leave is shown separately in records" },
            faculty ? { label: "Late arrivals", value: today.late, icon: "late", tone: "amber", valueTone: "amber", note: "Click to view late-arrival details", action: true }
                : { label: `Below ${this.state.data.threshold}% attendance`, value: this.shortage.length, icon: "shortage", tone: "amber", valueTone: "amber", note: "Shortage watchlist · saved registers" },
        ];
    }
    get insights() {
        const worst = this.departments.reduce((lowest, row) => !lowest || row.rate < lowest.rate ? row : lowest, null);
        return [
            { icon: "⚑", title: "Shortage concentration", note: `${this.shortage.length} students are below the ${this.state.data.threshold}% threshold. Review approved OD and leave before escalation.` },
            { icon: "↗", title: "Department performance", note: worst ? `${worst.name} has the lowest recorded attendance at ${worst.rate}% in this period.` : "Attendance comparisons appear after registers are submitted." },
            { icon: "◷", title: "Staff punctuality", note: `${this.repeatLate} staff members have repeated late marks in the selected period. Review their assigned schedules and check-in records.` },
        ];
    }

    openDialog(name) { this.state.dialog = name; }
    closeDialog() { this.state.dialog = ""; }
    clickDialog(event) {
        if (event.target === event.currentTarget) this.dialog.el.close();
    }
    print() { window.print(); }
    exportCSV() {
        const rows = this.tab === "overview" ? [...this.staff, ...this.students] : this.visibleRows;
        const cell = value => {
            let text = String(value ?? "");
            if (typeof value !== "number" && /^(?:[\t\r\n]|\s*[=+@-])/.test(text)) text = "'" + text;
            return '"' + text.replaceAll('"', '""') + '"';
        };
        const csv = [fields.join(","), ...rows.map(row => fields.map(key => cell(row[key])).join(","))].join("\r\n");
        const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = `attendance-${this.tab}-filtered.csv`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    tone(status) { return statusTone[status] || "blue"; }
    percent(value) { return value === null || value === undefined ? "—" : `${value}%`; }
    number(value) { return value === null || value === undefined ? "—" : value.toLocaleString("en-IN"); }
    initials(name) { return name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join(""); }
    date(value, year = true) {
        return new Date(`${value}T00:00:00Z`).toLocaleDateString("en-GB", {
            timeZone: "UTC", day: "2-digit", month: "short", ...(year ? { year: "numeric" } : {}),
        });
    }
}

registry.category("actions").add("ideastone_principal.attendance", PrincipalAttendance);
