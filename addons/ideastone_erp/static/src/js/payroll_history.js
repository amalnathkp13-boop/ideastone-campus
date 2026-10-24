/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const money = new Intl.NumberFormat("en-IN", {maximumFractionDigits: 0});
const amount = (value) => `₹ ${money.format(Number(value) || 0)}`;
const periodDate = (row) => new Date(`${row.date_from}T00:00:00`);

export class PayrollHistoryPage extends Component {
    static template = "ideastone_erp.PayrollHistoryPage";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        this.state = useState({loading: true, error: "", records: [], mode: "history", year: "all", month: "all",
            isAdmin: false, staff: [], employeeId: "", employeeName: "", entries: [], entryError: "",
            currencySymbol: "₹", currencyCode: "INR", currencyPosition: "before"});
        this.months = MONTHS;
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.isAdmin = await this.user.hasGroup("ideastone_erp.group_manager");
            if (this.state.isAdmin) {
                const data = await this.orm.call("campus.payslip", "get_history_data", [this.state.employeeId || false]);
                this.state.records = data.records;
                this.state.staff = data.staff;
                this.state.employeeId = String(data.employee_id || "");
                this.state.employeeName = data.employee_name;
                this.state.currencySymbol = data.currency_symbol;
                this.state.currencyCode = data.currency_code;
                this.state.currencyPosition = data.currency_position;
                await this.loadEntries();
            } else {
                this.state.records = await this.orm.searchRead("campus.payslip", [
                    ["employee_id.user_id", "=", this.user.userId],
                    ["state", "in", ["approved", "done"]],
                ], ["name", "date_from", "date_to", "net", "pf", "tds", "state"], {order: "date_from desc, id desc"});
            }
        } catch (error) {
            this.state.error = error.data?.message || "Payroll history could not be loaded. Check your access and try again.";
        } finally {
            this.state.loading = false;
        }
    }

    async loadEntries() {
        this.state.entries = [];
        this.state.entryError = "";
        if (!this.state.isAdmin || !this.latest || !this.state.employeeId) return;
        const slip = this.latest;
        const employeeId = Number(this.state.employeeId);
        try {
            const entries = await this.orm.call("campus.payslip", "get_punch_entries",
                [employeeId, slip.date_from, slip.date_to]);
            if (Number(this.state.employeeId) === employeeId && this.latest?.id === slip.id) {
                this.state.entries = entries;
            }
        } catch (error) {
            if (Number(this.state.employeeId) === employeeId && this.latest?.id === slip.id) {
                this.state.entryError = error.data?.message || "Punch details could not be loaded.";
            }
        }
    }

    get latest() { return this.state.isAdmin ? this.visibleRows[0] : this.state.records[0]; }
    get years() { return [...new Set(this.state.records.map((row) => periodDate(row).getFullYear()))].sort((a, b) => b - a); }
    get selectedYear() { return this.state.year === "all" ? new Date().getFullYear() : Number(this.state.year); }
    get yearRows() { return this.state.records.filter((row) => periodDate(row).getFullYear() === this.selectedYear); }
    get visibleRows() {
        return this.state.records.filter((row) => {
            const date = periodDate(row);
            return (this.state.year === "all" || date.getFullYear() === Number(this.state.year)) &&
                (this.state.month === "all" || date.getMonth() + 1 === Number(this.state.month));
        });
    }
    get latestLabel() { return this.latest ? `${MONTHS[periodDate(this.latest).getMonth()]} ${periodDate(this.latest).getFullYear()}` : "No payslips yet"; }
    get coverage() {
        if (!this.latest) return "No payroll periods available";
        const first = this.state.records[this.state.records.length - 1];
        return `From ${MONTHS[periodDate(first).getMonth()].slice(0, 3)} ${periodDate(first).getFullYear()} to ${MONTHS[periodDate(this.latest).getMonth()].slice(0, 3)} ${periodDate(this.latest).getFullYear()}`;
    }
    get yearPf() { return this.yearRows.reduce((sum, row) => sum + Number(row.pf || 0), 0); }
    get yearTds() { return this.yearRows.reduce((sum, row) => sum + Number(row.tds || 0), 0); }
    get trend() {
        const rows = this.state.records.slice(0, 12).reverse();
        const highest = Math.max(1, ...rows.map((row) => Number(row.net || 0)));
        const chartMaximum = Math.ceil(highest / 10000) * 10000;
        return rows.map((row) => ({
            id: row.id, value: Number(row.net || 0), label: MONTHS[periodDate(row).getMonth()].slice(0, 3),
            year: periodDate(row).getFullYear(),
            height: Number(row.net || 0) > 0 ? Math.max(5, Math.round(Number(row.net) / chartMaximum * 100)) : 0,
        }));
    }
    get chartMax() {
        const highest = Math.max(1, ...this.trend.map((bar) => bar.value));
        return Math.ceil(highest / 10000) * 10000;
    }
    get trendInsight() {
        if (this.state.records.length < 2) return "Your salary trend will appear when at least two payslips are available.";
        const latest = Number(this.state.records[0].net || 0);
        const prior = Number(this.state.records[1].net || 0);
        if (latest === prior) return `Your latest net salary has stayed at ${this.formatMoney(latest)}.`;
        return `Your latest net salary is ${this.formatMoney(Math.abs(latest - prior))} ${latest > prior ? "higher" : "lower"} than the previous payslip.`;
    }
    get taxInsight() {
        return this.yearTds ? `${this.formatMoney(this.yearTds)} in TDS appears on your ${this.selectedYear} payslips.` :
            `No TDS is recorded on your ${this.selectedYear} payslips.`;
    }
    get statusInsight() {
        return this.latest ? `${this.state.records.length} approved or completed payslips are available. Latest: ${this.latestLabel}.` :
            "Approved payslips will appear here once payroll is processed.";
    }
    formatMoney(value) {
        if (!this.state.isAdmin) return amount(value);
        const number = money.format(Number(value) || 0);
        return this.state.currencyPosition === "after" ? `${number} ${this.state.currencySymbol}` :
            `${this.state.currencySymbol} ${number}`;
    }
    rowMonth(row) { return MONTHS[periodDate(row).getMonth()]; }
    rowYear(row) { return periodDate(row).getFullYear(); }

    changeMode(event) {
        this.state.mode = event.target.value;
        if (this.state.mode === "selected") {
            const date = this.latest ? periodDate(this.latest) : new Date();
            this.state.year = String(date.getFullYear());
            this.state.month = String(date.getMonth() + 1);
        } else {
            this.state.year = "all";
            this.state.month = "all";
        }
        if (this.state.isAdmin) this.loadEntries();
    }
    changeYear(event) { this.state.year = event.target.value; if (this.state.isAdmin) this.loadEntries(); }
    changeMonth(event) { this.state.month = event.target.value; if (this.state.isAdmin) this.loadEntries(); }
    async changeEmployee(event) {
        this.state.employeeId = event.target.value;
        this.state.year = "all";
        this.state.month = "all";
        this.state.mode = "history";
        await this.load();
    }

    exportCsv() {
        const rows = this.state.isAdmin ?
            [["Staff", "Month", "Year", `Net Salary (${this.state.currencyCode})`, "Late Days", "Paid Late Days",
                "Deducted Late Days", `Late Deduction (${this.state.currencyCode})`, "Deducted Dates", "Status"],
            ...this.visibleRows.map((row) => [this.state.employeeName, this.rowMonth(row), this.rowYear(row), row.net,
                row.late_days, row.late_grace_days, row.late_deducted_days, row.late_deduction,
                row.late_deduction_dates || "", row.state])] :
            [["Month", "Year", "Net Salary (INR)", "PF (INR)", "TDS (INR)", "Status"],
            ...this.visibleRows.map((row) => [this.rowMonth(row), this.rowYear(row), row.net, row.pf, row.tds, row.state])];
        const csv = "\ufeff" + rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "payroll-history.csv";
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.payroll_history_page", PayrollHistoryPage);
