/** @odoo-module **/
// Campus home: one tile per module. Everything the office uses, on one screen.
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const TILES = [
    { key: "admissions", label: "Admissions", help: "Applications, counselling, offers", icon: "fa-user-plus", color: "#1fa587", action: "openeducat_admission.act_open_op_admission_view" },
    { key: "students", label: "Students", help: "Records, documents, guardians", icon: "fa-graduation-cap", color: "#0ea5e9", action: "openeducat_core.act_open_op_student_view" },
    { key: "faculty", label: "Faculty", help: "Staff, subjects, workload", icon: "fa-users", color: "#8b5cf6", action: "openeducat_core.act_open_op_faculty_view" },
    { key: "fees", label: "Fees", help: "Fee terms, invoices, receipts", icon: "fa-inr", color: "#f59e0b", action: "openeducat_fees.act_open_fees_terms_view" },
    { key: "attendance", label: "Attendance", help: "Daily sheets and reports", icon: "fa-check-square-o", color: "#10b981", action: "openeducat_attendance.act_open_op_attendance_sheet_view" },
    { key: "exams", label: "Exams", help: "Sessions, marks, results", icon: "fa-file-text-o", color: "#ef4444", action: "openeducat_exam.act_open_op_exam_view" },
    { key: "timetable", label: "Timetable", help: "Sessions by class and faculty", icon: "fa-calendar", color: "#6366f1", action: "openeducat_timetable.act_open_op_session_view" },
    { key: "library", label: "Library", help: "Catalogue, issue, return", icon: "fa-book", color: "#64748b", action: "openeducat_library.act_open_op_media_view" },
    { key: "lms", label: "Learning (LMS)", help: "Courses, content, online tests", icon: "fa-laptop", color: "#14856e", action: "ideastone_lms.action_lms_frame" },
];

export class CampusHome extends Component {
    static template = "ideastone_lms.CampusHome";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.user = useService("user");
        this.state = useState({ stats: {}, company: "" });
        onWillStart(async () => {
            const [students, faculty, courses] = await Promise.all([
                this.orm.searchCount("op.student", [["active", "=", true]]),
                this.orm.searchCount("op.faculty", [["active", "=", true]]),
                this.orm.searchCount("op.course", []),
            ]);
            this.state.stats = { students, faculty, courses };
            const c = await this.orm.read("res.company", [this.user.context.allowed_company_ids[0]], ["name"]);
            this.state.company = c.length ? c[0].name : "";
        });
    }

    get tiles() {
        return TILES;
    }

    async open(tile) {
        try {
            await this.action.doAction(tile.action);
        } catch (e) {
            // module providing this action may not be installed
            console.warn("Campus home: action not available", tile.action, e);
        }
    }
}

registry.category("actions").add("ideastone_lms.campus_home", CampusHome);
