/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OwnerSettings extends Component {
    static template = "ideastone_erp.OwnerSettings";
    static props = ["screen", "openPage"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({loading: true, saving: false, error: "", search: "", filename: "", data: {}, form: {}});
        onWillStart(() => this.load());
    }

    get screen() { return this.props.screen.replace("settings-", ""); }
    get title() {
        return {overview: "Settings", college: "College profile & policy", documents: "Document requirements",
            catalogue: "Student request catalogue", audit: "Audit log", users: "Users & roles",
            numbering: "ID & receipt numbering", import: "Import students"}[this.screen] || "Settings";
    }
    get description() {
        return {overview: "Manage core college configuration, access controls and operational policies from one place.",
            college: "Maintain official institution details and attendance/OD rules.",
            documents: "Define required documents, optionally by programme.",
            catalogue: "Control which request types students can submit through the portal.",
            audit: "Review who changed important records, when and which record was affected.",
            users: "Control who can access the ERP and what actions each role may perform.",
            numbering: "Manage prefixes and sequences used for student, invoice and receipt references.",
            import: "Upload a CSV, map required columns and validate rows before committing records."}[this.screen] || "";
    }
    get data() { return this.state.data; }
    get confirmedUsers() { return (this.data.users || []).filter(row => row.confirmed && row.active).length; }
    get adminUsers() { return (this.data.users || []).filter(row => row.active && row.role === "Owner / Admin").length; }
    get activeUsers() { return (this.data.users || []).filter(row => row.active).length; }
    get activeRequirements() { return (this.data.requirements || []).filter(row => row.active); }
    get actors() { return new Set((this.data.audits || []).map(row => row.actor)).size; }
    get configurationChanges() { return (this.data.audits || []).filter(row => /configur|policy|setting/i.test(row.action)).length; }
    get filteredRows() {
        const rows = {documents: this.data.requirements, catalogue: this.data.request_types, audit: this.data.audits,
            users: this.data.users, numbering: this.data.sequences}[this.screen] || [];
        const query = this.state.search.trim().toLowerCase();
        return query ? rows.filter(row => Object.values(row).join(" ").toLowerCase().includes(query)) : rows;
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.dashboard", "get_owner_settings", []);
            this.state.form = {...this.state.data.company};
        } catch (error) {
            this.state.error = error.data?.message || "Settings could not be loaded. Check your access and retry.";
        } finally {
            this.state.loading = false;
        }
    }

    async save() {
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            const fields = ["name", "street", "city", "phone", "email", "campus_attendance_threshold",
                "campus_excused_policy", "campus_od_default_tokens", "campus_od_token_rule",
                "campus_student_portal_enabled", "campus_student_contact_edit"];
            const values = Object.fromEntries(fields.map(key => [key, this.state.form[key]]));
            values.campus_attendance_threshold = Number(values.campus_attendance_threshold);
            values.campus_od_default_tokens = Number(values.campus_od_default_tokens);
            if (!Number.isFinite(values.campus_attendance_threshold) || !Number.isInteger(values.campus_od_default_tokens)) throw Error("Enter valid policy numbers.");
            await this.orm.call("campus.dashboard", "save_owner_settings", [values]);
            await this.load();
            this.notification.add("College settings saved.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || error.message || "Settings were not saved.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    async openAction(xmlid, id = null, create = false) {
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_action", [xmlid]);
            if (id || create) {
                action.view_mode = "form";
                action.views = [[false, "form"]];
                if (id) action.res_id = id;
                else delete action.res_id;
            }
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || "This register could not be opened.", {type: "danger"});
        }
    }

    async openStudentRequest(id) {
        try {
            const action = await this.orm.call("campus.dashboard", "get_owner_action", ["ideastone_erp.mvp_student_requests"]);
            action.res_id = id;
            action.view_mode = "form";
            action.views = [[false, "form"]];
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(error.data?.message || "The student request could not be opened.", {type: "danger"});
        }
    }

    downloadTemplate() {
        const csv = "student_number,first_name,last_name,phone,section_code\n";
        const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
        const link = document.createElement("a");
        link.href = url;
        link.download = "student-import-template.csv";
        link.click();
        URL.revokeObjectURL(url);
    }

    onFileChange(event) {
        this.importFile = event.target.files?.[0] || null;
        this.state.filename = this.importFile?.name || "";
    }

    async previewImport() {
        if (this.state.saving) return;
        if (!this.importFile) {
            this.notification.add("Choose a CSV file first.", {type: "warning"});
            return;
        }
        if (this.importFile.size > 2_000_000) {
            this.notification.add("Choose a CSV file smaller than 2 MB.", {type: "warning"});
            return;
        }
        this.state.saving = true;
        try {
            const content = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result).split(",")[1]);
                reader.onerror = reject;
                reader.readAsDataURL(this.importFile);
            });
            const ids = await this.orm.create("campus.student.import", [{
                company_id: this.data.company.id, file: content, filename: this.importFile.name,
            }]);
            await this.orm.call("campus.student.import", "action_preview", [ids]);
            await this.action.doAction({
                type: "ir.actions.act_window", res_model: "campus.student.import",
                res_id: ids[0], views: [[false, "form"]], target: "current",
            });
        } catch (error) {
            this.notification.add(error.data?.message || error.message || "The CSV could not be validated.", {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }
}
