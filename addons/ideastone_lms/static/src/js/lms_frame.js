/** @odoo-module **/
// Opens the OpenOlat LMS inside the Odoo web client (same browser session, same SSO).
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class LmsFrame extends Component {
    static template = "ideastone_lms.LmsFrame";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ url: "", loaded: false, error: "" });
        onWillStart(() => this.loadConfiguration());
    }

    async loadConfiguration() {
        this.state.error = "";
        this.state.loaded = false;
        try {
            const configuration = await this.orm.call("ideastone.lms.workspace", "configuration", []);
            this.state.url = configuration.url;
        } catch (error) {
            this.state.error = error.data?.message || "Learning configuration could not be loaded. Contact your college administrator or retry.";
        }
    }

    onLoad() {
        this.state.loaded = true;
    }

    openInNewTab() {
        window.open(this.state.url, "_blank", "noopener,noreferrer");
    }
}

registry.category("actions").add("ideastone_lms.lms_frame", LmsFrame);
