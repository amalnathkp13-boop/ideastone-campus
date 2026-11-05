/** @odoo-module **/
import { Component, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const EMPTY_FILTERS = {year: "", semester: "", section: "", from: "", to: ""};

class HodDetail extends Component {
    static template = "ideastone_erp.HodDashboardDetail";
    static components = { Dialog };
    static props = ["title", "columns", "rows", "actions", "close", "recordLinks?"];

    open(action) {
        this.props.close();
        return action();
    }
}

export class HodDashboard extends Component {
    static template = "ideastone_erp.HodDashboard";
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.filter = useRef("filter");
        this.filterTrigger = useRef("filterTrigger");
        this.state = useState({data: null, loading: false, error: "", filtersOpen: false,
            filters: {...EMPTY_FILTERS}, draft: {...EMPTY_FILTERS}});
        useExternalListener(window, "pointerdown", event => {
            if (this.state.filtersOpen && !this.filter.el?.contains(event.target)) {
                this.state.filtersOpen = false;
            }
        });
        onWillStart(() => this.refresh());
    }

    get d() { return this.state.data; }
    pct(value) { return value == null ? "—" : value + "%"; }
    date(value) {
        return value ? new Intl.DateTimeFormat("en-GB", {day: "2-digit", month: "short", year: "numeric"})
            .format(new Date(value.slice(0, 10) + "T12:00:00")) : "—";
    }
    progress(value) { return "width:" + Math.max(0, Math.min(100, value || 0)) + "%"; }

    async load(filters) {
        if (this.state.loading) return false;
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.hod.dashboard", "get_overview", [filters]);
            this.state.filters = {...filters};
            return true;
        } catch (error) {
            this.state.error = error.data?.message || _t("Department records could not be loaded. Try refreshing.");
            return false;
        } finally {
            this.state.loading = false;
        }
    }
    refresh() { return this.load(this.state.filters); }
    toggleFilters() {
        if (!this.state.filtersOpen) this.state.draft = {...this.state.filters};
        this.state.filtersOpen = !this.state.filtersOpen;
    }
    closeFilters() {
        this.state.filtersOpen = false;
        this.filterTrigger.el?.focus();
    }
    filterKey(event) {
        if (event.key === "Escape" && this.state.filtersOpen) {
            event.stopPropagation();
            this.closeFilters();
        }
    }
    async applyFilters() {
        if (await this.load(this.state.draft)) this.closeFilters();
    }
    async resetFilters() {
        this.state.draft = {...EMPTY_FILTERS};
        await this.applyFilters();
    }

    get kpis() {
        const d = this.d;
        return [
            {name: _t("Total students"), value: d.students, icon: "♙", foot: _t("Across %s years of study", d.years.length)},
            {name: _t("Faculty strength"), value: d.faculty, icon: "♟", foot: _t("%s on approved leave today", d.on_leave)},
            {name: _t("Department attendance"), value: this.pct(d.attendance_today), icon: "▣", foot: _t("Today · %s classes below %s", d.short_classes, this.pct(d.threshold))},
            {name: _t("Pending approvals"), value: d.pending, icon: "◷", foot: _t("Across %s review queues", d.approvals.filter(queue => queue.rows.length).length)},
            {name: _t("Exam readiness"), value: this.pct(d.readiness), icon: "✓", foot: _t("Marks submitted, locked or published")},
        ];
    }
    get metrics() {
        const d = this.d;
        return [
            {name: _t("Active sections"), value: d.active_sections, foot: d.year},
            {name: _t("Assigned subjects"), value: d.subjects, foot: _t("Department programmes and timetable")},
            {name: _t("Timetable coverage"), value: this.pct(d.coverage), foot: _t("%s periods need review", d.unassigned), progress: d.coverage, tone: ""},
            {name: _t("Student pass rate"), value: this.pct(d.pass_rate), foot: _t("Published results"), progress: d.pass_rate, tone: "green"},
            {name: _t("At-risk students"), value: d.risk, foot: _t("Below the attendance threshold"), progress: d.students ? 100 * d.risk / d.students : null, tone: "amber"},
            {name: _t("Faculty workload"), value: this.pct(d.workload), foot: _t("Periods covered by department faculty"), progress: d.workload, tone: ""},
        ];
    }
    get performance() {
        const d = this.d;
        return [[_t("Attendance"), d.attendance], [_t("Pass rate"), d.pass_rate],
            [_t("Assignment completion"), d.completion], [_t("Exam readiness"), d.readiness]];
    }
    get attentionYear() {
        return this.d.years.filter(row => row.attendance !== null && row.attendance < this.d.attendance)
            .sort((a, b) => a.attendance - b.attendance)[0];
    }
    get quickLinks() {
        return [
            {key: "students", title: _t("Student directory"), label: _t("Browse all students ↗")},
            {key: "faculty", title: _t("Faculty workload"), label: _t("Review allocations ↗")},
            {key: "exams", title: _t("Examinations & marks"), label: _t("Paper / marks review ↗")},
            {key: "reports", title: _t("Department reports"), label: _t("View analytics ↗")},
        ];
    }
    async openAction(action) {
        try {
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || _t("This workflow could not be opened."), {type: "danger"});
        }
    }
    openQueue(queue) {
        const recordLinks = queue.columns ? [] : queue.rows.map(([, , model, id]) => id ? () => this.openAction({
            type: "ir.actions.act_window", res_model: model, res_id: id, views: [[false, "form"]], target: "current",
        }) : null);
        this.dialog.add(HodDetail, {
            title: queue.name, columns: queue.columns || [_t("Record"), _t("Date")],
            rows: queue.columns ? queue.rows : queue.rows.map(row => row.slice(0, 2)), actions: queue.action ?
                [{label: _t("Open workflow"), run: () => this.openAction(queue.action)}] : [],
            recordLinks: recordLinks.some(Boolean) ? recordLinks : undefined,
        });
    }
    detail(key) {
        const d = this.d;
        const views = {
            details: [_t("Department details"), [_t("Metric"), _t("Value"), _t("Basis")],
                this.metrics.map(row => [row.name, row.value, row.foot])],
            approvals: [_t("Department approval queue"), [_t("Queue"), _t("Pending"), _t("Status")],
                d.approvals.map(row => [row.name, row.rows.length, row.rows.length ? row.status : _t("Clear")])],
            students: [_t("Student directory"), [_t("Student"), _t("Register no."), _t("Section"), _t("Attendance"), _t("Status")],
                d.student_rows.map(([name, register, section, attendance, risk]) =>
                    [name, register, section, this.pct(attendance), risk ? _t("Monitor") : attendance == null ? "—" : _t("On track")])],
            faculty: [_t("Faculty directory & workload"), [_t("Faculty member"), _t("Allocated periods"), _t("Availability")], d.faculty_rows],
            calendar: [_t("Department calendar"), [_t("Event"), _t("Date"), _t("Details"), _t("Status")],
                d.schedule.map(row => [row.name, this.date(row.date), row.detail, row.status])],
            reports: [_t("Department reports"), [_t("Indicator"), _t("Result")],
                this.performance.map(([name, value]) => [name, this.pct(value)])],
            exams: [_t("Examinations & marks"), [_t("Examination"), _t("Section"), _t("Date"), _t("Status")], d.exam_rows],
        };
        return views[key];
    }
    openDetail(key) {
        const [title, columns, rows] = this.detail(key);
        const queues = key === "approvals" ? this.d.approvals : key === "exams" ? this.d.approvals.filter(queue => ["papers", "marks"].includes(queue.key)) : [];
        const actions = queues.map(queue => ({label: queue.name, run: () => this.openQueue(queue)}));
        if (key === "details" || key === "faculty") {
            actions.push({label: _t("View timetable"), run: () => this.dialog.add(HodDetail, {
                title: _t("Department timetable"), columns: [_t("Subject"), _t("Section"), _t("Faculty"), _t("Start")],
                rows: this.d.session_rows, actions: [],
            })});
        }
        this.dialog.add(HodDetail, {title, columns, rows, actions});
    }
    exportOverview() {
        const rows = [[this.d.department, this.d.today], this.kpis.map(row => row.name), this.kpis.map(row => row.value)];
        for (const key of ["details", "approvals", "students", "faculty", "calendar", "reports", "exams"]) {
            const [title, columns, data] = this.detail(key);
            rows.push([], [title], columns, ...data);
        }
        const placements = this.d.placement_preview;
        if (placements) {
            rows.push([], [_t("Department placements · Sample data")], ...placements.metrics,
                [], [_t("Upcoming placements")], ...placements.upcoming.map(drive => [drive.name, drive.role, drive.date]));
        }
        const csv = rows.map(row => row.map(value => {
            const safe = String(value ?? "").replace(/^\s*[=+@-]/, "'$&");
            return '"' + safe.replaceAll('"', '""') + '"';
        }).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob(["\ufeff", csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "hod-overview-" + this.d.today + ".csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
}
