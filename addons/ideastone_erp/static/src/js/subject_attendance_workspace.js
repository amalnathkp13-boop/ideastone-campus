/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SubjectAttendanceWorkspace extends Component {
    static template = "ideastone_erp.SubjectAttendanceWorkspace";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({loading: true, saving: false, error: "", data: null,
            termId: "", facultyId: "", date: "", subjectKey: "", sessionId: "",
            page: 1, subjectPage: 1, subjectPageSize: 10, allocationPage: 1, classPage: 1, notes: "",
            subjectSearch: "", studentSearch: "", studentStatus: "all", showRoll: true,
            selectedStudents: []});
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.subject.attendance.ui", "get_dashboard", [
                this.state.termId || false, this.state.facultyId || false, this.state.date || false,
                this.state.subjectKey || false, this.state.sessionId || false,
            ]);
            this.state.data = data;
            this.state.termId = String(data.term_id || "");
            this.state.facultyId = String(data.faculty_id || "");
            this.state.date = data.date;
            this.state.subjectKey = data.subject_key || "";
            this.state.sessionId = String(data.session_id || "");
            this.state.notes = data.notes || "";
            this.state.page = Math.min(this.state.page, this.pageCount);
            this.state.subjectPage = Math.min(this.state.subjectPage, this.subjectPageCount);
            this.state.allocationPage = Math.min(this.state.allocationPage, this.allocationPageCount);
            this.state.classPage = Math.min(this.state.classPage, this.classPageCount);
        } catch (error) {
            this.state.error = error.data?.message || "Subject attendance could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get selectedSubject() {
        return this.state.data?.subjects.find((item) => item.key === this.state.subjectKey);
    }

    get filteredSubjects() {
        const query = this.state.subjectSearch.trim().toLowerCase();
        return (this.state.data?.subjects || []).filter(
            (item) => !query || [item.code, item.name, item.class].some(
                (value) => String(value || "").toLowerCase().includes(query)
            )
        );
    }

    get subjectPageCount() {
        return Math.max(1, Math.ceil(this.filteredSubjects.length / this.state.subjectPageSize));
    }

    get visibleSubjects() {
        const start = (this.state.subjectPage - 1) * this.state.subjectPageSize;
        return this.filteredSubjects.slice(start, start + this.state.subjectPageSize);
    }

    get filteredStudents() {
        const query = this.state.studentSearch.trim().toLowerCase();
        return (this.state.data?.students || []).filter((item) =>
            (this.state.studentStatus === "all" || item.status === this.state.studentStatus) &&
            (!query || [item.roll, item.name, item.class].some(
                (value) => String(value || "").toLowerCase().includes(query)
            ))
        );
    }

    get visibleStudents() {
        const offset = (this.state.page - 1) * 8;
        return this.filteredStudents.slice(offset, offset + 8);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.filteredStudents.length / 8));
    }

    get pageNumbers() {
        const total = this.pageCount;
        if (total <= 5) return Array.from({length: total}, (_, index) => index + 1);
        const current = this.state.page;
        const start = Math.max(1, Math.min(current - 1, total - 2));
        return [start, start + 1, start + 2];
    }

    get studentRange() {
        const count = this.filteredStudents.length;
        return count ? `Showing ${(this.state.page - 1) * 8 + 1} to ${Math.min(this.state.page * 8, count)} of ${count} students` : "No students in this class";
    }

    get allocationPageCount() {
        return Math.max(1, Math.ceil((this.state.data?.allocations.length || 0) / 5));
    }

    get visibleAllocations() {
        const start = (this.state.allocationPage - 1) * 5;
        return (this.state.data?.allocations || []).slice(start, start + 5);
    }

    get classPageCount() {
        return Math.max(1, Math.ceil((this.state.data?.classes.length || 0) / 4));
    }

    get visibleClasses() {
        const start = (this.state.classPage - 1) * 4;
        return (this.state.data?.classes || []).slice(start, start + 4);
    }

    get trendMax() {
        return Math.max(1, ...(this.state.data?.trend || []).flatMap(
            (item) => [item.present, item.absent, item.excused]
        ));
    }

    get trendScale() {
        return Math.max(20, Math.ceil(this.trendMax / 20) * 20);
    }

    get trendTicks() {
        return [4, 3, 2, 1, 0].map((step) => step * this.trendScale / 4);
    }

    get trendMonths() {
        const date = new Date(`${(this.state.data?.date || this.state.date).slice(0, 7)}-15T12:00:00Z`);
        return Array.from({length: 12}, (_, index) => {
            const month = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - index, 15));
            return {value: month.toISOString().slice(0, 7), label: month.toLocaleDateString(undefined, {month: "short", year: "numeric", timeZone: "UTC"})};
        });
    }

    chartHeight(value) {
        return value ? `${Math.max(4, Math.round(value * 100 / this.trendScale))}%` : "0%";
    }

    displayDate(value) { return value ? value.split("-").reverse().join("/") : ""; }

    async changeTerm(event) {
        this.state.termId = event.target.value;
        this.state.subjectKey = "";
        this.state.sessionId = "";
        this.state.page = 1;
        this.state.subjectPage = 1;
        this.state.selectedStudents = [];
        await this.load();
    }

    async changeFaculty(event) {
        this.state.facultyId = event.target.value;
        this.state.subjectKey = "";
        this.state.sessionId = "";
        this.state.page = 1;
        this.state.subjectPage = 1;
        this.state.selectedStudents = [];
        await this.load();
    }

    async changeDate(event) {
        this.state.date = event.target.value;
        this.state.sessionId = "";
        await this.load();
    }

    async changeTrendMonth(event) {
        this.state.date = `${event.target.value}-01`;
        this.state.sessionId = "";
        await this.load();
    }

    async chooseSubject(key) {
        this.state.subjectKey = key;
        this.state.sessionId = "";
        this.state.page = 1;
        this.state.selectedStudents = [];
        await this.load();
    }

    async chooseHour(event) {
        this.state.sessionId = event.target.value;
        await this.load();
    }

    async chooseAllocation(allocation) {
        this.state.date = allocation.date;
        this.state.sessionId = String(allocation.id);
        await this.load();
    }

    changeStatus(id, event) {
        const student = this.state.data.students.find((item) => item.id === id);
        if (student) student.status = event.target.value;
    }

    changeNotes(event) { this.state.notes = event.target.value; }
    setPage(page) { this.state.page = Math.max(1, Math.min(page, this.pageCount)); }
    setSubjectPage(page) { this.state.subjectPage = Math.max(1, Math.min(page, this.subjectPageCount)); }
    setAllocationPage(page) { this.state.allocationPage = Math.max(1, Math.min(page, this.allocationPageCount)); }
    setClassPage(page) { this.state.classPage = Math.max(1, Math.min(page, this.classPageCount)); }
    changeSubjectPageSize(event) { this.state.subjectPageSize = Number(event.target.value); this.state.subjectPage = 1; }
    searchSubjects(event) { this.state.subjectSearch = event.target.value; this.state.subjectPage = 1; }
    searchStudents(event) { this.state.studentSearch = event.target.value; this.state.page = 1; }
    filterStudents(event) { this.state.studentStatus = event.target.value; this.state.page = 1; }
    toggleRoll(event) { this.state.showRoll = event.target.checked; }
    toggleStudent(id, event) {
        this.state.selectedStudents = event.target.checked
            ? [...this.state.selectedStudents, id]
            : this.state.selectedStudents.filter((item) => item !== id);
    }
    toggleVisibleStudents(event) {
        const visible = this.visibleStudents.map((item) => item.id);
        this.state.selectedStudents = event.target.checked
            ? [...new Set([...this.state.selectedStudents, ...visible])]
            : this.state.selectedStudents.filter((id) => !visible.includes(id));
    }

    async save() {
        if (!this.state.data?.can_save || !this.state.sessionId || this.state.saving) return;
        this.state.saving = true;
        try {
            const statuses = Object.fromEntries(this.state.data.students.map((item) => [item.id, item.status]));
            const result = await this.orm.call("campus.subject.attendance.ui", "save_attendance", [
                Number(this.state.sessionId), statuses, this.state.notes,
            ]);
            this.notification.add(result.message, {type: "success"});
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Attendance could not be saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    exportSubjects() {
        const rows = [["Code", "Subject", "Class", "Students"],
            ...this.filteredSubjects.map((item) => [item.code, item.name, item.class, item.students])];
        const csv = "\ufeff" + rows.map((row) => row.map((value) => {
            const safe = String(value ?? "");
            return `"${( /^[=+\-@\t\r]/.test(safe) ? "'" + safe : safe).replaceAll('"', '""')}"`;
        }).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "subject-attendance-subjects.csv";
        link.click();
        URL.revokeObjectURL(url);
    }

    printSubjects() { window.print(); }

    openRecord(model, id, title) {
        this.action.doAction({type: "ir.actions.act_window", name: title, res_model: model,
            res_id: id, views: [[false, "form"]], target: "current"});
    }

    openAllocations() {
        if (!this.state.data?.can_manage_allocations) return;
        this.action.doAction({type: "ir.actions.act_window", name: "Teaching hours",
            res_model: "op.session", views: [[false, "tree"], [false, "form"]],
            domain: [["faculty_id", "=", Number(this.state.facultyId)]],
            context: {default_faculty_id: Number(this.state.facultyId),
                default_subject_id: this.selectedSubject?.subject_id,
                default_batch_id: this.selectedSubject?.batch_id}, target: "current"});
    }

    openClasses() {
        if (!this.state.data?.can_manage_allocations) return;
        this.action.doAction({type: "ir.actions.act_window", name: "Allocated classes",
            res_model: "op.batch", views: [[false, "tree"], [false, "form"]],
            domain: [["id", "in", this.state.data.classes.map((item) => item.id)]],
            target: "current"});
    }

    openHistory() {
        this.action.doAction({type: "ir.actions.act_window", name: "Attendance history",
            res_model: "op.attendance.sheet", views: [[false, "tree"], [false, "form"]],
            domain: [["session_id", "in", this.state.data.allocations.map((item) => item.id)]],
            target: "current"});
    }

    openLessonPlanner() {
        this.action.doAction({type: "ir.actions.act_window", name: "Lesson plans",
            res_model: "campus.teaching.plan", views: [[false, "tree"], [false, "form"]],
            domain: [["faculty_id", "=", Number(this.state.facultyId)]],
            context: {default_faculty_id: Number(this.state.facultyId),
                default_subject_id: this.selectedSubject?.subject_id,
                default_batch_id: this.selectedSubject?.batch_id}, target: "current"});
    }
}

registry.category("actions").add("ideastone_erp.subject_attendance_workspace", SubjectAttendanceWorkspace);
