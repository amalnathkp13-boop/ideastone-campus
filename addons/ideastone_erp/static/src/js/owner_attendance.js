/** @odoo-module **/
import { Component, onWillStart, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class OwnerAttendance extends Component {
    static template = "ideastone_erp.OwnerAttendance";
    static props = ["*"];
    static components = { Dialog };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.request = 0;
        this.state = useState({mode: "staff", month: "", department: "", search: "", chart: "weekly",
            data: null, loading: true, error: "", detail: null, modal: null, busy: false,
            assignees: [], assignee: "", due: "", note: "Please verify the source attendance records and update the review status."});
        onWillStart(() => this.load());
        useEffect(() => {
            if ((this.state.detail || this.state.modal) && !this.closePopup) {
                this.closePopup = this.dialog.add(OwnerAttendancePopup, {owner: this}, {onClose: () => {
                    this.closePopup = null;
                    this.state.detail = null;
                    this.state.modal = null;
                }});
            } else if (!this.state.detail && !this.state.modal && this.closePopup) {
                const close = this.closePopup;
                this.closePopup = null;
                close();
            }
        }, () => [!!this.state.detail, !!this.state.modal]);
    }
    async load() {
        const request = ++this.request;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.owner.attendance.ui", "get_dashboard", [this.state.mode, this.state.month || null, this.state.department]);
            if (request !== this.request) return;
            this.state.data = data;
            this.state.month = data.month;
        } catch (error) {
            if (request === this.request) this.state.error = error.data?.message || "Attendance could not be loaded. Please retry.";
        } finally { if (request === this.request) this.state.loading = false; }
    }
    get d() { return this.state.data; }
    get staff() { return this.state.mode === "staff"; }
    get rows() { const query = this.state.search.trim().toLowerCase(); return (this.d?.departments || []).filter(row => !query || row.name.toLowerCase().includes(query)); }
    rate(value) { return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`; }
    get metrics() {
        const t = this.d.totals;
        return this.staff ? [
            ["Staff Attendance", this.rate(t.rate), "Present / scheduled excluding leave", "blue", "bar-chart"],
            ["Present Today", t.present, "Recorded check-ins", "green", "users"],
            ["Delayed Arrivals", t.late, "Existing staff calendar policy", "amber", "clock-o"],
            ["Approved Leave", t.leave, "Verified in leave module", "purple", "calendar"],
            ["Unverified Absences", t.absent, "Elapsed workdays · HR review", "red", "exclamation-triangle"],
            ["Missing Punches", t.missing, "After the scheduled workday", "amber", "clock-o"]] : [
            ["Student Attendance", this.rate(t.rate), "Submitted eligible sessions", "blue", "bar-chart"],
            ["Enrolled Students", t.students, "Across selected departments", "green", "users"],
            ["Below Limit", t.below, `College threshold ${this.d.threshold}%`, "red", "exclamation-triangle"],
            ["Pending Sessions", t.pending, "Faculty submission pending", "amber", "clock-o"],
            ["Departments", this.d.departments.length, "In selected scope", "purple", "building-o"]];
    }
    async mode(mode) { Object.assign(this.state, {mode, department: "", search: "", detail: null}); await this.load(); }
    async filter(event, field) { this.state[field] = event.target.value; this.state.detail = null; await this.load(); }
    async clear() { Object.assign(this.state, {department: "", search: "", month: this.d.today.slice(0, 7)}); await this.load(); }
    reviewFor(issue) { return this.d.reviews.find(row => row.issue === issue.id && row.status !== "Closed"); }
    async assign(issue) {
        const review = this.reviewFor(issue);
        if (review) { this.state.modal = {type: "track", review}; return; }
        this.state.busy = true;
        try {
            const options = await this.orm.call("campus.owner.attendance.ui", "review_options", [this.state.mode, this.state.month, issue.id]);
            Object.assign(this.state, {assignees: options, assignee: options[0]?.id.toString() || "", due: this.d.today,
                modal: {type: "assign", issue}});
        } catch (error) { this.notify(error); }
        finally { this.state.busy = false; }
    }
    notify(error) { this.notification.add(error.data?.message || "The review could not be saved.", {type: "danger"}); }
    async saveReview() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            await this.orm.call("campus.owner.attendance.ui", "assign_review", [this.state.mode, this.state.month,
                this.state.modal.issue.id, Number(this.state.assignee), this.state.due, this.state.note]);
            this.state.modal = null;
            await this.load();
            this.notification.add("Attendance review assigned.", {type: "success"});
        } catch (error) { this.notify(error); }
        finally { this.state.busy = false; }
    }
    async escalate() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            await this.orm.call("campus.owner.attendance.ui", "escalate_review", [this.state.modal.review.id]);
            this.state.modal = null;
            await this.load();
            this.notification.add("Review escalation recorded.", {type: "success"});
        } catch (error) { this.notify(error); }
        finally { this.state.busy = false; }
    }
    openReview(review) {
        return this.action.doAction({type: "ir.actions.act_window", name: "Attendance review", res_model: "campus.service.request",
            res_id: review.id, views: [[false, "form"]], context: {campus_module: "attendance"}});
    }
    get trend() { return this.d[this.state.chart]; }
    get detail() { return this.state.detail; }
    department(row) { this.state.detail = {type: "department", title: row.name, department: row}; }
    staffDetail(person) { this.state.detail = {...this.detail, type: "staff", title: person.name, person}; }
    classDetail(row) { this.state.detail = {...this.detail, type: "class", title: row.name, class: row}; }
    studentDetail(person) { this.state.detail = {...this.detail, type: "student", title: person.name, person}; }
    backDepartment() { this.department(this.detail.department); }
    backClass() { this.classDetail(this.detail.class); }
    get insights() {
        const t = this.d.totals;
        return this.staff ? [
            ["Missing punch verification", `${t.missing} completed-day punch records need HR review.`],
            ["Leave is separate from absence", `${t.leave} staff have approved leave. Open workdays are not finalized as absence.`]] : [
            ["Unsubmitted teaching sessions", `${t.pending} sessions await faculty submission. They are not automatically student absences.`],
            ["Student shortage monitoring", `${t.below} students have recorded attendance below the college's ${this.d.threshold}% threshold.`]];
    }
    csv(rows, name) {
        const safe = value => { const text = String(value ?? ""); return /^[\s]*[=+@\-\t\r]/.test(text) ? "'" + text : text; };
        const text = rows.map(row => row.map(value => `"${safe(value).replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob(["\uFEFF" + text], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a"); link.href = url; link.download = name; link.click(); URL.revokeObjectURL(url);
    }
    exportOverview() {
        const headings = this.staff ? ["Department", "Scheduled", "Present", "Approved leave", "Unverified absence", "Delayed arrivals", "Missing punches"] : ["Department", "Students", "Attendance (%)", "Below limit", "Pending sessions"];
        this.csv([headings, ...this.rows.map(row => this.staff ? [row.name, row.scheduled, row.present, row.leave, row.absent, row.late, row.missing] :
            [row.name, row.students, row.rate, row.below, row.pending])], `VCET-${this.state.mode}-attendance-${this.state.month}.csv`);
    }
    exportStudent() {
        const person = this.detail.person;
        this.csv([["Student", "Register", "Subject", "Attended", "Held", "Rate (%)"],
            ...person.subjects.map(row => [person.name, person.roll, row.subject, row.present, row.sessions, row.rate])], `Student-attendance-${person.id}.csv`);
    }
}
class OwnerAttendancePopup extends OwnerAttendance {
    static template = "ideastone_erp.OwnerAttendancePopup";
    setup() {
        this.state = useState(this.props.owner.state);
        this.orm = this.props.owner.orm;
        this.notification = this.props.owner.notification;
        this.action = this.props.owner.action;
    }
    load() { return this.props.owner.load(); }
    openReview(review) { this.props.close(); return this.props.owner.openReview(review); }
}
registry.category("actions").add("ideastone_erp.owner_attendance_overview", OwnerAttendance);
