/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class FleetEntry extends Component {
    static template = "ideastone_erp.FleetEntry";
    static components = { Dialog };
    static props = ["close", "mode", "title", "workspace", "save", "row?", "event?"];

    setup() {
        const row = this.props.row;
        this.state = useState({
            route_id: String(row?.id || ""), replacement_id: "", note: "", amount: "",
            date: this.props.workspace.today, category: "", arrival: row?.actual || "",
            status: row?.status || "operational", driver: row?.driver || "",
            insurance_until: row?.insurance_until || "", service_due: row?.service_due || "",
            expected: row?.expected || "", verified: false, busy: false, error: "",
        });
    }

    async submit() {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.error = "";
        try {
            const {busy, error, ...fields} = this.state;
            await this.props.save(this.props.mode, {
                ...fields, route_id: Number(fields.route_id), replacement_id: Number(fields.replacement_id),
                event_id: this.props.event?.id,
            });
            this.props.close();
        } catch (failure) {
            this.state.error = failure.data?.message || "The fleet entry could not be saved.";
        } finally {
            this.state.busy = false;
        }
    }
}

class FleetManagement extends Component {
    static template = "ideastone_erp.FleetManagement";
    static props = ["*"];
    metrics = [
        ["total", "Total buses", "Registered this academic year", "bus", "blue"],
        ["active", "Active buses", "Running regular or replacement service", "road", "green"],
        ["insured", "Insurance active", "Current coverage", "shield", "blue"],
        ["pending", "Insurance pending", "Expired or awaiting verification", "clock-o", "amber"],
        ["service", "Service due", "Due today or overdue", "wrench", "rose"],
        ["on_time", "Arrived on time", "Today’s recorded arrivals", "check", "green"],
    ];
    attention = [
        ["pending", "Insurance pending", "amber"], ["service", "Service due", "rose"],
        ["late", "Delayed arrivals today", "blue"], ["incidents", "Open incidents", "rose"],
    ];

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({data: null, period: "month", filter: this.props.initialFilter || "all", search: ""});
        onWillStart(() => this.load());
    }

    async load() {
        const period = this.state.period;
        const data = await this.orm.call("campus.fleet.ui", "get_workspace", [period]);
        if (period === this.state.period) this.state.data = data;
    }

    get rows() {
        const query = this.state.search.trim().toLowerCase();
        const filter = this.state.filter;
        return this.state.data.rows.filter(row =>
            (filter === "all" || (filter === "active" ? row.running : !row.running)) &&
            [row.bus, row.route, row.driver].some(value => value.toLowerCase().includes(query)));
    }

    amount(value, compact = false) {
        return new Intl.NumberFormat("en-IN", {
            style: "currency", currency: this.state.data.currency, minimumFractionDigits: compact ? 0 : 2,
        }).format(value);
    }

    expenseMonth(offset) {
        const [year, month] = this.state.data.today.split("-").map(Number);
        return new Intl.DateTimeFormat("en-IN", {month: "short", year: "numeric"})
            .format(new Date(year, month - 1 + offset, 1));
    }

    get expenseBars() {
        const categories = this.state.data.categories;
        const labels = {fuel: "Diesel", maintenance: "Servicing", insurance: "Insurance"};
        const wages = categories.find(category => category.key === "salary")?.amount || 0;
        const visible = categories.filter(category => category.key !== "salary").map(category => ({
            ...category, name: labels[category.key] || category.name,
            amount: category.amount + (category.key === "other" ? wages : 0),
        }));
        const maximum = Math.max(1, ...visible.map(category => category.amount));
        return visible.map(category => ({...category, width: category.amount / maximum * 100}));
    }

    async changePeriod(event) {
        this.state.period = event.target.value;
        await this.load();
    }

    entry(mode, title, row, event) {
        this.dialog.add(FleetEntry, {
            mode, title, row, event, workspace: this.state.data,
            save: async (operation, payload) => {
                await this.orm.call("campus.fleet.ui", "save", [operation, payload]);
                try {
                    await this.load();
                    this.notification.add("Fleet register updated.", {type: "success"});
                } catch {
                    this.notification.add("Saved. Refresh the page to reload the fleet register.", {type: "warning"});
                }
            },
        });
    }

    exportRoutes() {
        const cell = value => {
            const text = String(value);
            const safe = /^[\s]*[=+\-@]/.test(text) ? "'" + text : text;
            return '"' + safe.replaceAll('"', '""') + '"';
        };
        const rows = [["Bus", "Route", "Driver", "Running", "Expected", "Actual"],
            ...this.rows.map(row => [row.bus, row.route, row.driver, row.running ? "Yes" : "No", row.expected, row.actual])];
        const url = URL.createObjectURL(new Blob([rows.map(row => row.map(cell).join(",")).join("\r\n")], {type: "text/csv"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "fleet-routes.csv";
        link.click();
        URL.revokeObjectURL(url);
    }
}

registry.category("actions").add("ideastone_erp.fleet_management", FleetManagement);
