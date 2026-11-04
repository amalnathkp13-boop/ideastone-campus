/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useEffect, useExternalListener, useRef, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { FacultyHome, FacultyDepartments } from "./faculty_home";
import { FacultyCommunication } from "./faculty_communication";
import { FacultyCampusServices } from "./faculty_campus_services";
import { NavigationCustomizer } from "@ideastone_campus/js/navigation_customizer";
import { navigationItems } from "@ideastone_campus/js/navigation_state";
import { OwnerSettings } from "./owner_settings";

class OwnerReportFilters extends Component {
    static template = "ideastone_erp.OwnerReportFilters";
    static components = { Dialog };
    static props = ["filters", "years", "apply", "close"];
    setup() { this.state = useState({...this.props.filters, busy: false, error: ""}); }
    async apply() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            this.state.error = await this.props.apply({date_from: this.state.date_from, date_to: this.state.date_to, year_id: this.state.year_id});
            if (!this.state.error) this.props.close();
        } finally { this.state.busy = false; }
    }
}

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
        this.dialog = useService("dialog");
        this.toggleRef = useRef("navToggle");
        this.subnavRef = useRef("subnavStrip");
        const route = dashboardRoute(this.props.action);
        this.state = useState({ loading: true, error: "", navigation: [], stats: [], pages: [], queues: [], quick: [], appointments: [],
            company: "", user: "", filter: "", open: false, page: route.page,
            is_owner_workspace: false, is_accountant_workspace: false, is_demo: false, ownerMetrics: {stats: [], years: [], setup: [], funnel: [], programmes: [], collection: [], trend: [], recent: [], notices: [], upcoming: [], due_dates: []},
            accountantMetrics: {cards: [], trend: [], collection_status: {}, activity: [], queue: [], departments: []},
            accountantFilters: {date_from: "", date_to: "", year_id: "", department_id: ""}, accountantError: "", accountantLoading: false,
            accountantTrendPeriod: "half",
            collectionOverview: {departments: [], by_department: [], status: {}, recent: []},
            collectionFilters: {date_from: "", date_to: "", department_id: ""},
            collectionError: "", collectionLoading: false,
            collectionRecords: {columns: [], rows: [], years: [], metrics: [], money_columns: [], date_columns: []},
            collectionYearId: "", collectionSearch: "", collectionStatusFilter: "",
            ownerFilters: {date_from: "", date_to: "", year_id: ""}, ownerAppliedFilters: {}, ownerError: "", ownerLoading: false,
            faculty_modules: [], faculty_tasks: [], faculty_schedule: [], faculty_surveys: [], module: route.module, activeAction: 0, activeTool: "",
            busy: false, query: "", cardQuery: "", unit: "", card: "", loanPage: 0, desk: { units: [], cards: [], loans: [], next: false } });
        // Handle the drawer before Odoo's global Escape shortcut consumes the key.
        useExternalListener(window, "keydown", (event) => {
            if (event.key === "Escape" && this.state.open && !document.querySelector(".campus_nav_dialog[open]")) { this.closeNav(); event.stopPropagation(); }
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
                if (this.state.is_accountant_workspace && !["overview", "accountant-overview", "faculty-module", "modules"].includes(this.state.page) && !this.state.page.startsWith("accountant-collections-")) {
                    this.state.page = "accountant-overview";
                }
                if (this.state.page === "overview") this.state.page = this.state.is_accountant_workspace ? "accountant-overview" : "owner-overview";
                const hash = this.router.current.hash;
                if (!this.state.ownerFilters.date_from) Object.assign(this.state.ownerFilters, {
                    date_from: hash.owner_from || `${this.state.today.slice(0, 8)}01`,
                    date_to: hash.owner_to || this.state.today, year_id: hash.owner_year || "",
                });
                if (this.state.page === "owner-overview") await this.loadOwnerMetrics();
                if (this.state.page === "accountant-overview") await this.loadAccountantMetrics();
                if (this.state.page === "accountant-collections-overview") await this.loadCollectionOverview();
                if (this.state.page.startsWith("accountant-collections-") && this.state.page !== "accountant-collections-overview") await this.loadCollectionRecords();
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
        if (this.state.page.startsWith("settings-")) return "Settings";
        if (this.state.faculty_home_enabled && this.state.page === "overview") return "Faculty overview";
        if (this.state.page === "faculty-departments") return "My departments";
        if (this.state.page === "owner-overview") return "Admin overview";
        if (this.state.page === "accountant-overview") return "Accountant overview";
        if (this.state.page === "accountant-collections-overview") return "Collections overview";
        if (this.state.page.startsWith("accountant-collections-")) return this.collectionPage.title;
        if (this.state.page === "faculty-module") return this.facultyModule?.label || "Faculty workspace";
        if (this.state.page === "help") return "Faculty guide";
        if (this.state.page === "analytics") return "My teaching dashboard";
        if (this.state.page === "surveys") return "My survey invitations";
        if (this.state.page === "overview") return this.state.is_admin ? "Institution overview" : "Your faculty workspace";
        if (this.state.page === "modules") return this.state.is_admin ? "All college modules" : "Your authorized modules";
        return this.state.page === "library" ? "Library circulation desk" : "Reports & exports";
    }
    async chooseModule(module) {
        if (this.state.is_principal_workspace && ["home", "decisions", "principal_notices"].includes(module.key) && module.items?.[0]?.action) {
            this.state.module = module.key;
            return this.open(module.items[0]);
        }
        if (module.key === "collections" && this.state.is_accountant_workspace) {
            this.state.module = "collections";
            return this.go({key: "accountant-collections-overview"});
        }
        if (module.key === "accounts" && this.state.is_owner_workspace) {
            this.state.module = "accounts";
            return this.go({key: "accountant-overview"});
        }
        if (this.state.is_owner_workspace && module.key === "settings") {
            this.state.module = "settings";
            return this.settingsPage("overview");
        }
        if ((this.state.is_coe_workspace || (this.state.is_accountant_workspace && module.key === "spending")) && module.items?.[0]?.action) {
            this.state.module = module.key;
            return this.open(module.items[0]);
        }
        if (this.state.is_accountant_workspace && module.key === "transport") {
            this.state.module = module.key;
            return this.open(module.items[0]);
        }
        if (((module.key === "staff" && this.state.faculty_profile_enabled) || ["teaching", "od", "attendance", "library", "grievances"].includes(module.key) || (this.state.is_owner_workspace && ["admissions", "students", "exams", "academics", "fees", "calendar", "staff", "communication"].includes(module.key))) && module.items?.[0]?.action) {
            this.state.module = module.key;
            return this.open(module.items[0]);
        }
        await this.action.doAction("ideastone_erp.action_dashboard", {
            additionalContext: { campus_page: module.key === "home" ? (this.state.is_accountant_workspace ? "accountant-overview" : this.state.is_owner_workspace ? "owner-overview" : "overview") : module.key === "engagement" ? "communication-surveys" : module.key === "services" ? "campus-services-service" : "faculty-module", campus_module: module.key },
        });
        this.state.module = module.key;
        this.state.open = false;
    }
    async facultyGo(item) {
        if (this.state.is_owner_workspace && this.state.module === "settings" && item.page?.startsWith("settings-")) {
            return this.settingsPage(item.page.slice(9));
        }
        if (item.action || item.profile_id || item.tool || item.url) return this.open(item);
        await this.go({ key: item.page });
    }
    async settingsPage(screen) {
        this.state.module = "settings";
        this.state.open = false;
        await this.action.doAction("ideastone_erp.action_dashboard", {
            additionalContext: {campus_page: `settings-${screen}`, campus_module: "settings"},
        });
    }
    async open(item) {
        if (item.allowed === false) return;
        try {
            if (["ideastone_erp.action_students_directory", "ideastone_erp.action_students_enrolments"].includes(item.action)) {
                this.router.pushState({students_screen: item.action.endsWith("enrolments") ? "enrolments" : "directory", students_department_id: "", students_batch_id: ""});
            }
            if (["ideastone_erp.action_faculty_appraisal_dashboard", "ideastone_erp.action_staff_profile", "ideastone_erp.action_staff_od_management", "ideastone_erp.action_hod_od_management", "ideastone_erp.action_faculty_grievances"].includes(item.action) && item.action_id) {
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
                    "ideastone_erp.action_faculty_leave_page", "ideastone_erp.action_faculty_appraisal_dashboard", "ideastone_erp.action_staff_profile", "ideastone_erp.action_staff_od_management", "ideastone_erp.action_hod_od_management", "ideastone_erp.action_faculty_attendance_page", "ideastone_erp.action_student_attendance_workspace",
                ].includes(item.action) ?
                    await this.orm.call("campus.dashboard", "get_owner_action", [item.action]) : item.action;
                if (this.state.is_owner_workspace && action.context) action.context.campus_module = this.state.module;
                if (this.state.is_principal_workspace && action.context) action.context.campus_workspace_role = "Principal";
                if (action.tag === "ideastone_erp.examinations") action.context.exams_year_id = this.action.currentController?.action.context?.exams_year_id ?? this.router.current.hash.exams_year_id ?? 0;
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
    ownerOpenFilters() {
        this.dialog.add(OwnerReportFilters, {
            filters: {...this.state.ownerFilters}, years: this.state.ownerMetrics.years,
            apply: async (filters) => {
                const previous = {...this.state.ownerFilters};
                Object.assign(this.state.ownerFilters, filters);
                await this.loadOwnerMetrics();
                const error = this.state.ownerError;
                if (error) {
                    Object.assign(this.state.ownerFilters, previous);
                    this.state.ownerError = "";
                }
                return error;
            },
        });
    }
    async loadOwnerMetrics() {
        if (this.state.ownerLoading) return;
        this.state.ownerLoading = true;
        this.state.ownerError = "";
        try {
            this.state.ownerMetrics = await this.orm.call("campus.dashboard", "get_owner_metrics", [this.state.ownerFilters]);
            this.state.ownerAppliedFilters = {...this.state.ownerFilters};
            this.router.pushState({owner_from: this.state.ownerFilters.date_from, owner_to: this.state.ownerFilters.date_to, owner_year: this.state.ownerFilters.year_id});
        } catch (error) {
            this.state.ownerError = error.data?.message || "The college report could not be loaded. Check the period and retry.";
        } finally { this.state.ownerLoading = false; }
    }
    async loadAccountantMetrics() {
        if (this.state.accountantLoading) return;
        this.state.accountantLoading = true;
        this.state.accountantError = "";
        try {
            if (!this.state.accountantFilters.date_from) Object.assign(this.state.accountantFilters, {
                date_from: `${this.state.today.slice(0, 8)}01`,
                date_to: `${this.state.today.slice(0, 8)}${new Date(Number(this.state.today.slice(0, 4)), Number(this.state.today.slice(5, 7)), 0).getDate()}`,
            });
            this.state.accountantMetrics = await this.orm.call("campus.dashboard", "get_accountant_metrics", [this.state.accountantFilters]);
        } catch (error) {
            this.state.accountantError = error.data?.message || "Accounts records could not be loaded. Check the period and retry.";
        } finally { this.state.accountantLoading = false; }
    }
    async loadCollectionOverview() {
        if (this.state.collectionLoading) return;
        this.state.collectionLoading = true;
        this.state.collectionError = "";
        try {
            if (!this.state.collectionFilters.date_from) Object.assign(this.state.collectionFilters, {
                date_from: `${this.state.today.slice(0, 8)}01`,
                date_to: this.state.today,
            });
            this.state.collectionOverview = await this.orm.call("campus.dashboard", "get_accountant_collections_overview", [this.state.collectionFilters]);
        } catch (error) {
            this.state.collectionError = error.data?.message || "Collections could not be loaded. Check the filters and retry.";
        } finally { this.state.collectionLoading = false; }
    }
    get collectionScreen() { return this.state.page.replace("accountant-collections-", ""); }
    get collectionPage() {
        return {
            structures: {title: "Fee structures", description: "Configure fee heads, programme applicability and installment rules.", action: "New fee structure"},
            assign: {title: "Assign fee structure", description: "Map a fee plan to student cohorts or individual enrolments.", action: "Assign fee structure"},
            invoices: {title: "Invoices", description: "Issue, track and manage student fee invoices.", action: "New invoice"},
            receipts: {title: "Receipts", description: "Review payment receipts and reconcile incoming collections.", action: "Record payment"},
            reports: {title: "Collection report", description: "Compare billed, collected and outstanding balances by department.", action: "Open report"},
            dues: {title: "Dues report", description: "Identify overdue balances and prioritize follow-up.", action: "Open dues report"},
            exports: {title: "Export files", description: "Prepare scoped CSV files for finance reconciliation and audit.", action: ""},
        }[this.collectionScreen] || {title: "Collections", description: "", action: ""};
    }
    async loadCollectionRecords() {
        if (this.state.collectionLoading) return;
        this.state.collectionLoading = true;
        this.state.collectionError = "";
        try {
            this.state.collectionRecords = await this.orm.call("campus.dashboard", "get_accountant_collection_records", [this.collectionScreen, this.state.collectionYearId]);
        } catch (error) {
            this.state.collectionError = error.data?.message || "Collection records could not be loaded. Please retry.";
        } finally { this.state.collectionLoading = false; }
    }
    collectionChangeYear(event) {
        this.state.collectionYearId = event.target.value;
        this.loadCollectionRecords();
    }
    get collectionRecordRows() {
        const query = this.state.collectionSearch.trim().toLowerCase();
        const status = this.state.collectionStatusFilter;
        return (this.state.collectionRecords.rows || []).filter(row =>
            (!status || row.status === status) && (!query || row.cells.join(" ").toLowerCase().includes(query)));
    }
    get collectionStatuses() {
        return [...new Set((this.state.collectionRecords.rows || []).map(row => row.status).filter(Boolean))];
    }
    collectionFullMoney(value) {
        const currency = this.state.collectionRecords.currency || "₹";
        return `${currency}${new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2}).format(Number(value) || 0)}`;
    }
    async collectionOpenEditor() {
        const screen = this.collectionScreen;
        if (screen === "invoices") return this.collectionCreateInvoice();
        if (screen === "assign") return this.accountantOpen("mvp_assign_fees");
        if (screen === "receipts") return this.action.doAction({type: "ir.actions.act_window", name: "Record payment",
            res_model: "campus.fee.payment.wizard", views: [[false, "form"]], target: "new"});
        if (screen === "reports" || screen === "dues") return this.accountantOpen(screen === "reports" ? "mvp_report_collection" : "mvp_report_dues");
        if (screen === "structures") {
            try {
                const action = await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.mvp_structures"]);
                await this.action.doAction({type: "ir.actions.act_window", name: action.name,
                    res_model: action.res_model, views: [action.views.find(([, type]) => type === "form")],
                    view_mode: "form", target: "current", context: action.context, domain: action.domain});
            } catch {
                this.notification.add("The fee structure form could not be opened.", {type: "danger"});
            }
        }
    }
    async collectionOpenRecord(id) {
        const source = {
            structures: "mvp_structures", assign: "mvp_fees", invoices: "mvp_invoices",
            receipts: "mvp_receipts", dues: "mvp_invoices",
        }[this.collectionScreen];
        if (!source) return;
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_action", [`ideastone_erp.${source}`]);
            await this.action.doAction({type: "ir.actions.act_window", name: action.name,
                res_model: action.res_model, res_id: id,
                views: [action.views.find(([, type]) => type === "form")],
                view_mode: "form", target: "current", context: action.context, domain: action.domain});
        } catch {
            this.notification.add("This record could not be opened. Check your access and retry.", {type: "danger"});
        }
    }
    async collectionExportCsv(screen = this.collectionScreen) {
        try {
            const data = screen === this.collectionScreen ? this.state.collectionRecords :
                await this.orm.call("campus.dashboard", "get_accountant_collection_records", [screen, this.state.collectionYearId]);
            const rows = screen === this.collectionScreen ? this.collectionRecordRows : data.rows;
            const values = [data.columns, ...rows.map(row => row.cells.map((cell, index) =>
                data.money_columns.includes(index) ? this.collectionFullMoney(cell) : data.date_columns.includes(index) ? this.collectionDate(cell) : cell))];
            const csv = "\uFEFF" + values.map(row => row.map(cell => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
            const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
            const link = document.createElement("a");
            link.href = url;
            link.download = `collections-${screen}.csv`;
            link.click();
            URL.revokeObjectURL(url);
        } catch {
            this.notification.add("The export could not be prepared. Please retry.", {type: "danger"});
        }
    }
    collectionMoney(value) {
        const amount = Number(value) || 0;
        const absolute = Math.abs(amount);
        const currency = this.state.collectionOverview.currency || "₹";
        const divisor = currency === "₹" ? (absolute >= 10000000 ? 10000000 : absolute >= 100000 ? 100000 : 1) :
            (absolute >= 1000000 ? 1000000 : absolute >= 1000 ? 1000 : 1);
        const suffix = divisor === 1 ? "" : currency === "₹" ? (divisor === 10000000 ? "Cr" : "L") : (divisor === 1000000 ? "M" : "K");
        return `${currency}${new Intl.NumberFormat("en-IN", {maximumFractionDigits: divisor === 1 ? 0 : 1}).format(amount / divisor)}${suffix}`;
    }
    collectionRate(value, total) {
        return total ? Math.max(0, Math.min(100, Math.round(value / total * 100))) : 0;
    }
    collectionDate(value) {
        if (!value) return "";
        const [year, month, day] = value.split("-").map(Number);
        return new Intl.DateTimeFormat("en-GB", {day: "numeric", month: "short", year: "numeric"}).format(new Date(year, month - 1, day));
    }
    get collectionInsights() {
        const data = this.state.collectionOverview;
        const weakest = [...(data.by_department || [])].filter(row => row.billed).sort((a, b) => a.rate - b.rate)[0];
        return [
            {tag: "FOLLOW-UP PRIORITY", title: weakest ? `Review ${weakest.name} accounts` : "Review outstanding accounts",
                detail: weakest ? `${weakest.name} has a ${weakest.rate}% collection rate for the selected period. Check its unpaid invoices and reminders.` : "No department invoices are posted in this period. Check the invoice register after billing."},
            {tag: "RECONCILIATION", title: "Match receipts to invoices",
                detail: `${this.collectionMoney(data.collected_month)} was received in this period. Confirm receipt references and reversals before closing the report.`},
            {tag: "PERIOD CLOSE", title: "Prioritize overdue balances",
                detail: `${this.collectionMoney(data.overdue)} is overdue across the selected accounts. Review the dues report before sending follow-ups.`},
        ];
    }
    async collectionCreateInvoice() {
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.mvp_invoices"]);
            action.name = "New student invoice";
            action.views = [[false, "form"]];
            action.view_mode = "form";
            action.context = {...action.context, default_move_type: "out_invoice"};
            await this.action.doAction(action);
        } catch {
            this.notification.add("The invoice form could not be opened. Check your permissions and retry.", {type: "danger"});
        }
    }
    accountantOpen(xmlid) {
        const item = this.state.navigation.find(row => row.action === `ideastone_erp.${xmlid}`);
        if (item) return this.open(item);
    }
    accountantMoney(value) {
        return `${this.state.accountantMetrics.currency || ""}${new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2}).format(value || 0)}`;
    }
    accountantCompactMoney(value) {
        const amount = Number(value) || 0;
        const absolute = Math.abs(amount);
        const indian = this.state.accountantMetrics.currency === "₹";
        const divisor = indian ? (absolute >= 10000000 ? 10000000 : absolute >= 100000 ? 100000 : 1) :
            (absolute >= 1000000 ? 1000000 : absolute >= 1000 ? 1000 : 1);
        const suffix = divisor === 1 ? "" : indian ? (divisor === 10000000 ? "Cr" : "L") : (divisor === 1000000 ? "M" : "K");
        return `${this.state.accountantMetrics.currency || ""}${new Intl.NumberFormat("en-IN", {maximumFractionDigits: 2}).format(amount / divisor)}${suffix}`;
    }
    get accountantTrendRows() {
        const rows = this.state.accountantMetrics.trend || [];
        return this.state.accountantTrendPeriod === "year" ? rows : rows.slice(-6);
    }
    get accountantChartMax() {
        const values = this.accountantTrendRows.flatMap(row => [row.collections, row.income]);
        const peak = Math.max(1, ...values);
        const raw = peak * 1.15 / 4;
        const magnitude = 10 ** Math.floor(Math.log10(raw));
        const step = [1, 2, 5, 10].find(candidate => candidate * magnitude >= raw) * magnitude;
        return step * 4;
    }
    get accountantChartTicks() {
        return Array.from({length: 5}, (_, index) => ({y: 30 + index * 47.5, value: this.accountantChartMax * (4 - index) / 4}));
    }
    get accountantChartBars() {
        const rows = this.accountantTrendRows;
        const width = rows.length === 12 ? 13 : 24;
        const step = 540 / Math.max(rows.length, 1);
        return rows.map((row, index) => {
            const x = 70 + index * step + (step - 2 * width - 4) / 2;
            const incomeHeight = Math.max(0, row.income) / this.accountantChartMax * 190;
            const collectionHeight = Math.max(0, row.collections) / this.accountantChartMax * 190;
            return {key: row.month, label: row.label, x, width,
                incomeY: 220 - incomeHeight, incomeHeight,
                collectionX: x + width + 4, collectionY: 220 - collectionHeight, collectionHeight,
                labelX: x + width + 2, income: row.income, collections: row.collections};
        });
    }
    accountantAxisMoney(value) {
        const indian = this.state.accountantMetrics.currency === "₹";
        const divisor = indian ? 100000 : Math.max(1, this.accountantChartMax >= 10000 ? 1000 : 1);
        return this.number(value / divisor);
    }
    get accountantChartUnit() {
        return `${this.state.accountantMetrics.currency || ""} ${this.state.accountantMetrics.currency === "₹" ? "lakh" : this.accountantChartMax >= 10000 ? "thousand" : "units"}`;
    }
    get accountantTrendChange() {
        const rows = this.accountantTrendRows;
        if (rows.length < 2 || !rows[rows.length - 2].collections) return null;
        return (rows[rows.length - 1].collections - rows[rows.length - 2].collections) /
            Math.abs(rows[rows.length - 2].collections) * 100;
    }
    get accountantCollectionStatus() {
        const status = this.state.accountantMetrics.collection_status || {};
        const total = Math.max(0, status.total || 0);
        const collected = Math.max(0, status.collected || 0);
        const pending = Math.max(0, status.pending || 0);
        const overdue = Math.max(0, status.overdue || 0);
        const circumference = 364.42;
        const collectedLength = total ? Math.min(1, collected / total) * circumference : 0;
        const pendingLength = total ? Math.min(1, pending / total) * circumference : 0;
        const overdueLength = total ? Math.min(1, overdue / total) * circumference : 0;
        return {total, collected, pending, overdue, overdue_30: status.overdue_30 || 0,
            percent: total ? Math.round(collected / total * 100) : 0, circumference,
            segments: [{key: "collected", color: "#1769e8", length: collectedLength, offset: 0},
                {key: "pending", color: "#69b8a4", length: pendingLength, offset: -collectedLength},
                {key: "overdue", color: "#f0b65c", length: overdueLength, offset: -collectedLength - pendingLength}]};
    }
    get accountantQueueCount() {
        return (this.state.accountantMetrics.queue || []).reduce((total, row) => total + row.count, 0);
    }
    accountantExportSummary() {
        const data = this.state.accountantMetrics;
        const department = data.departments?.find(row => String(row.id) === String(this.state.accountantFilters.department_id))?.name || "All departments";
        const rows = [["Accountant overview", data.period?.from || "", data.period?.to || "", department],
            ["Metric", "Amount"], ...(data.cards || []).map(card => [card.label, card.value]),
            [], ["Month", "Collections", "Billed income"],
            ...(data.trend || []).map(row => [row.month, row.collections, row.income]),
            [], ["Recent activity", "Reference", "Amount", "Status"],
            ...(data.activity || []).map(row => [row.name, row.reference, row.amount, row.status])];
        const csv = "\uFEFF" + rows.map(row => row.map(value => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = `accountant-overview-${data.period?.to || "report"}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }
    async ownerSource(card) {
        if (!card.allowed) return;
        try {
            if (card.kind === "fleet" && this.ownerUI.fleet) return this.openOwnerFleet("active");
            if (["services", "attendance_pending", "overdue_services", "overdue_dues", "staff_present", "staff_delayed", "fleet"].includes(card.kind)) return this.ownerOverviewAction(card.kind);
            const action = await this.orm.call("campus.dashboard", "get_owner_source_action", [card.kind, this.state.ownerAppliedFilters]);
            if (!action.views) action.views = (action.view_mode || "tree,form").split(",").map(mode => [false, mode]);
            if (action.help) action.help = markup(action.help);
            await this.action.doAction(action);
        } catch (error) { this.notification.add(error.data?.message || "The source register is unavailable.", {type: "danger"}); }
    }
    openOwnerFleet(filter = "all") {
        return this.action.doAction("ideastone_erp.action_fleet_management", {props: {initialFilter: filter}});
    }
    chartWidth(value, rows, field = "value") {
        const keys = Array.isArray(field) ? field : [field];
        const maximum = Math.max(1, ...rows.flatMap(row => keys.map(key => Math.abs(Number(row[key]) || 0))));
        return `${Math.abs(Number(value) || 0) / maximum * 100}%`;
    }
    number(value) { return new Intl.NumberFormat(undefined, {maximumFractionDigits: 2}).format(value); }
    get ownerUI() { return this.state.ownerMetrics.overview_ui || {kpis: [], activity: [], departments: [], funnel: [], events: [], insights: [], watchlist: []}; }
    get ownerYearLabel() { return this.state.ownerMetrics.years.find(year => String(year.id) === String(this.state.ownerAppliedFilters.year_id))?.name || "All academic years"; }
    async ownerPeriod(period) {
        const today = this.state.today;
        const semester = this.ownerUI.semester;
        if (period === "semester" && !semester) return;
        Object.assign(this.state.ownerFilters, {date_from: period === "today" ? today : period === "semester" ? semester.start : `${today.slice(0, 8)}01`,
            date_to: period === "semester" ? semester.end : today});
        await this.loadOwnerMetrics();
    }
    ownerPeriodSelected(period) {
        const f = this.state.ownerAppliedFilters, today = this.state.today;
        if (period === "today") return f.date_from === today && f.date_to === today;
        if (period === "month") return f.date_from === `${today.slice(0, 8)}01` && f.date_to === today && f.date_from !== today;
        return this.ownerUI.semester && f.date_from === this.ownerUI.semester.start && f.date_to === this.ownerUI.semester.end;
    }
    async ownerOverviewAction(kind, eventId = null) {
        try { await this.action.doAction(await this.orm.call("campus.dashboard", "get_owner_overview_action", [kind, this.state.ownerAppliedFilters, eventId])); }
        catch (error) { this.notification.add(error.data?.message || "This overview register is unavailable.", {type: "danger"}); }
    }
    ownerOpenAction(xmlid) {
        const item = this.state.navigation.find(row => row.action === xmlid);
        if (item) return this.open(item);
    }
    ownerCanOpen(xmlid) { return this.state.navigation.some(row => row.action === xmlid); }
    ownerPrint() { window.print(); }
    ownerMoney(value) { return `${this.ownerUI.currency_symbol || ""} ${this.number(value)}`.trim(); }
    ownerCompactMoney(value) {
        const magnitude = Math.abs(value);
        return `${this.ownerUI.currency_symbol || ""}${this.number(value / (magnitude >= 10000000 ? 10000000 : magnitude >= 100000 ? 100000 : 1))}${magnitude >= 10000000 ? "Cr" : magnitude >= 100000 ? "L" : ""}`;
    }
    ownerMonth(value) { return new Date(`${value.slice(0, 7)}-15T12:00:00Z`).toLocaleDateString(undefined, {month: "short", year: "2-digit", timeZone: "UTC"}); }
    ownerDay(value) { return value.slice(8, 10); }
    ownerMonthShort(value) { return new Date(`${value.slice(0, 10)}T12:00:00Z`).toLocaleDateString(undefined, {month: "short", timeZone: "UTC"}).toUpperCase(); }
    get ownerFunnel() {
        const total = this.ownerUI.funnel.reduce((sum, row) => sum + row.value, 0);
        let offset = 0;
        return this.ownerUI.funnel.map(row => { const ratio = total ? row.value / total : 0;
            const item = {...row, percent: ratio * 100, dash: `${ratio * 351.86} 351.86`, offset: -offset}; offset += ratio * 351.86; return item; });
    }
    ownerActivityPoints(field) {
        const rows = this.ownerUI.activity;
        return rows.map((row, i) => row[field] === null ? null : `${rows.length === 1 ? 320 : 55 + i * 530 / (rows.length - 1)},${190 - row[field] * 1.6}`)
            .reduce((parts, point) => { if (point === null) parts.push([]); else parts[parts.length - 1].push(point); return parts; }, [[]]).filter(part => part.length).map(part => part.join(" "));
    }
    get ownerQuickActions() {
        return [{label: "Review admissions", detail: "Applications & decisions", icon: "envelope-o", action: "ideastone_erp.mvp_applications"},
            {label: "Record a payment", detail: "Student fee accounts", icon: "inr", action: "ideastone_erp.action_owner_fees_overview"},
            {label: "Track attendance", detail: "Completed class registers", icon: "check", action: "ideastone_erp.mvp_attendance"},
            {label: "College calendar", detail: "Plan campus activities", icon: "calendar", action: "ideastone_erp.action_college_calendar"},
            {label: "Plan examinations", detail: "Schedules & marks", icon: "file-text-o", action: "ideastone_erp.mvp_exams"},
            {label: "Manage staff", detail: "Faculty directory", icon: "users", action: "ideastone_erp.action_owner_staff_directory"},
            {label: "Service desk", detail: "Open campus requests", icon: "flag-o", kind: "services", allowed: this.ownerUI.kpis.some(card => card.kind === "services" && card.allowed)},
            {label: "Build a report", detail: "Reports & analytics", icon: "bar-chart", module: "reports"}]
            .filter(item => item.action ? this.ownerCanOpen(item.action) : item.module ? this.state.faculty_modules.some(module => module.key === item.module) : item.allowed);
    }
    ownerQuick(item) { return item.action ? this.ownerOpenAction(item.action) : item.kind ? this.ownerOverviewAction(item.kind) : this.chooseModule({key: item.module}); }
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
    static components = { FacultyHome, FacultyDepartments, FacultyCommunication, FacultyCampusServices, OwnerSettings };
}
export class CampusNavigation extends CampusBase {
    static template = "ideastone_erp.Navigation";
    static props = ["*"];
    setup() {
        super.setup();
        this.navPreferences = useState({revision: 0, items: []});
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this.syncFacultyRoute());
        useEffect(() => {
            if (this.action.currentController?.action.tag?.includes("question_papers")) {
                this.subnavRef.el?.querySelector("button.active")?.scrollIntoView({block: "nearest", inline: "nearest"});
            }
        }, () => [this.state.activeAction, this.state.module, this.state.faculty_modules.length]);
        onWillUnmount(() => { document.body.classList.remove("campus_faculty_workspace"); this.navCustomizer?.close(); });
    }
    async load() {
        await super.load();
        document.body.classList.toggle("campus_faculty_workspace", this.state.faculty_modules.length > 0);
        this.syncFacultyRoute();
        try { Object.assign(this.navPreferences, await this.orm.call("res.users", "campus_get_navigation", [this.navigationScope])); }
        catch { /* Default navigation remains usable if preferences cannot load. */ }
    }
    get navigationScope() {
        return this.state.is_principal_workspace ? "principal" : this.state.is_coe_workspace ? "coe" : this.state.is_accountant_workspace ? "accountant" : this.state.is_owner_workspace ? "owner" : this.state.is_hod ? "hod" : this.state.faculty_modules.length ? "faculty" : "staff";
    }
    get navigationCatalog() {
        const catalog = [];
        if (this.state.faculty_modules.length) {
            for (const module of this.state.faculty_modules) {
                catalog.push({id: `module/${module.key}`, label: module.label, icon: module.icon, main: true, kind: "module", data: module});
                for (const item of module.items || []) {
                    const key = item.action || item.tool || (item.page && `page-${item.page}`) || (item.profile_id && "profile") || (item.url && "url");
                    if (!key || item.allowed === false) continue;
                    catalog.push({id: `item/${module.key}/${key}`, label: item.label, icon: module.icon, group: module.label, kind: "item", module: module.key, data: item});
                }
            }
        } else {
            for (const page of this.state.pages) catalog.push({id: `page/${page.key}`, label: page.label, icon: page.icon, main: true, kind: "page", data: page});
            for (const item of this.state.navigation.filter(item => item.allowed)) {
                catalog.push({id: `action/${item.action}`, label: item.label, icon: "folder-open-o", group: item.group, kind: "action", data: item});
            }
        }
        return [...new Map(catalog.map(item => [item.id, item])).values()];
    }
    get sidebarItems() {
        const catalog = this.navigationCatalog;
        return navigationItems(catalog, this.navPreferences.items).filter(row => row.visible && !row.removed).map(row => {
            const target = catalog.find(item => item.id === row.target);
            const active = target.kind === "module" ? this.state.module === target.data.key : target.kind === "page" ? this.state.page === target.data.key :
                this.state.module === target.module && (target.data.page?.startsWith("settings-") ? this.state.page === target.data.page : target.data.action_id ? this.state.activeAction === target.data.action_id : target.data.tool ? this.state.activeTool === target.data.tool : this.state.page === target.data.page);
            return {...row, icon: target.icon, active};
        });
    }
    async openSidebarItem(row) {
        const target = this.navigationCatalog.find(item => item.id === row.target);
        if (!target) return;
        if (target.kind === "module") return this.chooseModule(target.data);
        if (target.kind === "page") return this.go(target.data);
        if (target.kind === "action") return this.open(target.data);
        this.state.module = target.module;
        return this.facultyGo(target.data);
    }
    async customizeNavigation() {
        try {
            const scope = this.navigationScope;
            const preferences = await this.orm.call("res.users", "campus_get_navigation", [scope]);
            Object.assign(this.navPreferences, preferences);
            this.navCustomizer?.close();
            this.navCustomizer = new NavigationCustomizer({catalog: this.navigationCatalog, preferences,
                save: (items, revision) => this.orm.call("res.users", "campus_save_navigation", [scope, items, revision]),
                apply: saved => Object.assign(this.navPreferences, saved)});
            this.navCustomizer.open();
        } catch {
            this.notification.add("Navigation customization could not be loaded. Please retry.", {type: "danger"});
        }
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
