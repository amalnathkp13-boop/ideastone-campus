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
        this.state = useState({loading: true, error: "", data: null, period: 6, showPlan: false});
        onWillStart(() => this.load());
    }
    get title() {
        return {overview: "Principal overview", decisions: "Decisions", notices: "Notices & circulars"}[this.view];
    }
    get trendRows() {
        return (this.state.data?.dashboard?.trend || []).slice(-this.state.period);
    }
    percent(value) {
        return value === null || value === undefined ? "—" : `${value}%`;
    }
    barHeight(value) {
        return `height: ${Math.max(0, Math.min(100, value || 0))}%`;
    }
    barWidth(value) {
        return `width: ${Math.max(0, Math.min(100, value || 0))}%`;
    }
    donutStyle(outcomes) {
        const total = outcomes.total || 1;
        const placed = outcomes.placed * 100 / total;
        const studies = placed + outcomes.higher_studies * 100 / total;
        const seeking = studies + outcomes.seeking * 100 / total;
        return `background: conic-gradient(#1769e8 0 ${placed}%, #36a3f7 ${placed}% ${studies}%, #35b98b ${studies}% ${seeking}%, #f2b34b ${seeking}% 100%)`;
    }
    monthLabel(month) {
        return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(month.slice(5, 7)) - 1];
    }
    choosePeriod(event) {
        this.state.period = Number(event.target.value);
    }
    togglePlan() {
        this.state.showPlan = !this.state.showPlan;
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
