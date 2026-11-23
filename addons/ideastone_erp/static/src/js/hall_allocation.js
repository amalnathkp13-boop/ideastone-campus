/** @odoo-module **/

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const blankDetails = () => ({ programme: "", type: "", coordinator: "", attendees: "", requirements: "" });
const tone = status => ({ Available: "green", Approved: "green", Booked: "red", Pending: "amber", Rejected: "red", Cancelled: "blue" }[status] || "blue");

export class HallAllocation extends Component {
    static template = "ideastone_erp.HallAllocation";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null, stage: "schedule", loading: true, saving: false, error: "",
            schedule: { date: "", start: "", end: "" }, slot: null, selected: null,
            details: blankDetails(), filter: "all", feedback: "", dialog: null, confirmCancel: false });
        this.dialog = useRef("dialog");
        this.main = useRef("main");
        this.programme = useRef("programme");
        this.requestToken = crypto.randomUUID();
        useEffect(dialog => {
            if (dialog && !dialog.open) dialog.showModal();
        }, () => [this.dialog.el]);
        useEffect(input => input?.focus({ preventScroll: true }), () => [this.programme.el]);
        onWillStart(() => this.load());
    }

    async load(slot = this.state.slot) {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("campus.hod.hall.ui", "get_workspace", [slot]);
            return true;
        } catch (error) {
            this.state.error = error.data?.message || "Hall availability could not be loaded. Please retry.";
            return false;
        } finally { this.state.loading = false; }
    }

    stage(value) {
        this.state.stage = value;
        this.state.error = "";
        this.main.el?.scrollTo({ top: 0 });
    }
    async availability() {
        const slot = { ...this.state.schedule };
        if (!slot.date || !slot.start || !slot.end || slot.start >= slot.end) {
            this.state.error = "Choose a valid date and an end time later than the start time.";
            return;
        }
        if (await this.load(slot)) {
            this.state.slot = slot;
            this.state.selected = null;
            this.state.feedback = "";
            this.stage("results");
        }
    }
    reset() {
        this.state.schedule = { date: "", start: "", end: "" };
        this.state.slot = null;
        this.state.selected = null;
        this.state.details = blankDetails();
        this.state.feedback = "";
        this.requestToken = crypto.randomUUID();
        this.stage("schedule");
    }
    editSlot() {
        this.state.selected = null;
        this.state.slot = null;
        this.state.feedback = "";
        this.requestToken = crypto.randomUUID();
        this.stage("schedule");
    }
    select(hall) {
        if (hall.status !== "Available") return;
        this.state.selected = hall.id;
        if (Number(this.state.details.attendees) > hall.capacity) this.state.details.attendees = "";
        this.requestToken = crypto.randomUUID();
        this.stage("booking");
    }
    clearDetails() { this.state.details = blankDetails(); this.state.error = ""; }
    changeHall() { this.state.selected = null; this.stage("results"); }
    async history() {
        if (await this.load()) {
            this.state.feedback = "";
            this.stage("history");
        }
    }

    get halls() {
        const slot = this.state.slot;
        return (this.state.data?.halls || []).map(hall => {
            const conflicts = slot ? this.state.data.bookings.filter(row => row.hall_id === hall.id
                && row.date === slot.date && row.start < slot.end && slot.start < row.end) : [];
            const booking = conflicts.find(row => row.status === "Approved") || conflicts[0];
            return { ...hall, booking, status: booking ? booking.status === "Approved" ? "Booked" : "Pending" : "Available" };
        }).sort((a, b) => Number(b.status === "Available") - Number(a.status === "Available"));
    }
    get selected() { return this.halls.find(hall => hall.id === this.state.selected); }
    get groups() {
        return [
            { title: "Available halls", halls: this.halls.filter(hall => hall.status === "Available") },
            { title: "Unavailable halls · booked or on hold", halls: this.halls.filter(hall => hall.status !== "Available") },
        ].filter(group => group.halls.length);
    }
    get kpis() {
        return [
            { label: "Available halls", value: this.halls.filter(hall => hall.status === "Available").length, note: "Free for selected slot", icon: "available", tone: "blue" },
            { label: "Already booked", value: this.halls.filter(hall => hall.status === "Booked").length, note: "Confirmed overlapping events", icon: "lock", tone: "red" },
            { label: "Pending holds", value: this.halls.filter(hall => hall.status === "Pending").length, note: "Halls temporarily reserved", icon: "clock", tone: "amber" },
            { label: "My pending requests", value: this.state.data.requests.filter(row => row.status === "Pending").length,
                note: this.state.data.department, icon: "request", tone: "green" },
        ];
    }
    get filteredRequests() {
        return this.state.data.requests.filter(row => this.state.filter === "all" || row.status === this.state.filter);
    }
    get scheduleRows() {
        return this.state.data.bookings.filter(row => row.hall_id === this.state.dialog.hall.id)
            .sort((a, b) => a.start.localeCompare(b.start));
    }
    get requestFields() {
        const row = this.state.dialog.request;
        return [
            ["Request ID", row.reference], ["Programme", row.programme], ["Programme type", row.type],
            ["Department", row.department], ["Hall", row.hall], ["Date", this.date(row.date)],
            ["Time", this.timeRange(row.start, row.end)], ["Attendees", row.attendees],
            ["Coordinator", row.coordinator], ["Requirements", row.requirements || "None"], ["Status", row.status],
            ...(row.reason ? [["Reason", row.reason]] : []),
        ];
    }

    async submit() {
        if (this.state.saving) return;
        this.state.saving = true;
        this.state.error = "";
        try {
            const row = await this.orm.call("campus.hod.hall.ui", "submit", [{
                ...this.state.details, attendees: Number(this.state.details.attendees), slot: this.state.slot,
                hall_id: this.state.selected, token: this.requestToken,
            }]);
            this.state.filter = "all";
            this.state.selected = null;
            this.state.slot = null;
            this.state.details = blankDetails();
            this.requestToken = crypto.randomUUID();
            this.stage("history");
            this.state.feedback = `${row.reference} submitted for approval. The requested slot is now on hold.`;
            await this.load();
        } catch (error) {
            this.state.error = error.data?.message || "The request could not be submitted. Please retry.";
            await this.load();
            if (this.selected?.status !== "Available") {
                this.state.selected = null;
                this.state.stage = "results";
            }
        } finally { this.state.saving = false; }
    }

    async showSchedule(hall) {
        this.state.error = "";
        if (await this.load()) {
            this.state.dialog = { hall };
            this.state.confirmCancel = false;
        }
    }
    details(row) {
        this.state.dialog = { request: row };
        this.state.confirmCancel = false;
    }
    closeDialog() { this.state.dialog = null; this.state.confirmCancel = false; }
    backdrop(event) { if (event.target === event.currentTarget) this.closeDialog(); }
    keys(event) {
        if (event.key === "Escape" && this.state.dialog) {
            event.preventDefault();
            event.stopPropagation();
            this.closeDialog();
        }
    }
    async cancel() {
        if (!this.state.confirmCancel) { this.state.confirmCancel = true; return; }
        if (this.state.saving) return;
        this.state.saving = true;
        try {
            const row = this.state.dialog.request;
            await this.orm.call("campus.hod.hall.ui", "cancel", [row.id]);
            this.closeDialog();
            this.state.feedback = `${row.reference} cancelled. Its temporary hold has been released.`;
            await this.load();
        } catch (error) {
            this.state.error = error.data?.message || "The cancellation could not be saved. Please retry.";
        } finally { this.state.saving = false; }
    }

    tone(status) { return tone(status); }
    date(value) {
        return new Date(value + "T12:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
    }
    time(value) {
        const [hour, minutes] = value.split(":").map(Number);
        return `${hour % 12 || 12}:${String(minutes).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
    }
    timeRange(start, end) { return `${this.time(start)} – ${this.time(end)}`; }
}
registry.category("actions").add("ideastone_erp.hod_hall_allocation", HallAllocation);
