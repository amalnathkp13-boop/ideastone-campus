/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class FacultyAttendancePage extends Component {
    static template = "ideastone_erp.FacultyAttendancePage";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        const now = new Date();
        this.state = useState({loading: true, error: "", data: null, month: now.getMonth() + 1,
            year: now.getFullYear(), employeeId: "", departmentId: "", chart: "weekly"});
        this.months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("campus.faculty.attendance.ui", "get_dashboard",
                [this.state.employeeId || false, this.state.year, this.state.month]);
            this.state.data = data;
            this.state.employeeId = String(data.employee_id || "");
            const selected = data.staff.find((item) => item.id === data.employee_id);
            this.state.departmentId = String(selected?.department_id || "");
        } catch (error) {
            this.state.error = error.data?.message || "Attendance could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }

    get visibleStaff() {
        return (this.state.data?.staff || []).filter((item) => !this.state.departmentId ||
            String(item.department_id) === this.state.departmentId);
    }

    async changeDepartment(event) {
        const departmentId = event.target.value;
        this.state.departmentId = departmentId;
        const first = this.visibleStaff[0];
        this.state.employeeId = String(first?.id || "");
        await this.load();
        this.state.departmentId = departmentId;
    }

    async changeEmployee(event) { this.state.employeeId = event.target.value; await this.load(); }
    async changeMonth(event) { this.state.month = Number(event.target.value); await this.load(); }
    async changeYear(event) { this.state.year = Number(event.target.value); await this.load(); }
    setChart(chart) { this.state.chart = chart; }

    get chartBars() {
        const rows = this.state.data?.trend || [];
        if (this.state.chart === "weekly") return rows;
        const rate = this.state.data?.metrics.rate;
        return [{label: this.state.data?.month_name || "Month", rate: rate ?? 0}];
    }

    get years() {
        return [this.state.year - 1, this.state.year, this.state.year + 1];
    }

    statusClass(status) {
        if (status === "Present") return "present";
        if (status === "Absent") return "absent";
        return "neutral";
    }

    exportCsv() {
        const data = this.state.data;
        if (!data) return;
        const staff = data.staff.find((item) => item.id === data.employee_id);
        const rows = [["Staff", staff?.name || ""], ["Month", `${data.month_name} ${data.year}`],
            ["Date", "Day", "Status", "Check-in", "Check-out", "Late Mark"],
            ...data.attendance.map((row) => [row.date, row.day, row.status, row.check_in, row.check_out, row.late])];
        const csv = "\ufeff" + rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        link.download = `staff-attendance-${data.year}-${String(data.month).padStart(2, "0")}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    }
}

registry.category("actions").add("ideastone_erp.faculty_attendance_page", FacultyAttendancePage);
