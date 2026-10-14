/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CampusBase extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({ loading: true, error: "", navigation: [], stats: [], company: "", filter: "", open: false });
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            Object.assign(this.state, await this.orm.call("campus.dashboard", "get_overview", []));
        } catch (error) {
            this.state.error = "Campus data could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }
    get groups() {
        const query = this.state.filter.trim().toLowerCase();
        return [...new Set(this.state.navigation.map(item => item.group))].map(label => ({
            label,
            items: this.state.navigation.filter(item => item.group === label && (!query || item.label.toLowerCase().includes(query))),
        })).filter(group => group.items.length);
    }
    async open(item) {
        try {
            await this.action.doAction(item.action);
            this.state.open = false;
        } catch (error) {
            this.notification.add("This screen could not be opened. Check your access permissions or retry.", { type: "danger" });
        }
    }
    async home() {
        await this.open({ action: "ideastone_erp.action_dashboard" });
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
