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
        this.state = useState({loading: true, saving: false, error: "", data: null,
            termId: "", facultyId: "", date: "", subjectKey: "", sessionId: "",
            page: 1, notes: "", holdDate: false});
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
        } catch (error) {
            this.state.error = error.data?.message || "Subject attendance could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get selectedSubject() {
        return this.state.data?.subjects.find((item) => item.key === this.state.subjectKey);
    }

    get visibleStudents() {
        const offset = (this.state.page - 1) * 8;
        return (this.state.data?.students || []).slice(offset, offset + 8);
    }

    get pageCount() {
        return Math.max(1, Math.ceil((this.state.data?.students.length || 0) / 8));
    }

    get pageNumbers() {
        const total = this.pageCount;
        if (total <= 5) return Array.from({length: total}, (_, index) => index + 1);
        const current = this.state.page;
        const start = Math.max(1, Math.min(current - 1, total - 2));
        return [start, start + 1, start + 2];
    }

    get studentRange() {
        const count = this.state.data?.students.length || 0;
        return count ? `Showing ${(this.state.page - 1) * 8 + 1} to ${Math.min(this.state.page * 8, count)} of ${count} students` : "No students in this class";
    }

    async changeTerm(event) {
        this.state.termId = event.target.value;
        this.state.subjectKey = "";
        this.state.sessionId = "";
        this.state.page = 1;
        await this.load();
    }

    async changeFaculty(event) {
        this.state.facultyId = event.target.value;
        this.state.subjectKey = "";
        this.state.sessionId = "";
        this.state.page = 1;
        await this.load();
    }

    async changeDate(event) {
        this.state.date = event.target.value;
        this.state.sessionId = "";
        await this.load();
    }

    async chooseSubject(key) {
        this.state.subjectKey = key;
        this.state.sessionId = "";
        this.state.page = 1;
        await this.load();
    }

    async chooseHour(event) {
        this.state.sessionId = event.target.value;
        await this.load();
    }

    changeStatus(id, event) {
        const student = this.state.data.students.find((item) => item.id === id);
        if (student) student.status = event.target.value;
    }

    changeNotes(event) { this.state.notes = event.target.value; }
    changeHoldDate(event) { this.state.holdDate = event.target.checked; }
    setPage(page) { this.state.page = Math.max(1, Math.min(page, this.pageCount)); }

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
            ...(this.state.data?.subjects || []).map((item) => [item.code, item.name, item.class, item.students])];
        const csv = "\ufeff" + rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "subject-attendance-subjects.csv";
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.subject_attendance_workspace", SubjectAttendanceWorkspace);
