/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const FACTOR_LABELS = { attendance: "Attendance", academics: "Results", fees: "Fees", engagement: "Engagement" };
const BAND_LABELS = { high: "Needs attention", watch: "Watch", low: "On track" };

export class SuccessRadarPage extends Component {
    static template = "ideastone_ai.SuccessRadarPage";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: "", data: null, departmentId: "", batchId: "", band: "", query: "", open: null });
        this.factorLabels = FACTOR_LABELS;
        this.bandLabels = BAND_LABELS;
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.success.radar", "get_workspace", [{
                department_id: this.state.departmentId, batch_id: this.state.batchId, band: this.state.band, query: this.state.query,
            }]);
        } catch (error) {
            this.state.error = error.data?.message || "The Student Success Radar could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get batches() {
        return (this.state.data?.batches || []).filter((batch) => !this.state.departmentId || String(batch.department_id) === this.state.departmentId);
    }
    get roleLabel() {
        return { owner: "College workspace", hod: "Department HOD", mentor: "Mentor" }[this.state.data?.role] || "";
    }
    isSelected(id, value) { return String(id) === String(value); }
    factorLabel(key) { return FACTOR_LABELS[key] || key; }
    bandLabel(key) { return BAND_LABELS[key] || key; }
    percent(count) {
        const total = this.state.data?.summary?.students || 0;
        return total ? Math.round((count * 100) / total) : 0;
    }

    changeDepartment(event) { this.state.departmentId = event.target.value; this.state.batchId = ""; this.load(); }
    changeBatch(event) { this.state.batchId = event.target.value; this.load(); }
    changeBand(event) { this.state.band = event.target.value; this.load(); }
    search(event) { event.preventDefault(); this.load(); }
    updateQuery(event) { this.state.query = event.target.value; }
    toggle(id) { this.state.open = this.state.open === id ? null : id; }

    async counsel(row) {
        try {
            await this.action.doAction(await this.orm.call("campus.success.radar", "get_counseling_action", [row.id]), { onClose: () => this.load() });
        } catch (error) {
            this.notification.add(error.data?.message || "Counselling could not be opened.", { type: "danger" });
        }
    }
    async openStudent(row) {
        await this.action.doAction({ type: "ir.actions.act_window", res_model: "op.student", res_id: row.id, views: [[false, "form"]], target: "current" });
    }
    exportCsv() {
        const rows = [["Student", "Number", "Programme", "Class", "Semester", "Mentor", "Score", "Band", "Attendance %", "Results %", "Overdue fees", "Top factor", "Suggested action"],
            ...(this.state.data?.rows || []).map((row) => [row.name, row.number, row.programme, row.batch, row.semester, row.mentor, row.score,
                BAND_LABELS[row.band], row.attendance.rate ?? "", row.academics.average ?? "", row.fees.overdue,
                row.factors[0] ? FACTOR_LABELS[row.factors[0].key] : "", row.action])];
        const csv = "﻿" + rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = "student-success-radar.csv";
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_ai.success_radar", SuccessRadarPage);
