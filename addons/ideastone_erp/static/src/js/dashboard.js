/** @odoo-module **/
import { Component, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

class CampusBase extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.toggleRef = useRef("navToggle");
        this.state = useState({ loading: true, error: "", navigation: [], stats: [], pages: [], queues: [], quick: [], appointments: [],
            company: "", user: "", filter: "", open: false, page: this.props.action?.context?.campus_page || "overview",
            busy: false, query: "", cardQuery: "", unit: "", card: "", loanPage: 0, desk: { units: [], cards: [], loans: [], next: false } });
        // Handle the drawer before Odoo's global Escape shortcut consumes the key.
        useExternalListener(window, "keydown", (event) => {
            if (event.key === "Escape" && this.state.open) { this.closeNav(); event.stopPropagation(); }
        }, { capture: true });
        useBus(this.env.bus, "CAMPUS:PAGE", (event) => { this.state.page = event.detail; });
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            Object.assign(this.state, await this.orm.call("campus.dashboard", "get_overview", []));
            if (this.state.page === "library") await this.loadDesk();
            if (this.props.action) this.env.bus.trigger("CAMPUS:PAGE", this.state.page);
        } catch (error) {
            this.state.error = "Campus data could not be loaded. Check your access or retry.";
        } finally {
            this.state.loading = false;
        }
    }
    get groups() {
        const query = this.state.filter.trim().toLowerCase();
        return [...new Set(this.state.navigation.map(item => item.group))].map(label => ({
            label,
            items: this.state.navigation.filter(item => item.group === label && (!query || `${item.label} ${label}`.toLowerCase().includes(query))),
        })).filter(group => group.items.length);
    }
    async open(item) {
        if (item.allowed === false) return;
        try {
            if (item.profile_id) {
                await this.action.doAction({ type: "ir.actions.act_window", res_model: "op.faculty", res_id: item.profile_id, views: [[false, "form"]], target: "current" });
            } else {
                await this.action.doAction(item.action);
            }
            this.state.open = false;
        } catch (error) {
            this.notification.add("This screen could not be opened. Check your access permissions or retry.", { type: "danger" });
        }
    }
    async go(item) {
        if (item.action || item.profile_id) return this.open(item);
        this.state.open = false;
        await this.action.doAction("ideastone_erp.action_dashboard", { additionalContext: { campus_page: item.key } });
    }
    async home() { await this.go({ key: "overview" }); }
    closeNav() { this.state.open = false; this.toggleRef.el?.focus(); }
    async loadDesk() {
        this.state.desk = await this.orm.call("campus.library.desk", "get_desk", [this.state.query, this.state.loanPage, this.state.cardQuery]);
        this.state.unit = "";
        this.state.card = "";
    }
    async searchDesk() {
        if (this.state.busy) return;
        this.state.busy = true;
        try { await this.loadDesk(); }
        catch (error) { this.notification.add("The library desk is unavailable. Check your appointment and search again.", { type: "danger" }); }
        finally { this.state.busy = false; }
    }
    async loanPage(delta) { this.state.loanPage += delta; await this.searchDesk(); }
    async issue() {
        if (!this.state.unit || !this.state.card || this.state.busy) return;
        await this.libraryAction("issue", [Number(this.state.unit), Number(this.state.card)]);
    }
    async returnLoan(id) { await this.libraryAction("return_loan", [id]); }
    async libraryAction(method, args) {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            await this.orm.call("campus.library.desk", method, args);
            await this.loadDesk();
            this.notification.add("Library transaction saved.", { type: "success" });
        } catch (error) {
            this.notification.add(error.data?.message || "Transaction was not saved. Check availability and appointment scope.", { type: "danger" });
        } finally { this.state.busy = false; }
    }
}

export class CampusDashboard extends CampusBase {
    static template = "ideastone_erp.Dashboard";
    static props = ["*"];
}
export class CampusNavigation extends CampusBase {
    static template = "ideastone_erp.Navigation";
    static props = ["*"];
}
registry.category("actions").add("ideastone_erp.dashboard", CampusDashboard);
registry.category("main_components").add("CampusNavigation", { Component: CampusNavigation });
