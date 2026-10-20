/** @odoo-module **/
import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class StudentAttendanceWorkspace extends Component {
    static template = "ideastone_erp.StudentAttendanceWorkspace";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        const now = new Date();
        const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
        this.state = useState({loading: true, saving: false, error: "", data: null,
            yearId: "", termId: "", departmentId: "", facultyId: "", batchId: "", sessionId: "",
            date, notes: "", absentIds: [], classPage: 0, studentPage: 0,
            showRegister: false, rosterFilter: "all", chart: "weekly"});
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.student.attendance.ui", "get_dashboard", [
                this.state.yearId || false, this.state.departmentId || false,
                this.state.facultyId || false, this.state.batchId || false,
                this.state.date, this.state.sessionId || false, this.state.termId || false,
            ]);
            this.state.data = data;
            this.state.yearId = String(data.year_id || "");
            this.state.termId = String(data.term_id || "");
            this.state.departmentId = String(data.department_id || "");
            this.state.facultyId = String(data.faculty_id || "");
            this.state.batchId = String(data.batch_id || "");
            this.state.sessionId = String(data.session_id || "");
            this.state.notes = data.notes || "";
            this.state.absentIds = data.students.filter((student) => student.absent).map((student) => student.id);
        } catch (error) {
            this.state.error = error.data?.message || "Student attendance could not be loaded.";
        } finally {
            this.state.loading = false;
        }
    }

    async changeDepartment(event) {
        this.state.departmentId = event.target.value;
        this.state.facultyId = "";
        this.state.batchId = "";
        this.state.sessionId = "";
        this.state.classPage = 0;
        await this.load();
    }
    async changeFaculty(event) {
        this.state.facultyId = event.target.value;
        this.state.batchId = "";
        this.state.sessionId = "";
        this.state.classPage = 0;
        await this.load();
    }
    async changeDate(event) {
        this.state.date = event.target.value;
        this.state.yearId = "";
        this.state.termId = "";
        this.state.sessionId = "";
        await this.load();
    }
    async changeTerm(event) {
        this.state.termId = event.target.value;
        this.state.batchId = "";
        this.state.sessionId = "";
        this.state.classPage = 0;
        await this.load();
    }
    async selectClass(id) {
        this.state.batchId = String(id);
        this.state.sessionId = "";
        this.state.studentPage = 0;
        await this.load();
    }
    async selectHour(id) {
        this.state.sessionId = String(id);
        await this.load();
    }
    changeNotes(event) { this.state.notes = event.target.value; }
    changeRosterFilter(event) { this.state.rosterFilter = event.target.value; this.state.studentPage = 0; }
    toggleRegister(event) { this.state.showRegister = event.target.checked; }
    toggleAbsent(id) {
        const chosen = new Set(this.state.absentIds);
        if (chosen.has(id)) chosen.delete(id);
        else chosen.add(id);
        this.state.absentIds = [...chosen];
    }
    toggleAllAbsent(event) {
        const chosen = new Set(this.state.absentIds);
        for (const student of this.visibleStudents) {
            if (event.target.checked) chosen.add(student.id);
            else chosen.delete(student.id);
        }
        this.state.absentIds = [...chosen];
    }
    isAbsent(id) { return this.state.absentIds.includes(id); }

    get selectedClass() {
        return this.state.data?.classes.find((item) => String(item.id) === this.state.batchId);
    }
    get academicYearName() {
        return this.state.data?.years.find((item) => String(item.id) === this.state.yearId)?.name || "—";
    }
    get classesPage() { return this.state.data?.classes.slice(this.state.classPage * 4, this.state.classPage * 4 + 4) || []; }
    get classPages() { return Math.max(1, Math.ceil((this.state.data?.classes.length || 0) / 4)); }
    get visibleStudents() {
        const students = this.state.data?.students || [];
        return this.state.rosterFilter === "absent" ? students.filter((item) => this.state.absentIds.includes(item.id)) : students;
    }
    get studentsPage() { return this.visibleStudents.slice(this.state.studentPage * 6, this.state.studentPage * 6 + 6); }
    get studentPages() { return Math.max(1, Math.ceil(this.visibleStudents.length / 6)); }
    setClassPage(delta) { this.state.classPage = Math.max(0, Math.min(this.classPages - 1, this.state.classPage + delta)); }
    setStudentPage(delta) { this.state.studentPage = Math.max(0, Math.min(this.studentPages - 1, this.state.studentPage + delta)); }
    setChart(value) { this.state.chart = value; }
    get chartBars() {
        if (this.state.chart === "weekly") return this.state.data?.trend || [];
        return [{label: this.state.data?.month_name || "Month", rate: this.state.data?.metrics.rate || 0}];
    }

    async save() {
        if (!this.state.sessionId || this.state.saving) return;
        this.state.saving = true;
        try {
            const result = await this.orm.call("campus.student.attendance.ui", "save_hour", [
                Number(this.state.sessionId), this.state.absentIds, this.state.notes,
            ]);
            this.notification.add(result.message, {type: "success"});
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Attendance could not be saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    exportClasses() {
        const rows = [["Class", "Academic Year", "Semester", "From Date", "To Date", "Students"],
            ...(this.state.data?.classes || []).map((item) => [item.name, item.year, item.semester, item.from, item.to, item.total])];
        const csv = "\ufeff" + rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "student-attendance-classes.csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    async viewHistory() {
        await this.action.doAction({type: "ir.actions.act_window", name: "Attendance History",
            res_model: "op.attendance.sheet", views: [[false, "tree"], [false, "form"]],
            domain: [["batch_id", "=", Number(this.state.batchId)], ["campus_managed", "=", true]],
            target: "current"});
    }
    viewInsights() { document.querySelector(".sa_insights")?.scrollIntoView({behavior: "smooth", block: "center"}); }
}

registry.category("actions").add("ideastone_erp.student_attendance_workspace", StudentAttendanceWorkspace);
