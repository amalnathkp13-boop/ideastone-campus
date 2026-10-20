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
        this.state = useState({loading: true, error: "", records: [], mode: "history", year: "all", month: "all"});
        this.months = MONTHS;
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.records = await this.orm.searchRead("campus.payslip", [
                ["employee_id.user_id", "=", this.user.userId],
                ["state", "in", ["approved", "done"]],
            ], ["name", "date_from", "date_to", "net", "pf", "tds", "state"], {order: "date_from desc, id desc"});
        } catch (error) {
            this.state.error = error.data?.message || "Payroll history could not be loaded. Check your access and try again.";
        } finally {
            this.state.loading = false;
        }
    }

    get latest() { return this.state.records[0]; }
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
        if (latest === prior) return `Your latest net salary has stayed at ${amount(latest)}.`;
        return `Your latest net salary is ${amount(Math.abs(latest - prior))} ${latest > prior ? "higher" : "lower"} than the previous payslip.`;
    }
    get taxInsight() {
        return this.yearTds ? `${amount(this.yearTds)} in TDS appears on your ${this.selectedYear} payslips.` :
            `No TDS is recorded on your ${this.selectedYear} payslips.`;
    }
    get statusInsight() {
        return this.latest ? `${this.state.records.length} approved or completed payslips are available. Latest: ${this.latestLabel}.` :
            "Approved payslips will appear here once payroll is processed.";
    }
    formatMoney(value) { return amount(value); }
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
    }
    changeYear(event) { this.state.year = event.target.value; }
    changeMonth(event) { this.state.month = event.target.value; }

    exportCsv() {
        const rows = [["Month", "Year", "Net Salary (INR)", "PF (INR)", "TDS (INR)", "Status"],
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
