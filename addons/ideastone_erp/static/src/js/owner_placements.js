/** @odoo-module **/
import { Component, onMounted, useExternalListener, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

const SCREENS = new Set(["overview", "departments", "students", "drives", "offers", "history", "insights"]);

class OwnerPlacements extends Component {
    static template = "ideastone_erp.OwnerPlacements";
    static props = ["*"];
    setup() {
        this.router = useService("router");
        this.company = useService("company");
        this.frame = useRef("workspace");
        const route = this.route();
        this.currentRoute = route;
        this.url = "/campus/owner/placements/workspace?" + new URLSearchParams({
            company_id: this.company.currentCompany.id, ...route,
        });
        useExternalListener(window, "message", event => {
            if (event.origin !== location.origin || event.source !== this.frame.el?.contentWindow || !this.isCurrentAction()) return;
            if (event.data?.type === "campus-owner-placements-ready") return this.navigate(true);
            if (event.data?.type !== "campus-owner-placements-route" || !SCREENS.has(event.data.screen)) return;
            const year = String(event.data.year ?? "");
            const department = String(event.data.department || "All");
            if (!/^(0|\d{4})?$/.test(year) || !/^(All|\d{1,10})$/.test(department)) return;
            this.currentRoute = {screen: event.data.screen, year, department};
            this.env.bus.trigger("CAMPUS:PAGE", event.data.screen);
            this.router.pushState({placements_screen: event.data.screen, placements_year: year,
                placements_department: department, campus_module: "placements"});
        });
        onMounted(() => this.navigate());
        useBus(this.env.bus, "CAMPUS:PLACEMENTS:NAVIGATE", event => {
            if (this.isCurrentAction() && SCREENS.has(event.detail)) this.frame.el?.contentWindow?.postMessage({
                type: "campus-owner-placements-navigate", ...this.route(), screen: event.detail,
            }, location.origin);
        });
        useBus(this.env.bus, "ROUTE_CHANGE", () => this.navigate());
        useExternalListener(window, "hashchange", () => this.navigate());
    }
    isCurrentAction() {
        const id = new URLSearchParams(location.hash.slice(1)).get("action");
        return Boolean(id) && (id === String(this.props.action.id) || id === this.props.action.xml_id);
    }
    route() {
        // Read the address being restored; Odoo can still hold the previous action's route during mounting.
        const hash = Object.fromEntries(new URLSearchParams(location.hash.slice(1)));
        const action = this.props.action;
        const matching = this.isCurrentAction();
        const previous = this.currentRoute || {};
        // Odoo briefly reduces the address to the action ID while restoring a client action.
        const screen = (matching && hash.placements_screen) || previous.screen || action.context?.placements_screen || "overview";
        return {screen: SCREENS.has(screen) ? screen : "overview",
            year: String(hash.placements_year ?? previous.year ?? ""),
            department: String(hash.placements_department ?? previous.department ?? "All")};
    }
    navigate(restoreHash = false) {
        if (!this.isCurrentAction()) return;
        const route = this.currentRoute = this.route();
        this.env.bus.trigger("CAMPUS:PAGE", route.screen);
        if (restoreHash === true) this.router.replaceState({placements_screen: route.screen, placements_year: route.year,
            placements_department: route.department, campus_module: "placements"});
        this.frame.el?.contentWindow?.postMessage({type: "campus-owner-placements-navigate", ...route}, location.origin);
    }
}

registry.category("actions").add("ideastone_erp.owner_placements", OwnerPlacements);
