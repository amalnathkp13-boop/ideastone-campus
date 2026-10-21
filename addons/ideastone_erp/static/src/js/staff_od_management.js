/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class StaffODManagement extends Component {
    static template = "ideastone_erp.StaffODManagement";
    static props = ["*"];
}

registry.category("actions").add("ideastone_erp.staff_od_management", StaffODManagement);
