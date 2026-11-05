/** @odoo-module **/
import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class ComplaintsWorkspace extends Component {
    static template = "ideastone_erp.ComplaintsWorkspace";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.page = this.props.action.params?.page || "dashboard";
        this.state = useState({
            loading: true, busy: false, error: "", data: null, filter: "all", query: "",
            selectedId: 0, showForm: false, note: "", assignee: "", routeCategory: "", routeUser: "",
            form: {subject: "", description: "", kind: "complaint", category: "infrastructure",
                location: "", incident_date: "", target_user_id: "", student_number: "",
                anonymous_to_respondent: true, evidence: "", evidence_filename: ""},
        });
        onWillStart(() => this.load());
    }

    get title() {
        return {dashboard: "Complaints", students: "Student complaints", staff: "Staff complaints"}[this.page];
    }
    get selected() { return this.state.data?.rows.find(row => row.id === this.state.selectedId); }
    get rows() {
        const query = this.state.query.trim().toLowerCase();
        return (this.state.data?.rows || []).filter(row =>
            (this.state.filter === "all" || (this.state.filter === "mine" && row.mine) ||
             (this.state.filter === "about" && row.about_me) ||
             (this.state.filter === "assigned" && row.assigned_to_me)) &&
            (!query || [row.reference, row.subject, row.category, row.concerned].some(value =>
                String(value || "").toLowerCase().includes(query))));
    }
    get canSubmit() { return Boolean(this.state.data && !this.state.data.owner); }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.complaints.ui", "get_page_data", [this.page]);
            if (this.state.selectedId && !this.selected) this.state.selectedId = 0;
        } catch (error) {
            this.state.error = error.data?.message || "Complaints could not be loaded. Please retry.";
        } finally {
            this.state.loading = false;
        }
    }
    select(row) {
        this.state.selectedId = row.id;
        this.state.note = "";
        this.state.assignee = "";
    }
    caseKeydown(event, row) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.select(row);
        }
    }
    async evidenceChanged(event) {
        const file = event.target.files?.[0];
        if (!file) {
            this.state.form.evidence = "";
            this.state.form.evidence_filename = "";
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            this.notification.add("Evidence must be at most 5 MB.", {type: "danger"});
            event.target.value = "";
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            this.state.form.evidence = String(reader.result).split(",", 2)[1] || "";
            this.state.form.evidence_filename = file.name;
        };
        reader.readAsDataURL(file);
    }
    async submit() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const result = await this.orm.call("campus.complaints.ui", "submit", [{...this.state.form}]);
            this.state.form = {subject: "", description: "", kind: "complaint", category: "infrastructure",
                location: "", incident_date: "", target_user_id: "", student_number: "",
                anonymous_to_respondent: true, evidence: "", evidence_filename: ""};
            this.state.showForm = false;
            this.notification.add(result.reference + " submitted.", {type: "success"});
            await this.load();
            this.state.selectedId = result.id;
        } catch (error) {
            this.notification.add(error.data?.message || "Complaint could not be submitted.", {type: "danger"});
        } finally { this.state.busy = false; }
    }
    async act(operation) {
        if (this.state.busy || !this.selected) return;
        this.state.busy = true;
        try {
            const values = operation === "assign" ? {user_id: this.state.assignee} :
                operation === "resolve" ? {resolution: this.state.note} : {note: this.state.note};
            await this.orm.call("campus.complaints.ui", "act", [this.selected.id, operation, values]);
            this.state.note = "";
            this.state.assignee = "";
            this.notification.add("Case updated.", {type: "success"});
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Case update was not saved.", {type: "danger"});
        } finally { this.state.busy = false; }
    }
    async saveRoute() {
        if (this.state.busy || !this.state.routeCategory || !this.state.routeUser) return;
        this.state.busy = true;
        try {
            await this.orm.call("campus.complaints.ui", "save_route", [this.state.routeCategory, this.state.routeUser]);
            this.notification.add("Category in-charge saved.", {type: "success"});
            this.state.routeCategory = "";
            this.state.routeUser = "";
            await this.load();
        } catch (error) {
            this.notification.add(error.data?.message || "Routing could not be saved.", {type: "danger"});
        } finally { this.state.busy = false; }
    }
    async downloadEvidence() {
        if (!this.selected) return;
        try {
            const result = await this.orm.call("campus.complaints.ui", "evidence", [this.selected.id]);
            const bytes = Uint8Array.from(atob(result[0]), char => char.charCodeAt(0));
            const blob = new Blob([bytes], {type: "application/octet-stream"});
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url; anchor.download = result[1]; anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch {
            this.notification.add("Evidence is not available to this account.", {type: "danger"});
        }
    }
    openEarlier(kind) {
        return this.action.doAction(kind === "feedback" ?
            "ideastone_erp.action_feedback" : "ideastone_erp.action_service_request");
    }
}

registry.category("actions").add("ideastone_erp.complaints", ComplaintsWorkspace);
