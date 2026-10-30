/** @odoo-module **/
import {Component, onWillStart, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

const META = {
    surveys: {
        title: "Surveys", sub: "Create feedback surveys and review participation, completion, and average response scores.",
        table: "Feedback surveys", desc: "Survey register with owner and response metrics.",
        columns: ["Survey title", "Responsible", "Average duration", "Registered", "Success ratio", "Average score", "Status"],
        statuses: ["Draft", "Open", "Published", "Closed"], nameLabel: "Survey title", ownerLabel: "Responsible person", dateLabel: "Survey date",
        notice: "Before publishing a survey, confirm the audience, closing date, and data-privacy wording.",
        insightTitle: "Survey engagement", insightIntro: "Review response rates and completion signals before sharing survey findings.",
        guidance: [["Follow up on low participation", "Check surveys with registrations but few completed responses."], ["Review response quality", "Use the average score alongside response count; small samples may not be representative."], ["Close the loop", "Share a brief summary of actions taken after collecting feedback."]],
    },
    events: {
        title: "Events and clubs", sub: "Coordinate campus events and clubs, manage venues and organisers, and monitor attendance.",
        table: "Events and clubs register", desc: "Event register showing venue, responsible person, dates, attendance, and current stage.",
        columns: ["Event", "Venue", "Responsible", "Start date", "End date", "Registered", "Attended", "Stage"],
        statuses: ["New", "Announced", "Booked", "In progress", "Ended", "Cancelled"], nameLabel: "Event title", ownerLabel: "Responsible organiser", dateLabel: "Start date",
        notice: "Confirm venue availability, accessibility, event approvals, and final attendance after each event.",
        insightTitle: "Event coordination", insightIntro: "Use the event register to identify upcoming activity and follow up on attendance records.",
        guidance: [["Upcoming event readiness", "Review venue and organiser details for booked events before the event date."], ["Attendance follow-up", "Record actual attendance after each event to improve future planning."], ["Publish event details", "Ensure event information and contact details are visible to the intended campus audience."]],
    },
    alumni: {
        title: "Alumni forums", sub: "Support alumni discussions, monitor forum activity, and maintain a helpful community knowledge base.",
        table: "Alumni forums", desc: "Forum register with website, post activity, and view totals.",
        columns: ["Forum name", "Website", "Posts", "Views", "Status"],
        statuses: ["Active", "Needs review", "Archived"], nameLabel: "Forum name", ownerLabel: "Forum moderator", dateLabel: "Review date",
        notice: "Follow campus moderation guidelines and avoid publishing personal or confidential information in forum posts.",
        insightTitle: "Alumni community activity", insightIntro: "The forum register identifies active topics and places where moderation or responses may be needed.",
        guidance: [["Review unanswered posts", "Check recent posts regularly and direct alumni questions to the appropriate department."], ["Keep forum details current", "Verify forum links and moderator ownership periodically."], ["Encourage constructive participation", "Use clear community guidelines and respond respectfully to alumni queries."]],
    },
};

export class FacultyCommunication extends Component {
    static template = "ideastone_erp.FacultyCommunication";
    static props = ["page"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({data: null, loading: true, error: "", query: "", status: "all", form: false, busy: false,
            values: {name: "", owner: "", date: "", status: "", description: ""}});
        onWillStart(() => this.load());
    }

    get kind() { return this.props.page.replace("communication-", ""); }
    get meta() { return META[this.kind] || META.surveys; }
    get rows() { return this.state.data?.rows?.[this.kind] || []; }
    get filtered() {
        const q = this.state.query.trim().toLowerCase();
        return this.rows.filter(row => (this.state.status === "all" || row.status === this.state.status) &&
            (!q || [row.name, row.owner, row.venue, row.website, row.status].join(" ").toLowerCase().includes(q)));
    }
    get stats() {
        const rows = this.rows, sum = key => rows.reduce((n, row) => n + Number(row[key] || 0), 0);
        if (this.kind === "surveys") return [
            {icon: "▤", label: "Surveys", value: rows.length, tone: "", note: "In this register"},
            {icon: "◎", label: "Registered", value: sum("registered"), tone: "green", note: "Across all surveys"},
            {icon: "◷", label: "Published / open", value: rows.filter(r => ["Published", "Open"].includes(r.status)).length, tone: "amber", note: "Available or collecting"},
            {icon: "✓", label: "Avg. success ratio", value: rows.length ? Math.round(sum("success") / rows.length) + "%" : "0%", tone: "violet", note: "Across recorded surveys"},
        ];
        if (this.kind === "events") return [
            {icon: "▦", label: "Events", value: rows.length, tone: "", note: "In this register"},
            {icon: "◷", label: "Upcoming / planned", value: rows.filter(r => ["New", "Announced", "Booked", "In progress"].includes(r.status)).length, tone: "amber", note: "Require coordination"},
            {icon: "◎", label: "Registered attendees", value: sum("registered"), tone: "green", note: "Across listed events"},
            {icon: "✓", label: "Ended events", value: rows.filter(r => r.status === "Ended").length, tone: "violet", note: "Attendance can be reviewed"},
        ];
        return [
            {icon: "◎", label: "Forums", value: rows.length, tone: "", note: "In this register"},
            {icon: "▤", label: "Posts", value: sum("posts"), tone: "green", note: "Across listed forums"},
            {icon: "◉", label: "Views", value: sum("views"), tone: "violet", note: "Recorded forum views"},
            {icon: "◷", label: "Needs review", value: rows.filter(r => r.status === "Needs review").length, tone: "amber", note: "Forum moderation"},
        ];
    }
    statusClass(status) {
        if (["Published", "Ended", "Active"].includes(status)) return "green";
        if (["Draft", "New", "Open", "Needs review"].includes(status)) return "amber";
        if (["Booked", "Announced", "In progress"].includes(status)) return "blue";
        return status === "Cancelled" ? "red" : "violet";
    }
    date(value) {
        return value ? new Date(`${value.slice(0, 10)}T12:00:00Z`).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric", timeZone: "UTC"}) : "—";
    }
    score(value) { return Number(value || 0).toFixed(2); }
    get newTitle() { return `Create ${this.meta.title.toLowerCase().replace(/s$/, "")} record`; }
    async load() {
        this.state.loading = true; this.state.error = "";
        try { this.state.data = await this.orm.call("campus.faculty.communication", "get_data", []); }
        catch (error) { this.state.error = error.data?.message || "Communication records could not be loaded."; }
        finally { this.state.loading = false; }
    }
    openForm() {
        this.state.form = true;
        this.state.values = {name: "", owner: "", date: this.state.data?.today || "", status: this.meta.statuses[0], description: ""};
    }
    cancel() { this.state.form = false; }
    resetFilters() { this.state.query = ""; this.state.status = "all"; }
    async save() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            await this.orm.call("campus.faculty.communication", "create_record", [this.kind, {...this.state.values}]);
            await this.load(); this.state.form = false; this.resetFilters();
            this.notification.add("Communication record saved.", {type: "success"});
        } catch (error) {
            this.notification.add(error.data?.message || "The record could not be saved.", {type: "danger"});
        } finally { this.state.busy = false; }
    }
}
