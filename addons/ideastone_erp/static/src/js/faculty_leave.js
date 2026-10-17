/** @odoo-module **/
import { Component, useExternalListener, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DASHBOARD_DESTINATIONS = {
    "Home": ["overview", "home"],
    "Search": ["modules", "search"],
    "Library": ["faculty-module", "library"],
    "Grievance & Others": ["faculty-module", "grievances"],
    "Reports": ["reports", "reports"],
    "Dashboard": ["analytics", "analytics"],
    "Hostel": ["faculty-module", "hostel"],
    "Services": ["faculty-module", "services"],
    "Help": ["help", "help"],
};

export class FacultyLeavePage extends Component {
    static template = "ideastone_erp.FacultyLeavePage";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.user = useService("user");
        this.frame = useRef("leaveFrame");
        useExternalListener(window, "message", (event) => this.onMessage(event));
    }

    async onMessage(event) {
        if (event.origin !== window.location.origin || event.source !== this.frame.el?.contentWindow ||
            event.data?.type !== "vcet-leave:navigate") return;
        const module = event.data.module;
        if (module === "My Task List") {
            await this.action.doAction("ideastone_erp.action_faculty_task");
        } else if (module === "My Profile") {
            await this.action.doAction("ideastone_erp.action_faculty_detail");
        } else if (module === "Account Settings") {
            await this.action.doAction({type: "ir.actions.act_window", name: "My account",
                res_model: "res.users", res_id: this.user.userId, views: [[false, "form"]]});
        } else if (DASHBOARD_DESTINATIONS[module]) {
            const [page, area] = DASHBOARD_DESTINATIONS[module];
            await this.action.doAction("ideastone_erp.action_dashboard", {
                additionalContext: {campus_page: page, campus_module: area},
            });
        }
    }
}

registry.category("actions").add("ideastone_erp.faculty_leave_page", FacultyLeavePage);
