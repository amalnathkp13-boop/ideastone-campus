/** @odoo-module **/
import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const SUGGESTIONS = [
    "How is fee collection going this month compared with outstanding dues?",
    "Which programme has the most active students?",
    "How many students need attention right now and what is driving it?",
    "Summarise this period's admissions funnel in three lines.",
];

export class CampusAssistantPage extends Component {
    static template = "ideastone_ai.CampusAssistantPage";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.suggestions = SUGGESTIONS;
        this.periodRequest = 0;
        this.state = useState({
            loading: true, error: "", status: null, tab: "ask", busy: false,
            question: "", answers: [],
            brief: "", audience: "all", tone: "formal", notice: null,
            period: "", periods: [], kind: "student", feedback: null, periodsLoading: false,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.status = await this.orm.call("campus.ai.assistant", "get_status", []);
            this.state.periods = await this.orm.call("campus.ai.assistant", "feedback_periods", [this.state.kind]);
        } catch (error) {
            this.state.error = error.data?.message || "The Campus Assistant could not be loaded.";
        } finally {
            this.state.loading = false;
        }
    }

    selectTab(tab) { this.state.tab = tab; }
    async fail(error, fallback) {
        this.notification.add(error.data?.message || fallback, { type: "danger", sticky: true });
        try { this.state.status = await this.orm.call("campus.ai.assistant", "get_status", []); } catch {}
    }

    async ask(event) {
        event?.preventDefault();
        const question = this.state.question.trim();
        if (!question || this.state.busy) return;
        this.state.busy = true;
        try {
            const result = await this.orm.call("campus.ai.assistant", "ask", [question]);
            this.state.answers.unshift({ question, answer: result.answer, period: result.period, shared: result.shared });
            this.state.question = "";
            this.state.status.used += 1;
        } catch (error) {
            await this.fail(error, "The assistant could not answer.");
        } finally {
            this.state.busy = false;
        }
    }
    useSuggestion(text) { this.state.question = text; }

    async draft(event) {
        event?.preventDefault();
        if (!this.state.brief.trim() || this.state.busy) return;
        this.state.busy = true;
        try {
            const notice = await this.orm.call("campus.ai.assistant", "draft_notice", [this.state.brief.trim(), this.state.audience, this.state.tone]);
            // body_html is built server-side from escaped text, so it is safe to render as markup.
            this.state.notice = { ...notice, body_html: markup(notice.body_html) };
            this.state.status.used += 1;
        } catch (error) {
            await this.fail(error, "The notice could not be drafted.");
        } finally {
            this.state.busy = false;
        }
    }
    async createCircular() {
        if (this.state.notice?.create_action) await this.action.doAction(this.state.notice.create_action);
    }
    async copyNotice() {
        try {
            await navigator.clipboard.writeText((this.state.notice.title ? this.state.notice.title + "\n\n" : "") + this.state.notice.body_text);
            this.notification.add("Notice copied.", { type: "success" });
        } catch {
            this.notification.add("Select the text and copy it manually.", { type: "warning" });
        }
    }

    async changeKind(event) {
        const request = ++this.periodRequest;
        this.state.kind = event.target.value;
        this.state.period = "";
        this.state.periods = [];
        this.state.feedback = null;
        this.state.periodsLoading = true;
        try {
            const periods = await this.orm.call("campus.ai.assistant", "feedback_periods", [this.state.kind]);
            if (request === this.periodRequest) this.state.periods = periods;
        } catch (error) {
            if (request === this.periodRequest) await this.fail(error, "Feedback periods could not be loaded.");
        } finally {
            if (request === this.periodRequest) this.state.periodsLoading = false;
        }
    }
    async summarise(event) {
        event?.preventDefault();
        if (this.state.busy || this.state.periodsLoading) return;
        this.state.busy = true;
        try {
            this.state.feedback = await this.orm.call("campus.ai.assistant", "summarise_feedback", [this.state.period || false, this.state.kind]);
            this.state.status.used += 1;
        } catch (error) {
            await this.fail(error, "Feedback could not be summarised.");
        } finally {
            this.state.busy = false;
        }
    }
    async openSettings() {
        await this.action.doAction("ideastone_erp.mvp_college");
    }
}

registry.category("actions").add("ideastone_ai.assistant", CampusAssistantPage);
