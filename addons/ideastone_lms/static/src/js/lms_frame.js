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
        this.state = useState({ url: "/lms/", loaded: false });
        onWillStart(async () => {
            const params = await this.orm.call("ir.config_parameter", "get_param", ["ideastone.lms_url", "/lms/"]);
            this.state.url = params || "/lms/";
        });
    }

    onLoad() {
        this.state.loaded = true;
    }

    openInNewTab() {
        window.open(this.state.url, "_blank");
    }
}

registry.category("actions").add("ideastone_lms.lms_frame", LmsFrame);
