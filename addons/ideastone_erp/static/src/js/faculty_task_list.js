/** @odoo-module **/
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/webclient/actions/action_hook";

export class FacultyTaskList extends Component {
    static template = "ideastone_erp.FacultyTaskList";
    static props = ["*"];
    static mode = "mentor";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.state = useState({data: null, loading: true, saving: false, error: "", classKey: "", termId: "",
            date: "", subjectKey: "", sessionId: "", search: "", filter: "all", page: 1, step: 1,
            statuses: {}, notes: "", dirty: false, profile: null, followup: null, confirm: false});
        useSetupAction({beforeLeave: () => {
            if (this.state.dirty) this.notification.add("Save or discard your attendance draft before leaving this page.", {type: "warning"});
            return !this.state.dirty;
        }, beforeUnload: event => {
            if (this.state.dirty) { event.preventDefault(); event.returnValue = ""; }
        }});
        onWillStart(() => this.load());
    }
    get mentor() { return this.constructor.mode === "mentor"; }
    get d() { return this.state.data; }
    get title() { return this.mentor ? "My Mentorship Class" : "My Teaching Subjects"; }
    get subject() { return this.d?.subjects.find(row => row.key === this.state.subjectKey); }
    get editable() { return !this.mentor && this.d?.can_save && !this.state.saving; }
    get riskRows() { return (this.d?.students || []).filter(row => row.shortage); }
    get counts() {
        const values = Object.values(this.state.statuses);
        return {total: values.length, present: values.filter(x => ["present", "late"].includes(x)).length,
            absent: values.filter(x => x === "absent").length, protected: values.filter(x => x === "excused").length,
            unmarked: values.filter(x => x === "unmarked").length};
    }
    get filteredRows() {
        const query = this.state.search.toLowerCase().trim();
        return (this.d?.students || []).filter(row => (!query || `${row.name} ${row.roll}`.toLowerCase().includes(query)) &&
            (this.state.filter === "all" || (this.mentor ? this.state.filter === "risk" ? row.shortage : row.followup : this.state.statuses[row.id] === this.state.filter)));
    }
    get pageCount() { return Math.max(1, Math.ceil(this.filteredRows.length / 8)); }
    get rows() { return this.filteredRows.slice((this.state.page - 1) * 8, this.state.page * 8); }
    get ready() { return this.editable && this.counts.total > 0 && this.counts.unmarked === 0 && this.state.notes.trim().length > 0; }
    rate(value) { return value === null || value === undefined ? "—" : `${value}%`; }
    status(value) { return {present: "Present", absent: "Absent", excused: "Approved OD / Leave", late: "Late", unmarked: "Unmarked"}[value] || value; }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.faculty.task.list", this.mentor ? "get_mentor_data" : "get_teaching_data",
                this.mentor ? [this.state.classKey || false] : [this.state.termId || false, this.state.date || false, this.state.subjectKey || false, this.state.sessionId || false]);
            this.state.data = data;
            if (this.mentor) this.state.classKey = data.class_key;
            else Object.assign(this.state, {termId: String(data.term_id || ""), date: data.date, subjectKey: data.subject_key,
                sessionId: String(data.session_id || ""), notes: data.notes,
                statuses: Object.fromEntries(data.students.map(row => [row.id, data.sheet_state === "unrecorded" ? "unmarked" : row.status]))});
            this.state.dirty = false;
            this.state.page = Math.min(this.state.page, this.pageCount);
        } catch (error) { this.state.error = error.data?.message || "Your task list could not be loaded. Please retry."; }
        finally { this.state.loading = false; }
    }
    async change(event, key) {
        if (this.state.dirty) {
            const saved = {classKey: this.d.class_key, termId: String(this.d.term_id || ""),
                date: this.d.date, subjectKey: this.d.subject_key, sessionId: String(this.d.session_id || "")};
            this.state[key] = saved[key];
            event.target.value = saved[key];
            return this.notification.add("Save or discard your draft before changing the selected session.", {type: "warning"});
        }
        this.state[key] = event.target.value;
        if (key !== "sessionId") this.state.sessionId = "";
        if (key === "termId") this.state.subjectKey = "";
        this.state.page = 1;
        await this.load();
    }
    search(event) { this.state.search = event.target.value; this.state.page = 1; }
    filter(event) { this.state.filter = event.target.value; this.state.page = 1; }
    setPage(page) { this.state.page = Math.max(1, Math.min(page, this.pageCount)); }
    setStep(step) { this.state.step = step; this.root.el.querySelector(`#task-step-${step}`)?.scrollIntoView({behavior: "smooth", block: "start"}); }
    mark(row, status) {
        if (!this.editable || row.status === "excused") return;
        this.state.statuses[row.id] = status;
        this.state.dirty = true;
    }
    markAll() {
        for (const row of this.d.students) this.mark(row, "present");
    }
    notes(event) { this.state.notes = event.target.value; this.state.dirty = true; }
    showProfile(row) { this.state.profile = {...row, ...(row.performance || {})}; }
    showFollowup(row) { this.state.followup = {id: row.id, name: row.name, note: ""}; }
    async saveFollowup() {
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            await this.orm.call("campus.faculty.task.list", "save_followup", [this.state.followup.id, this.state.followup.note, this.state.classKey]);
            this.state.followup = null;
            await this.load();
            this.notification.add("Follow-up saved to mentor counseling.", {type: "success"});
        } catch (error) { this.notification.add(error.data?.message || "The follow-up could not be saved.", {type: "danger"}); }
        finally { this.state.saving = false; }
    }
    async save(submit = false) {
        if (!this.editable || this.counts.unmarked) return;
        this.state.saving = true;
        try {
            const result = await this.orm.call("campus.faculty.task.list", "save_teaching_attendance", [Number(this.state.sessionId), this.state.statuses, this.state.notes, submit]);
            this.state.confirm = false;
            await this.load();
            this.notification.add(result.message, {type: "success"});
        } catch (error) { this.notification.add(error.data?.message || "Attendance could not be saved.", {type: "danger"}); }
        finally { this.state.saving = false; }
    }
    download(kind) {
        const rows = kind === "history" ? this.d.history : this.d.students;
        const fields = kind === "history" ? ["date", "subject", "class", "hour", "present", "absent", "status"] : ["roll", "name", "present", "held", "rate"];
        const escape = value => `"${String(value ?? "").replace(/^[=+@\-]/, "'$&").replaceAll('"', '""')}"`;
        const csv = [fields.join(","), ...rows.map(row => fields.map(key => escape(row[key])).join(","))].join("\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a"); link.href = url; link.download = `${this.mentor ? "mentorship" : "teaching"}-${kind}.csv`; link.click(); URL.revokeObjectURL(url);
    }
}

export class MyTeachingSubjects extends FacultyTaskList { static mode = "teaching"; }
registry.category("actions").add("ideastone_erp.my_mentorship_class", FacultyTaskList);
registry.category("actions").add("ideastone_erp.my_teaching_subjects", MyTeachingSubjects);
