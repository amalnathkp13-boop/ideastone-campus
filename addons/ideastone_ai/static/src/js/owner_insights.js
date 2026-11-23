/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class OwnerInsights extends Component {
    static template = "ideastone_ai.OwnerInsights";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.requestId = 0;
        this.state = useState({ data: null, loading: true, error: "", departmentId: "" });
        onWillStart(() => this.load());
    }

    async load() {
        const requestId = ++this.requestId;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.owner.ai.insights", "get_overview", [
                this.state.departmentId ? Number(this.state.departmentId) : null,
            ]);
            if (requestId === this.requestId) this.state.data = data;
        } catch (error) {
            if (requestId === this.requestId) this.state.error = error.data?.message || "Insights could not be loaded. Please try again.";
        } finally {
            if (requestId === this.requestId) this.state.loading = false;
        }
    }

    get data() { return this.state.data; }
    get summary() { return this.data.summary; }
    get metrics() {
        const s = this.summary;
        return [
            { label: "Students reviewed", value: this.number(s.students), detail: "Active students in the selected scope", icon: "graduation-cap", tone: "blue" },
            { label: "Priority follow-ups", value: this.number(s.attention), detail: `${this.number(s.high)} need attention · ${this.number(s.watch)} on watch`, icon: "flag-o", tone: "red" },
            { label: "Attendance below threshold", value: this.number(s.attendance_below), detail: `Recorded attendance below ${this.data.threshold}%`, icon: "calendar-check-o", tone: "amber" },
            { label: "Overdue student fees", value: this.money(s.overdue_amount), detail: `${this.number(s.overdue_students)} students with overdue invoices`, icon: "inr", tone: "purple" },
        ];
    }
    number(value) { return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value || 0); }
    money(value) { return "₹ " + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value || 0); }
    get updatedAt() {
        return new Date(this.data.updated_at.replace(" ", "T") + "Z").toLocaleString("en-IN", {
            dateStyle: "medium", timeStyle: "short",
        });
    }
    percentage(value, total) { return total ? Math.min(100, Math.round(value * 100 / total)) : 0; }
    changeDepartment(event) { this.state.departmentId = event.target.value; return this.load(); }

    async openAction(action, options = {}) {
        try { await this.action.doAction(action, options); }
        catch (error) { this.notification.add(error.data?.message || "This workspace could not be opened. Please try again.", { type: "danger" }); }
    }
    radar(departmentId = this.state.departmentId, band = "") {
        return this.openAction("ideastone_ai.action_success_radar", {
            additionalContext: { campus_module: "ai", department_id: departmentId || "", band },
        });
    }
    assistant() { return this.openAction("ideastone_ai.action_assistant", { additionalContext: { campus_module: "ai" } }); }
    async student(id) {
        try {
            const action = await this.orm.call("campus.students.ui", "get_record_action", ["student", id]);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || "This student record could not be opened.", { type: "danger" });
        }
    }
}

registry.category("actions").add("ideastone_ai.owner_insights", OwnerInsights);
