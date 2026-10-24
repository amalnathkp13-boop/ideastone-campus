/** @odoo-module **/

import { titleService } from "@web/core/browser/title_service";
import { registry } from "@web/core/registry";

registry.category("services").add("title", {
    ...titleService,
    start(...args) {
        const service = titleService.start(...args);
        const setParts = service.setParts;
        service.setParts = (parts) => {
            setParts(parts);
            document.title = "erp.vcet";
        };
        return service;
    },
}, { force: true });
