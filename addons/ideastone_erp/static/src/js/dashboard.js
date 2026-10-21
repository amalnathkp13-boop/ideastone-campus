/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useExternalListener, useRef, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

function dashboardRoute(action = {}) {
    const params = {...action.params, ...action.context?.params, ...action.context};
    return {page: params.campus_page || "overview", module: params.campus_module || "home"};
}

class CampusBase extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.router = useService("router");
        this.notification = useService("notification");
        this.toggleRef = useRef("navToggle");
        this.subnavRef = useRef("subnavStrip");
        const route = dashboardRoute(this.props.action);
        this.state = useState({ loading: true, error: "", navigation: [], stats: [], pages: [], queues: [], quick: [], appointments: [],
            company: "", user: "", filter: "", open: false, page: route.page,
            is_owner_workspace: false, is_demo: false, ownerMetrics: {stats: [], years: [], setup: [], funnel: [], programmes: [], collection: [], trend: [], recent: [], notices: [], upcoming: [], due_dates: []},
            ownerFilters: {date_from: "", date_to: "", year_id: ""}, ownerError: "", ownerLoading: false,
            faculty_modules: [], faculty_tasks: [], faculty_schedule: [], faculty_surveys: [], module: route.module, activeAction: 0, activeTool: "",
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
            if (this.state.is_owner_workspace) {
                if (this.state.page === "overview") this.state.page = "owner-overview";
                const hash = this.router.current.hash;
                if (!this.state.ownerFilters.date_from) Object.assign(this.state.ownerFilters, {
                    date_from: hash.owner_from || `${this.state.today.slice(0, 8)}01`,
                    date_to: hash.owner_to || this.state.today, year_id: hash.owner_year || "",
                });
                if (this.state.page === "owner-overview") await this.loadOwnerMetrics();
            }
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
    get facultyModule() { return this.state.faculty_modules.find(item => item.key === this.state.module) || this.state.faculty_modules[0]; }
    get pageTitle() {
        if (this.state.page === "owner-overview") return "College overview";
        if (this.state.page === "faculty-module") return this.facultyModule?.label || "Faculty workspace";
        if (this.state.page === "help") return "Faculty guide";
        if (this.state.page === "analytics") return "My teaching dashboard";
        if (this.state.page === "surveys") return "My survey invitations";
        if (this.state.page === "overview") return this.state.is_admin ? "Institution overview" : "Your faculty workspace";
        if (this.state.page === "modules") return this.state.is_admin ? "All college modules" : "Your authorized modules";
        return this.state.page === "library" ? "Library circulation desk" : "Reports & exports";
    }
    async chooseModule(module) {
        if (this.state.is_owner_workspace && module.key === "admissions" && module.items?.[0]?.action) {
            this.state.module = module.key;
            return this.open(module.items[0]);
        }
        await this.action.doAction("ideastone_erp.action_dashboard", {
            additionalContext: { campus_page: module.key === "home" ? (this.state.is_owner_workspace ? "owner-overview" : "overview") : "faculty-module", campus_module: module.key },
        });
        this.state.module = module.key;
        this.state.open = false;
    }
    async facultyGo(item) {
        if (item.action || item.profile_id || item.tool || item.url) return this.open(item);
        await this.go({ key: item.page });
    }
    async open(item) {
        if (item.allowed === false) return;
        try {
            if (["ideastone_erp.action_faculty_appraisal_dashboard", "ideastone_erp.action_staff_profile"].includes(item.action) && item.action_id) {
                window.location.assign(`/web#action=${item.action_id}`);
                return;
            }
            if (item.url) {
                await this.action.doAction({type: "ir.actions.act_url", url: item.url, target: "new"});
            } else if (item.tool) {
                await this.action.doAction(await this.orm.call("campus.dashboard", "get_faculty_action", [item.tool]));
            } else if (item.profile_id) {
                await this.action.doAction({ type: "ir.actions.act_window", res_model: "op.faculty", res_id: item.profile_id, views: [[false, "form"]], target: "current" });
            } else {
                const action = this.state.is_owner_workspace && ![
                    "ideastone_erp.action_faculty_leave_page", "ideastone_erp.action_faculty_appraisal_dashboard", "ideastone_erp.action_staff_profile", "ideastone_erp.action_faculty_attendance_page", "ideastone_erp.action_student_attendance_workspace",
                ].includes(item.action) ?
                    await this.orm.call("campus.dashboard", "get_owner_action", [item.action]) : item.action;
                if (this.state.is_owner_workspace && action.context) action.context.campus_module = this.state.module;
                if (action.help) action.help = markup(action.help);
                await this.action.doAction(action);
            }
            this.state.open = false;
        } catch (error) {
            this.notification.add("This screen could not be opened. Check your access permissions or retry.", { type: "danger" });
        }
    }
    async go(item) {
        if (item.action || item.profile_id) return this.open(item);
        this.state.open = false;
        const module = this.state.faculty_modules.length && ["reports", "analytics", "help"].includes(item.key) ? item.key : this.state.module;
        await this.action.doAction("ideastone_erp.action_dashboard", { additionalContext: { campus_page: item.key, campus_module: module } });
    }
    async home() {
        if (this.state.faculty_modules.length) return this.chooseModule(this.state.faculty_modules[0]);
        await this.go({ key: "overview" });
    }
    closeNav() { this.state.open = false; this.toggleRef.el?.focus(); }
    async loadOwnerMetrics() {
        if (this.state.ownerLoading) return;
        this.state.ownerLoading = true;
        this.state.ownerError = "";
        try {
            this.state.ownerMetrics = await this.orm.call("campus.dashboard", "get_owner_metrics", [this.state.ownerFilters]);
            this.router.pushState({owner_from: this.state.ownerFilters.date_from, owner_to: this.state.ownerFilters.date_to, owner_year: this.state.ownerFilters.year_id});
        } catch (error) {
            this.state.ownerError = error.data?.message || "The college report could not be loaded. Check the period and retry.";
        } finally { this.state.ownerLoading = false; }
    }
    async ownerSource(card) {
        if (!card.allowed) return;
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_source_action", [card.kind, this.state.ownerFilters]);
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || "The source register is unavailable.", {type: "danger"}); }
    }
    chartWidth(value, rows, field = "value") {
        const keys = Array.isArray(field) ? field : [field];
        const maximum = Math.max(1, ...rows.flatMap(row => keys.map(key => Math.abs(Number(row[key]) || 0))));
        return `${Math.abs(Number(value) || 0) / maximum * 100}%`;
    }
    number(value) { return new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(value); }
    scrollSubmodules(direction) { this.subnavRef.el?.scrollBy({left: direction * 320, behavior: "smooth"}); }
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
    setup() {
        super.setup();
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this.syncFacultyRoute());
        onWillUnmount(() => document.body.classList.remove("campus_faculty_workspace"));
    }
    async load() {
        await super.load();
        document.body.classList.toggle("campus_faculty_workspace", this.state.faculty_modules.length > 0);
        this.syncFacultyRoute();
    }
    syncFacultyRoute() {
        const action = this.action.currentController?.action;
        if (!action || action.target === "new" || !this.state.faculty_modules.length) return;
        this.state.activeAction = action.id || 0;
        this.state.activeTool = action.context?.campus_tool || "";
        if (action.tag === "ideastone_erp.dashboard") {
            const route = dashboardRoute(action);
            this.state.module = route.module;
            this.state.page = route.page;
            // Odoo includes these hash parameters in the restored client action.
            this.router.pushState({campus_module: route.module, campus_page: route.page});
        } else if (action.context?.campus_module) {
            this.state.module = action.context.campus_module;
            this.state.page = action.context.campus_page || "overview";
        } else {
            const module = this.state.faculty_modules.find(module => module.items.some(item => item.action_id && item.action_id === action.id)) ||
                this.state.faculty_modules.find(module => module.items.some(item => item.model && item.model === action.res_model));
            if (module) this.state.module = module.key;
        }
    }
}
registry.category("actions").add("ideastone_erp.dashboard", CampusDashboard);
registry.category("main_components").add("CampusNavigation", { Component: CampusNavigation });
