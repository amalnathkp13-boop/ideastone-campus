/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PrincipalWorkspace extends Component {
    static template = "ideastone_principal.Workspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.view = this.props.action.params?.view || "overview";
        this.state = useState({loading: true, error: "", data: null});
        onWillStart(() => this.load());
    }
    get title() {
        return {overview: "Principal overview", decisions: "Decisions", notices: "Notices & circulars"}[this.view];
    }
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("ideastone.principal.dashboard", "get_overview", []);
        } catch {
            this.state.error = "Principal records could not be loaded. Check access and retry.";
        } finally {
            this.state.loading = false;
        }
    }
    openModule(action) {
        return this.action.doAction(action, {additionalContext: {campus_workspace_role: "Principal"}});
    }
    openRequest(id) {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "ideastone.principal.request",
            res_id: id, views: [[false, "form"]], target: "current"});
    }
    openNotice(id) {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "ideastone.principal.notice",
            res_id: id, views: [[false, "form"]], target: "current"});
    }
    openStudentLeave(id) {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "campus.student.leave",
            res_id: id, views: [[false, "form"]], target: "current"});
    }
}
registry.category("actions").add("ideastone_principal.workspace", PrincipalWorkspace);
