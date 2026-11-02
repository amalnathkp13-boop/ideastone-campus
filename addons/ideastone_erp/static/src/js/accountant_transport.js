/** @odoo-module **/
import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SCREENS = {
    overview: {tab: "Transport overview", title: "Transport overview", subtitle: "Monitor college transport usage, fleet operations and financial performance."},
    routes: {tab: "Routes & fleet", title: "Routes & fleet", subtitle: "College buses, route assignments, capacity and transport users."},
    revenue: {tab: "Revenue & expenses", title: "Revenue & expenses", subtitle: "Track transport income, running costs, maintenance allowance and net balance."},
    drivers: {tab: "Driver salaries", title: "Driver salary records", subtitle: "Manage monthly driver payroll, assigned buses and payment status."},
};
export class AccountantTransport extends Component {
    static template = "ideastone_erp.AccountantTransport";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.action = useService("action"); this.router = useService("router");
        this.workspaceRef = useRef("transportWorkspace");
        const hash = this.router.current.hash;
        this.state = useState({screen: SCREENS[hash.transport_view] ? hash.transport_view : "overview", query: "", status: "all",
            type: "all", month: "", year: hash.transport_year || "", data: {routes: [], transactions: [], payroll: [], years: [], expenses: {}}, busy: false, error: ""});
        onWillStart(() => this.load());
    }
    get screens() { return Object.entries(SCREENS).map(([key, config]) => ({key, ...config})); }
    get config() { return SCREENS[this.state.screen]; }
    get data() { return this.state.data; }
    get operational() { return this.data.routes.filter(r => r.status === "operational").length; }
    get maintenance() { return this.data.routes.filter(r => r.status === "maintenance").length; }
    get reserveFleet() { return this.data.routes.filter(r => r.status === "reserve").length; }
    get activeRoutes() { return this.data.routes.filter(r => r.status !== "reserve"); }
    get students() { return this.data.routes.reduce((sum, r) => sum + r.students, 0); }
    get staff() { return this.data.routes.reduce((sum, r) => sum + r.staff, 0); }
    get capacity() { return this.activeRoutes.reduce((sum, r) => sum + r.capacity, 0); }
    get expense() { return Object.values(this.data.expenses).reduce((sum, value) => sum + value, 0); }
    get net() { return this.data.revenue - this.expense; }
    get serviceDue() { return this.data.routes.filter(r => r.service_due && r.service_due.slice(0, 7) === this.data.today?.slice(0, 7)).length; }
    money(amount, compact = false) {
        const value = Number(amount) || 0, abs = Math.abs(value), indian = this.data.currency === "₹";
        const divisor = compact ? (indian ? (abs >= 1e7 ? 1e7 : abs >= 1e5 ? 1e5 : 1) : (abs >= 1e6 ? 1e6 : abs >= 1e3 ? 1e3 : 1)) : 1;
        const suffix = divisor === 1 ? "" : indian ? (divisor === 1e7 ? "Cr" : "L") : divisor === 1e6 ? "M" : "K";
        return (value < 0 ? "-" : "") + (this.data.currency || "") + new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2}).format(abs / divisor) + suffix;
    }
    number(value) { return new Intl.NumberFormat("en-IN", {maximumFractionDigits: 0}).format(value || 0); }
    date(value) { return new Intl.DateTimeFormat("en-GB", {day: "2-digit", month: "short", year: "numeric"}).format(new Date(value + "T12:00:00Z")); }
    monthLabel(value) { return value ? new Intl.DateTimeFormat("en-GB", {month: "long", year: "numeric"}).format(new Date(value + "-01T12:00:00Z")) : ""; }
    busCount(value) { return `${value} ${value === 1 ? "bus" : "buses"}`; }
    get cards() {
        const data = this.data, m = v => this.money(v, true), n = v => this.number(v);
        const drivers = new Set(this.activeRoutes.filter(r => r.driver).map(r => r.driver_code || r.driver)).size;
        const payroll = this.monthPayroll;
        if (this.state.screen === "routes") return [
            ["Total fleet", n(data.routes.length), `${this.activeRoutes.length} active · ${this.reserveFleet} reserve`, "▣", "blue"],
            ["Active routes", n(this.activeRoutes.length), "Daily campus service", "↗", "blue"],
            ["Total capacity", n(this.capacity), "Seats across active buses", "♙", "blue"],
            ["Occupancy", (this.capacity ? Math.round((this.students + this.staff) / this.capacity * 100) : 0) + "%", `${n(this.students + this.staff)} assigned riders`, "◉", "blue"],
        ];
        if (this.state.screen === "revenue") return [
            ["Transport revenue", m(data.revenue), "Collected in " + data.year, "₹", "blue"],
            ["Total expenses", m(this.expense), "Posted fuel, payroll, upkeep and permits", "↘", "rose"],
            ["Net operating balance", m(this.net), "Revenue minus recorded expenses", "✓", "green"],
            ["Maintenance reserve", m(data.reserve), "Budget allocated this year", "⚙", "amber"],
        ];
        if (this.state.screen === "drivers") return [
            ["Active drivers", n(drivers), "Assigned across college fleet", "♙", "blue"],
            ["Monthly payroll", m(payroll.filter(p => p.status !== "cancelled").reduce((sum, p) => sum + p.net, 0)), "Selected monthly total", "₹", "blue"],
            ["Paid this month", n(payroll.filter(p => p.status === "paid").length), "Driver salaries processed", "✓", "green"],
            ["Pending payments", n(payroll.filter(p => ["pending", "processing"].includes(p.status)).length), "Awaiting posting / processing", "◷", "amber"],
        ];
        return [
            ["Active buses", n(this.activeRoutes.length), `${this.operational} operational · ${this.maintenance} in maintenance`, "▣", "blue"],
            ["Student riders", n(this.students), `Across ${this.activeRoutes.length} active routes`, "♙", "green"],
            ["Staff riders", n(this.staff), "Faculty and campus staff", "♟", "violet"],
            ["Net transport balance", m(this.net), "Revenue less recorded expenses · " + data.year, "₹", "amber"],
        ];
    }
    get breakdown() {
        const categories = [["fuel", "Fuel", "#1769d2"], ["maintenance", "Maintenance", "#6840bf"],
            ["salary", "Driver salaries", "#08784c"], ["insurance", "Insurance & permits", "#d99a27"], ["other", "Other", "#627a96"]];
        const max = Math.max(1, ...Object.values(this.data.expenses));
        return categories.filter(([key]) => key !== "other" || this.data.expenses.other).map(([key, label, color]) => ({
            key, label, amount: this.data.expenses[key] || 0, style: `width:${(this.data.expenses[key] || 0) / max * 100}%;background:${color}`,
        }));
    }
    get months() { return [...new Set([this.data.today?.slice(0, 7), ...this.data.payroll.map(p => p.month)].filter(Boolean))].sort().reverse(); }
    get monthPayroll() { return this.data.payroll.filter(p => p.month === this.state.month); }
    get rows() {
        const query = this.state.query.trim().toLowerCase();
        const source = this.state.screen === "routes" ? this.data.routes : this.state.screen === "drivers" ? this.monthPayroll : this.data.transactions;
        return source.filter(row => (!query || Object.values(row).join(" ").toLowerCase().includes(query))
            && (this.state.status === "all" || row.status === this.state.status)
            && (this.state.type === "all" || (this.state.type === "revenue" ? row.kind === "receipt" : row.kind === "bill")));
    }
    get recent() { return this.data.transactions.slice(0, 5); }
    get tableTitle() { return {routes: "Fleet directory", revenue: "Transport transaction ledger", drivers: "Driver payroll"}[this.state.screen]; }
    get tableSubtitle() { return {routes: "Bus details, route, driver and assigned ridership", revenue: "Income and expense records by date and category", drivers: "Salary, allowances, deductions and take-home amount"}[this.state.screen]; }
    get columns() {
        return {routes: ["Bus / Reg. No.", "Route", "Driver", "Students", "Staff", "Capacity", "Status"],
            revenue: ["Date", "Reference", "Bus / Route", "Category", "Income", "Expense", "Net", "Status"],
            drivers: ["Employee ID", "Driver name", "Assigned bus", "Base salary", "Allowance", "Deductions", "Net salary", "Payment status"]}[this.state.screen] || [];
    }
    cells(row) {
        if (this.state.screen === "routes") return [row.registration, row.name, row.driver || "Unassigned", this.number(row.students), this.number(row.staff), this.number(row.capacity)];
        if (this.state.screen === "drivers") return [row.employee, row.driver, row.bus, this.money(row.base), this.money(row.allowance), this.money(row.deductions), this.money(row.net)];
        return [this.date(row.date), row.reference, row.route, row.category, row.income ? this.money(row.income) : "—", row.expense ? this.money(row.expense) : "—", this.money(row.income - row.expense)];
    }
    statusLabel(status) { return {operational: "Operational", maintenance: "Maintenance", reserve: "Inactive / reserve", paid: "Paid", pending: "Pending", processing: "Processing", cancelled: "Cancelled"}[status] || status; }
    tone(status) { return ["operational", "paid", "Paid", "Posted", "Recorded"].includes(status) ? "good" : ["Cancelled", "cancelled", "Reversed"].includes(status) ? "bad" : "warn"; }
    async load() {
        if (this.state.busy) return;
        this.state.busy = true; this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.dashboard", "get_transport_data", [this.state.year || false]);
            this.state.year = String(this.data.year_id || "");
            if (!this.state.month) this.state.month = this.data.today.slice(0, 7);
        } catch (error) { this.state.error = error.data?.message || "Transport records could not be loaded. Please retry."; }
        finally { this.state.busy = false; }
    }
    go(screen) {
        this.state.screen = screen; this.state.query = ""; this.state.status = "all"; this.state.type = "all";
        if (this.workspaceRef.el) this.workspaceRef.el.scrollTop = 0;
        this.router.pushState({transport_view: screen});
    }
    async changeYear() { this.router.pushState({transport_year: this.state.year}); await this.load(); }
    async open(kind, id = false) {
        try {
            const action = await this.orm.call("campus.dashboard", "get_transport_action", [kind, id]);
            action.context = {...action.context, default_year_id: this.data.year_id, campus_module: "transport"};
            await this.action.doAction(action, {onClose: () => this.load()});
        } catch (error) { this.state.error = error.data?.message || "This transport record could not be opened."; }
    }
    openRow(row) { return this.open(this.state.screen === "routes" ? "fleet" : this.state.screen === "drivers" ? "payroll" : row.kind, this.state.screen === "revenue" ? row.record_id : row.id); }
    exportRows() {
        const rows = [this.columns, ...this.rows.map(row => [...this.cells(row), this.statusLabel(row.status)])];
        const csv = "\uFEFF" + rows.map(row => row.map(value => '"' + String(value).replaceAll('"', '""') + '"').join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a"); link.href = url; link.download = `transport-${this.state.screen}.csv`; link.click(); URL.revokeObjectURL(url);
    }
}
registry.category("actions").add("ideastone_erp.accountant_transport", AccountantTransport);

