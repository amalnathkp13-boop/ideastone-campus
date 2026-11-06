/** @odoo-module **/
import { Component, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const emptyForm = (today = "") => ({
    academicYear: "", leaveTypeId: "", duration: "one", fromDate: today,
    toDate: today, fromSession: "FN", toSession: "AN", reason: "",
});

export class FacultyLeavePage extends Component {
    static template = "ideastone_erp.FacultyLeavePage";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.coverageRequest = 0;
        this.state = useState({
            loading: true, saving: false, error: "", data: null, tab: "process",
            form: emptyForm(), showAll: false, modal: "", selected: null,
            coverage: null, editCoverage: null, loadingCoverage: false, coverageError: "",
        });
        onWillStart(() => this.load());
        useExternalListener(window, "keydown", (event) => {
            if (event.key === "Escape") this.closeModal();
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.faculty.leave.ui", "get_page_data", []);
            this.state.data = data;
            this.resetForm();
        } catch (error) {
            this.state.error = error.data?.message || "Leave requests could not be loaded. Check your access and try again.";
        } finally {
            this.state.loading = false;
        }
    }

    resetForm() {
        const data = this.state.data;
        this.state.form = emptyForm(data?.today || "");
        this.state.form.academicYear = data?.academic_years?.[0] || "";
        this.state.form.leaveTypeId = String(data?.leave_types?.[0]?.id || "");
        if (this.props.staffOnDuty || this.props.action?.context?.staff_on_duty) {
            const type = data?.leave_types?.find(item => item.staff_od);
            if (type) this.state.form.leaveTypeId = String(type.id);
        }
        this.state.coverage = null;
        if (data?.can_apply) this.loadCoverage();
    }

    changeDuration(event) {
        this.state.form.duration = event.target.value;
        if (event.target.value === "one") this.state.form.toDate = this.state.form.fromDate;
        this.loadCoverage();
    }

    changeFromDate(event) {
        this.state.form.fromDate = event.target.value;
        if (this.state.form.duration === "one") this.state.form.toDate = event.target.value;
        this.loadCoverage();
    }

    changeCoverageField(field, event) {
        this.state.form[field] = event.target.value;
        this.loadCoverage();
    }

    get requestValues() {
        const form = this.state.form;
        return {leave_type_id: Number(form.leaveTypeId), date_from: form.fromDate, date_to: form.toDate,
            from_session: form.fromSession, to_session: form.toSession};
    }

    get currentCoverage() {
        const coverage = this.state.coverage;
        return coverage?.key === JSON.stringify(this.requestValues) ? coverage : null;
    }

    async loadCoverage(record = null) {
        const request = ++this.coverageRequest;
        const values = this.requestValues;
        this.state.coverageError = "";
        if (!record && (!values.leave_type_id || !values.date_from || !values.date_to || values.date_to < values.date_from)) {
            this.state.loadingCoverage = false;
            return;
        }
        this.state.loadingCoverage = true;
        const previous = record ? null : this.state.coverage;
        try {
            const plan = await this.orm.call("campus.faculty.leave.ui", "get_coverage",
                record ? [null, record.id] : [values]);
            if (request !== this.coverageRequest || (record && this.state.selected?.id !== record.id)) return;
            for (const row of plan.rows) {
                row.savedFacultyId = row.faculty_id;
                row.faculty_id = String(row.faculty_id || "");
                const selected = previous?.rows.find(item => item.id === row.id)?.faculty_id;
                if (selected && row.options.some(item => item.id === Number(selected))) row.faculty_id = selected;
            }
            if (record) {
                this.state.editCoverage = plan;
                this.state.modal = "coverage";
            } else {
                this.state.coverage = {...plan, key: JSON.stringify(values)};
            }
        } catch (error) {
            if (request !== this.coverageRequest) return;
            const message = error.data?.message || "The teaching timetable could not be loaded.";
            if (record) this.notification.add(message, {type: "danger"});
            else this.state.coverageError = message;
        } finally {
            if (request === this.coverageRequest) this.state.loadingCoverage = false;
        }
    }

    coveragePayload(plan) {
        return plan.rows.filter(row => row.faculty_id).map(row => ({session_id: row.id, faculty_id: Number(row.faculty_id)}));
    }

    suggestCoverage(plan) {
        for (const row of plan.rows) {
            if (row.faculty_id) continue;
            const candidate = row.options.find(option => !plan.rows.some(other =>
                Number(other.faculty_id) === option.id && other.start < row.end && other.end > row.start));
            if (candidate) row.faculty_id = String(candidate.id);
        }
    }

    clearCoverage(plan) {
        for (const row of plan.rows) row.faculty_id = "";
    }

    async respondToCoverage(row, accept) {
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            await this.orm.call("campus.faculty.leave.ui", "respond_to_coverage", [row.leave_id, row.id, accept]);
            await this.load();
            this.notification.add(accept ? "Substitute duty accepted." : "Substitute duty declined.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || "Your response could not be saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    async saveCoverage() {
        const plan = this.state.editCoverage;
        if (this.state.saving || !plan) return;
        this.state.saving = true;
        try {
            await this.orm.call("campus.faculty.leave.ui", "save_coverage", [this.state.selected.id, this.coveragePayload(plan)]);
            this.closeModal();
            await this.load();
            this.notification.add("Teaching coverage saved.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || "Teaching coverage could not be saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    async submit(event) {
        event.preventDefault();
        if (this.state.saving || !this.state.data?.can_apply) return;
        const form = this.state.form;
        if (!form.leaveTypeId || !form.fromDate || !form.toDate || !form.reason.trim()) {
            this.notification.add("Choose a leave type and dates, then enter a reason.", { type: "warning" });
            return;
        }
        if (form.toDate < form.fromDate ||
            (form.duration === "one" && form.toDate !== form.fromDate)) {
            this.notification.add("The selected leave dates are not valid.", { type: "warning" });
            return;
        }
        const plan = this.currentCoverage;
        if (!plan || this.state.loadingCoverage) {
            this.notification.add("Check the timetable for the selected leave dates before submitting.", {type: "warning"});
            return;
        }
        this.state.saving = true;
        try {
            await this.orm.call("campus.faculty.leave.ui", "submit_leave", [{
                ...this.requestValues,
                coverage: this.coveragePayload(plan),
                reason: form.reason.trim(),
            }]);
            await this.load();
            this.notification.add("Leave request submitted for approval.", { type: "success" });
        } catch (error) {
            this.notification.add(error.data?.message || "The leave request could not be saved.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    get historyRows() {
        const rows = this.state.data?.history || [];
        return this.state.showAll ? rows : rows.slice(0, 5);
    }

    formatDate(value) {
        if (!value) return "—";
        const parts = value.split("-");
        return parts.length === 3 ? [parts[2], parts[1], parts[0]].join("/") : value;
    }

    dateLabel(record) {
        if (!record) return "—";
        if (record.date) return record.date;
        if (record.from !== record.to) return this.formatDate(record.from) + " – " + this.formatDate(record.to);
        return this.formatDate(record.from) + (record.days === 0.5 ? " (Half day)" : " (Full day)");
    }

    statusClass(status) {
        if (status === "Approved") return "approved";
        if (status === "Refused") return "refused";
        return "pending";
    }

    attendanceClass(value) {
        if (value === "Present") return "present";
        if (value === "OD") return "duty";
        if (value === "Leave Applied") return "leave";
        return "";
    }

    yearLabel(value) {
        return (value || "").replace("-", " – ");
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    toggleHistory() {
        this.state.showAll = !this.state.showAll;
    }

    openDetails(record) {
        this.state.selected = record;
        this.state.modal = "details";
    }

    openInsights() {
        this.state.modal = "insights";
    }

    closeModal() {
        this.state.modal = "";
        this.state.selected = null;
        this.state.editCoverage = null;
    }

    stopModalClick() {}

    printHistory() {
        window.print();
    }
}

registry.category("actions").add("ideastone_erp.faculty_leave_page", FacultyLeavePage);
