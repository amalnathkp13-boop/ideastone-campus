/** @odoo-module **/
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/webclient/actions/action_hook";
import { FacultyQuestionPapers } from "./faculty_question_papers";

const PAGES = {
    timetable: ["Timetable", "Check your teaching hours, rooms, mentorship periods and substitute assignments."],
    attendance: ["Student Attendance", "Record your assigned mentorship-class daily attendance and review individual performance."],
    tasks: ["My Tasks & e-Diary", "Track assigned faculty work and maintain an academic activity diary."],
    exams: ["Examinations & Marks", "Enter internal assessment marks, check deadlines and monitor submission readiness."],
    assignments: ["Assignments", "Publish class assignments, monitor submissions and review student work."],
    alternate: ["Alternate Hour", "Coordinate substitute teaching and ensure classes are covered during faculty absences."],
    lessons: ["Lesson Plans", "Plan weekly teaching outcomes and track syllabus coverage across your subjects."],
    circulars: ["Circulars & Announcements", "Review official college and departmental notices and record acknowledgement."],
};
const MARKS = {present: "Present", absent: "Absent", late: "Late", excused: "Approved OD / Leave", unmarked: "Unmarked"};
const ASSESSMENT = {draft: "Draft", entry: "Entry in progress", submitted: "Submitted", locked: "Locked", published: "Published"};
const ASSIGNMENT = {draft: "Draft", publish: "Open", finish: "Closed", cancel: "Cancelled"};
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export class FacultySopPapers extends FacultyQuestionPapers {
    static template = "ideastone_erp.FacultySopPapers";
}

export class FacultySop extends Component {
    static template = "ideastone_erp.FacultySop";
    static components = { FacultySopPapers };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.drawer = useRef("drawer");
        this.page = this.props.action.params.page;
        this.weekdays = WEEKDAYS;
        this.markOptions = ["present", "absent", "late"];
        this.state = useState({
            data: null, error: "", loading: true, busy: false, dirty: false,
            filter: "All", search: "", day: 0, classKey: "", date: "", period: "FN",
            allocation: "", subjectId: "", examId: "", register: null, values: {},
            selected: null, modal: null, form: {}, gradeForm: {}, diary: "", diaryDate: "",
            alternateDate: "", alternateClass: "", alternateSession: "", replacement: "", reason: "",
        });
        onWillStart(() => this.load(true));
        useEffect(() => {
            if (this.state.modal) this.drawer.el?.querySelector("button")?.focus();
        }, () => [this.state.modal]);
        useSetupAction({
            beforeLeave: () => !this.state.dirty || this.unsaved(),
            beforeUnload: event => {
                if (this.state.dirty) { event.preventDefault(); event.returnValue = ""; }
            },
        });
    }

    get d() { return this.state.data; }
    get title() { return PAGES[this.page][0]; }
    get description() { return PAGES[this.page][1]; }
    get rows() { return this.d.rows; }
    get todayRows() { return this.rows.filter(row => row.date === this.d.today); }
    get dayRows() { return this.rows.filter(row => row.day === this.state.day); }
    get alternateClasses() {
        return [...new Set(this.d.sessions.filter(row => row.date === this.state.alternateDate).map(row => row.class))];
    }
    get alternateHours() {
        return this.d.sessions.filter(row => row.date === this.state.alternateDate && row.class === this.state.alternateClass);
    }
    get taskRows() {
        return this.rows.filter(row => this.state.filter === "All" || row.done === (this.state.filter === "Completed"));
    }
    get lessonAllocation() { return this.d.allocations.find(row => row.id === Number(this.state.allocation)); }
    get lessonRows() {
        const allocation = this.lessonAllocation;
        return allocation ? this.rows.filter(row => row.subject_id === allocation.subject_id && row.class_id === allocation.class_id) : [];
    }
    get lessonProgress() {
        return this.lessonRows.length ? Math.round(this.lessonRows.filter(row => row.done).length * 100 / this.lessonRows.length) : 0;
    }
    get circularCategories() { return ["All", "Unread", ...new Set(["Academic", "Mentorship", "General", ...this.rows.map(row => row.category)])]; }
    get circularRows() {
        return this.rows.filter(row => this.state.filter === "All" || (this.state.filter === "Unread" && !row.read) || row.category === this.state.filter);
    }
    get circular() { return this.rows.find(row => row.id === this.state.selected) || this.rows[0]; }
    get assessmentSubjects() {
        return [...new Map(this.rows.map(row => [row.subject_id, row])).values()];
    }
    get assessments() { return this.rows.filter(row => row.subject_id === Number(this.state.subjectId)); }
    get marksOpen() { return ["draft", "entry"].includes(this.state.register?.status); }
    get enteredMarks() {
        return (this.state.register?.rows || []).filter(row => (this.state.values[row.id] ?? "") !== "").length;
    }
    get dailyRows() {
        const query = this.state.search.trim().toLowerCase();
        return this.rows.filter(row => (!query || (row.name + " " + row.roll).toLowerCase().includes(query))
            && (this.state.filter === "All" || row.status === this.state.filter));
    }
    get dailyCounts() {
        return Object.fromEntries(Object.keys(MARKS).map(key => [key, this.rows.filter(row => row.status === key).length]));
    }
    get dailyEditable() { return !this.d.locked && !this.state.busy && !!this.rows.length; }
    get confirmed() { return this.rows.filter(row => ["approved", "done"].includes(row.state)); }
    get pending() { return this.rows.filter(row => row.state === "submitted" && row.consent !== "declined"); }
    get kpis() {
        const rows = this.rows;
        switch (this.page) {
            case "timetable":
                return [["Weekly Teaching Hours", rows.length, "Assigned subject periods", "clock"],
                    ["Today’s Classes", this.todayRows.length, this.date(this.d.today), "calendar"],
                    ["Teaching Subjects", new Set(rows.map(row => row.subject)).size, "Across assigned classes", "book"],
                    ["Alternate Hours", this.d.coverage.length, "Confirmed upcoming coverage", "refresh"]];
            case "attendance": {
                const counts = this.dailyCounts;
                return [["Total Students", rows.length, "Assigned class roster", "users"],
                    ["Present", counts.present + counts.late, "Includes late arrivals", "check"],
                    ["Absent", counts.absent, "Requires attendance review", "alert"],
                    ["Unmarked", counts.unmarked, "Complete before submission", "clipboard"]];
            }
            case "tasks":
                return [["Pending Tasks", rows.filter(row => !row.done).length, "Still to be completed", "clipboard"],
                    ["Due Today", rows.filter(row => !row.done && row.date === this.d.today).length, "Tasks requiring attention", "clock"],
                    ["Completed Tasks", rows.filter(row => row.done).length, "Saved task history", "check"],
                    ["Overdue Tasks", rows.filter(row => !row.done && row.date < this.d.today).length, "Past due and open", "alert"]];
            case "exams":
                return [["Assigned Courses", this.assessmentSubjects.length, "Subjects with mark responsibilities", "book"],
                    ["Marks Entered", this.enteredMarks, "In the selected assessment", "check"],
                    ["Awaiting Entry", (this.state.register?.rows.length || 0) - this.enteredMarks, "Students with missing marks", "alert"],
                    ["Upcoming Exams", rows.filter(row => row.date >= this.d.today).length, "Assigned assessments", "calendar"]];
            case "assignments":
                return [["Total Assignments", rows.length, "Created for assigned subjects", "file"],
                    ["Open Assignments", rows.filter(row => row.status === "publish").length, "Accepting submissions", "clipboard"],
                    ["Submitted Work", rows.reduce((total, row) => total + row.submitted, 0), "Across all assignments", "check"],
                    ["Awaiting Review", rows.reduce((total, row) => total + row.waiting, 0), "Submitted work awaiting a grade", "clock"]];
            case "alternate":
                return [["Upcoming Alternates", rows.filter(row => row.date >= this.d.today).length, "Assigned or requested", "refresh"],
                    ["Confirmed", this.confirmed.length, "Approved coverage", "check"],
                    ["Pending Approval", this.pending.length, "Awaiting consent or approval", "clock"],
                    ["Uncovered Hours", this.pending.length, "Requested hours awaiting coverage", "shield"]];
            case "lessons": {
                const complete = this.lessonRows.filter(row => row.done).length;
                return [["Planned Topics", this.lessonRows.length, "Current subject", "book"],
                    ["Topics Completed", complete, "Marked as delivered", "check"],
                    ["Syllabus Progress", this.lessonProgress + "%", "Based on recorded topics", "trend"],
                    ["Upcoming Topics", this.lessonRows.length - complete, "Still to be taught", "calendar"]];
            }
            case "circulars":
                return [["All Circulars", rows.length, "Published for your faculty account", "file"],
                    ["Unread", rows.filter(row => !row.read).length, "Require faculty attention", "bell"],
                    ["Pinned", rows.filter(row => row.pinned).length, "Priority announcements", "alert"],
                    ["Acknowledged", rows.filter(row => row.read).length, "Marked as read", "check"]];
        }
        return [];
    }

    date(value) {
        return value ? new Intl.DateTimeFormat("en-IN", {day: "2-digit", month: "short", year: "numeric"})
            .format(new Date(value + "T12:00:00")) : "—";
    }
    attendanceStatus(value) { return MARKS[value]; }
    assessmentStatus(value) { return ASSESSMENT[value]; }
    assignmentStatus(value) { return ASSIGNMENT[value]; }
    alternateStatus(row) {
        if (["approved", "done"].includes(row.state)) return "Confirmed";
        if (row.state === "cancelled") return "Cancelled";
        if (row.consent === "declined") return "Declined";
        if (row.state === "draft") return "Draft";
        return row.consent === "accepted" ? "Awaiting approval" : "Pending consent";
    }
    rpc(method, args) { return this.orm.call("campus.faculty.task.list", method, args); }
    error(error) { return error.data?.message || error.message || "Please retry."; }
    unsaved() {
        this.notification.add("Save or clear the unsaved entries before changing records.", {type: "warning"});
        return false;
    }

    async load(initial = false, daily = {}) {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = this.page === "attendance" ?
                await this.rpc("get_sop_daily", [daily.classKey ?? (this.state.classKey || false),
                    daily.date ?? (this.state.date || false), daily.period ?? this.state.period]) :
                await this.rpc("get_sop_page", [this.page]);
            this.state.data = data;
            if (this.page === "attendance") {
                Object.assign(this.state, {classKey: data.class_key, date: data.date, period: data.period});
            }
            if (initial) {
                this.state.day = (new Date(data.today + "T12:00:00").getDay() + 6) % 7;
                this.state.diaryDate = data.today;
                this.state.allocation = String(data.allocations?.[0]?.id || "");
                this.state.alternateDate = data.sessions?.[0]?.date || data.today;
                this.selectAlternate();
                this.state.form = {date: data.today, maximum: 20, week: 14, type: String(data.types?.[0]?.id || "")};
            } else if (this.page === "alternate" && !data.sessions.some(row => row.id === Number(this.state.alternateSession))) {
                this.state.alternateDate = data.sessions[0]?.date || data.today;
                this.selectAlternate();
            }
            if (this.page === "exams") {
                this.state.subjectId ||= String(this.assessmentSubjects[0]?.subject_id || "");
                await this.loadMarks(this.state.examId || this.assessments[0]?.id || "");
            }
            this.state.dirty = false;
        } catch (error) {
            this.state.error = this.error(error);
        } finally {
            this.state.loading = false;
        }
    }
    async loadMarks(id) {
        const register = id ? await this.rpc("get_sop_marks", [Number(id)]) : null;
        Object.assign(this.state, {examId: String(id), register,
            values: Object.fromEntries((register?.rows || []).map(row => [row.id, row.marks ?? ""]))});
    }
    async chooseMarks(event, subject) {
        const previous = subject ? this.state.subjectId : this.state.examId;
        if (this.state.dirty || this.state.busy) { event.target.value = previous; return this.unsaved(); }
        const value = event.target.value;
        this.state.busy = true;
        try {
            if (subject) {
                this.state.subjectId = value;
                await this.loadMarks(this.assessments[0]?.id || "");
            } else {
                await this.loadMarks(value);
            }
        } catch (error) {
            if (subject) this.state.subjectId = previous;
            event.target.value = previous;
            this.notification.add(this.error(error), {type: "danger"});
        } finally { this.state.busy = false; }
    }
    async chooseDaily(event, field) {
        if (this.state.dirty || this.state.loading || this.state.busy) {
            event.target.value = this.state[field];
            return this.unsaved();
        }
        await this.load(false, {[field]: event.target.value});
        event.target.value = this.state[field];
    }
    selectAlternate() {
        const classes = this.d.sessions?.filter(row => row.date === this.state.alternateDate) || [];
        this.state.alternateClass = classes[0]?.class || "";
        this.state.alternateSession = String(classes[0]?.id || "");
    }
    changeAlternateClass() { this.state.alternateSession = String(this.alternateHours[0]?.id || ""); }

    async run(method, args, message, after) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            await this.rpc(method, args);
            this.state.dirty = false;
            after?.();
            await this.load();
            this.notification.add(message, {type: "success"});
        } catch (error) {
            this.notification.add(this.error(error), {type: "danger"});
        } finally { this.state.busy = false; }
    }
    mark(row, status) {
        if (!this.dailyEditable || row.protected) return;
        row.status = status;
        this.state.dirty = true;
    }
    markAll() { for (const row of this.rows) this.mark(row, "present"); }
    dailyRemark(row, event) {
        if (!this.dailyEditable || row.protected) return;
        row.remark = event.target.value;
        this.state.dirty = true;
    }
    saveDaily(submit) {
        const values = Object.fromEntries(this.rows.map(row => [row.id, {status: row.status, remark: row.remark}]));
        return this.run("save_sop_daily", [this.state.classKey, this.state.date, this.state.period, values, submit],
            submit ? "Daily attendance submitted." : "Daily attendance draft saved.", () => this.close());
    }
    enterMark(row, event) {
        this.state.values[row.id] = event.target.value;
        this.state.dirty = true;
    }
    saveMarks(submit) {
        const values = Object.fromEntries(this.state.register.rows
            .filter(row => this.state.values[row.id] !== "" || row.marks !== null)
            .map(row => {
                const value = this.state.values[row.id];
                return [row.id, value === "" ? null : Number(value)];
            }));
        return this.run("save_sop_marks", [Number(this.state.examId), values, submit],
            submit ? "Marks submitted for approval." : "Marks draft saved.", () => this.close());
    }
    newTask() {
        this.state.form = {title: "", area: "", date: this.d.today, priority: "0"};
        this.open("task", "Add Faculty Task");
    }
    saveTask() {
        const {title, area, date, priority} = this.state.form;
        return this.run("save_sop_task", [title, area, date, priority], "Task added.", () => this.close());
    }
    toggleTask(row) { return this.run("toggle_sop_task", [row.id, !row.done], row.done ? "Task reopened." : "Task completed."); }
    saveDiary() {
        return this.run("save_sop_diary", [this.state.diaryDate, this.state.diary], "Diary entry saved.",
            () => { this.state.diary = ""; });
    }
    saveAssignment() {
        const {title, date, maximum, type} = this.state.form;
        return this.run("save_sop_assignment", [Number(this.state.allocation), title, date, Number(maximum), Number(type)],
            "Assignment published to the class.", () => { this.state.form.title = ""; });
    }
    async review(row) {
        try {
            const students = await this.rpc("get_sop_submissions", [row.id]);
            this.open("review", "Review Assignment", {row, students});
        } catch (error) { this.notification.add(this.error(error), {type: "danger"}); }
    }
    grade(student) {
        const row = this.state.modal.row;
        this.state.gradeForm = {marks: student.marks ?? "", feedback: student.feedback};
        this.open("grade", "Grade Assignment Submission", {row, student});
    }
    saveGrade() {
        const {student} = this.state.modal;
        return this.run("save_sop_review", [student.submission, Number(this.state.gradeForm.marks), this.state.gradeForm.feedback],
            "Grade and feedback released.", () => this.close());
    }
    saveAlternate() {
        return this.run("save_sop_alternate", [Number(this.state.alternateSession), Number(this.state.replacement), this.state.reason],
            "Alternate request submitted for confirmation.", () => { this.state.reason = ""; });
    }
    replyAlternate(answer) {
        return this.run("reply_sop_alternate", [this.state.modal.row.id, answer], "Substitute response saved.", () => this.close());
    }
    saveLesson() {
        const {title, week, date, outcome} = this.state.form;
        return this.run("save_sop_lesson", [Number(this.state.allocation), title, Number(week), date, outcome],
            "Lesson topic added.", () => { this.state.form.title = ""; this.state.form.outcome = ""; });
    }
    toggleLesson(row) { return this.run("toggle_sop_lesson", [row.id, !row.done], row.done ? "Topic reopened." : "Topic marked complete."); }
    acknowledge() { return this.run("acknowledge_sop_circular", [this.circular.id], "Circular acknowledged."); }
    async performance(student) {
        try {
            const data = await this.rpc("get_mentor_data", [this.state.classKey]);
            const row = data.students.find(item => item.id === student.id);
            if (row) this.open("performance", "Student Performance", {row});
        } catch (error) { this.notification.add(this.error(error), {type: "danger"}); }
    }
    openTeaching(row) {
        return this.action.doAction("ideastone_erp.action_my_teaching_subjects", {additionalContext: {
            sop_session_id: row.id, sop_term_id: row.term_id, sop_date: row.date, sop_subject_key: row.subject_key,
        }});
    }
    goAlternate() { return this.action.doAction("ideastone_erp.action_faculty_sop_alternate"); }
    goMentorship() { return this.action.doAction("ideastone_erp.action_my_mentorship_class"); }
    open(kind, title, props = {}) {
        if (!this.state.modal) this.lastFocus = document.activeElement;
        this.state.modal = {kind, title, ...props};
    }
    close() { this.state.modal = null; this.lastFocus?.focus(); }
    modalKey(event) {
        if (event.key === "Escape") { event.stopPropagation(); this.close(); }
        if (event.key !== "Tab") return;
        const controls = [...this.drawer.el.querySelectorAll("button:not(:disabled),input:not(:disabled),select,textarea,a[href]")];
        const first = controls[0];
        const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    csv(kind) {
        const tables = {
            daily: () => [["Date", "Session", "Present", "Late", "Absent", "Approved OD / Leave"],
                ...this.d.history.map(row => [row.date, row.period, row.present + row.late, row.late, row.absent, row.excused])],
            marks: () => [["Roll No.", "Student", "Previous marks", "Selected assessment"],
                ...this.state.register.rows.map(row => [row.roll, row.name, row.previous, row.marks])],
            assignments: () => [["Assignment", "Subject", "Class", "Due", "Submitted", "Enrolled", "Maximum Marks", "Status"],
                ...this.rows.map(row => [row.title, row.subject, row.class, row.date, row.submitted, row.students, row.maximum, this.assignmentStatus(row.status)])],
        };
        const quote = value => '"' + String(value ?? "").replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"';
        const content = tables[kind]().map(row => row.map(quote).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob(["\ufeff" + content], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "faculty-" + kind + ".csv";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
}

registry.category("actions").add("ideastone_erp.faculty_sop", FacultySop);
