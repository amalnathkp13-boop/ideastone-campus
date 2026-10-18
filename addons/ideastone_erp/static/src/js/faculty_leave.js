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
        this.state = useState({
            loading: true, saving: false, error: "", data: null, tab: "process",
            form: emptyForm(), showAll: false, modal: "", selected: null,
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
    }

    changeDuration(event) {
        this.state.form.duration = event.target.value;
        if (event.target.value === "one") this.state.form.toDate = this.state.form.fromDate;
    }

    changeFromDate(event) {
        this.state.form.fromDate = event.target.value;
        if (this.state.form.duration === "one") this.state.form.toDate = event.target.value;
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
        this.state.saving = true;
        try {
            await this.orm.call("campus.faculty.leave.ui", "submit_leave", [{
                leave_type_id: Number(form.leaveTypeId),
                date_from: form.fromDate,
                date_to: form.toDate,
                from_session: form.fromSession,
                to_session: form.toSession,
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
    }

    stopModalClick() {}

    printHistory() {
        window.print();
    }
}

registry.category("actions").add("ideastone_erp.faculty_leave_page", FacultyLeavePage);
