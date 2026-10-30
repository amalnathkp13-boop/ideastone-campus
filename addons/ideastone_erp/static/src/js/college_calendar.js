/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const CATEGORIES = [
    ["academic", "Academic"], ["cultural", "Cultural & campus life"],
    ["exam", "Examination / deadline"], ["holiday", "Holiday / observance"],
    ["workshop", "Workshop / professional"],
];
const STATUSES = [["planning", "Planning"], ["upcoming", "Upcoming"], ["completed", "Completed"]];
const parseDate = value => new Date(`${value}T12:00:00`);
const dateKey = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export class CollegeCalendarForm extends Component {
    static template = "ideastone_erp.CollegeCalendarForm";
    static components = { Dialog };
    static props = ["close", "event?", "date", "onSaved"];
    setup() {
        this.orm = useService("orm"); this.nextKey = 0;
        const event = this.props.event;
        this.state = useState({busy: false, error: "", form: {
            name: event?.name || "", category: event?.category || "academic", status: event?.status || "planning",
            date_start: event?.date_start || this.props.date, date_end: event?.date_end || "",
            time: event?.time || "", venue: event?.venue || "", organizer: event?.organizer || "",
            contact: event?.contact || "", audience: event?.audience || "All campus", description: event?.description || "",
        }, schedule: (event?.schedule || []).map(row => ({...row, key: this.nextKey++}))});
    }
    get categories() { return CATEGORIES; }
    get statuses() { return STATUSES; }
    addSchedule() { this.state.schedule.push({key: this.nextKey++, time: "", title: ""}); }
    removeSchedule(key) { this.state.schedule = this.state.schedule.filter(row => row.key !== key); }
    async save(ev) {
        ev.preventDefault();
        if (this.state.busy) return;
        const form = this.state.form;
        this.state.error = "";
        if (!form.name.trim()) { this.state.error = "Enter an event title."; return; }
        if (form.date_end && form.date_end < form.date_start) {
            this.state.error = "The end date must be on or after the start date."; return;
        }
        if (this.state.schedule.some(row => !row.time.trim() || !row.title.trim())) {
            this.state.error = "Enter a time and activity for each schedule entry, or remove the empty entry."; return;
        }
        this.state.busy = true;
        try {
            const values = {...form, name: form.name.trim(), date_end: form.date_end || form.date_start,
                schedule: this.state.schedule.map(({time, title}) => ({time: time.trim(), title: title.trim()}))};
            let id = this.props.event?.id;
            if (id) await this.orm.write("campus.calendar.event", [id], values);
            else [id] = await this.orm.create("campus.calendar.event", [values]);
            await this.props.onSaved(id);
            this.props.close();
        } catch (error) { this.state.error = error.data?.message || "The event could not be saved. Please retry."; }
        finally { this.state.busy = false; }
    }
}

export class CollegeCalendar extends Component {
    static template = "ideastone_erp.CollegeCalendar";
    static props = ["*"];
    setup() {
        this.orm = useService("orm"); this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({data: null, loading: true, error: "", shown: "", selectedDate: "", selectedId: null,
            category: "all", status: "all", query: "", view: "month", reminderBusy: false});
        onWillStart(() => this.load());
    }
    get categories() { return CATEGORIES; }
    get statuses() { return STATUSES; }
    get weekdays() { return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]; }
    get events() { return this.state.data?.events || []; }
    get filtered() {
        const s = this.state, query = s.query.trim().toLowerCase();
        return this.events.filter(event => (s.category === "all" || event.category === s.category)
            && (s.status === "all" || event.status === s.status)
            && (!query || [event.name, event.organizer, event.venue, event.description, event.contact, event.audience]
                .filter(Boolean).join(" ").toLowerCase().includes(query)));
    }
    get monthStart() { return `${this.state.shown}-01`; }
    get monthEnd() {
        const date = parseDate(this.monthStart);
        return dateKey(new Date(date.getFullYear(), date.getMonth() + 1, 0, 12));
    }
    get monthLabel() { return parseDate(this.monthStart).toLocaleDateString("en-US", {month: "long", year: "numeric"}); }
    get monthEvents() { return this.filtered.filter(event => event.date_start <= this.monthEnd && event.date_end >= this.monthStart); }
    get stats() {
        const events = this.filtered;
        return [
            {label: "This month", value: this.monthEvents.length, help: `Events scheduled in ${this.monthLabel}`, icon: "▦", tone: ""},
            {label: "Upcoming", value: events.filter(e => e.date_end >= this.state.data.today && e.status !== "completed").length, help: "Future events and deadlines", icon: "◷", tone: ""},
            {label: "Completed", value: events.filter(e => e.status === "completed").length, help: "Completed campus activities", icon: "✓", tone: "green"},
            {label: "Needs coordination", value: events.filter(e => e.status === "planning").length, help: "Planning or venue confirmation", icon: "!", tone: "amber"},
        ];
    }
    get days() {
        const start = parseDate(this.monthStart);
        start.setDate(start.getDate() - start.getDay());
        return Array.from({length: 42}, (_, i) => {
            const date = new Date(start); date.setDate(start.getDate() + i);
            const key = dateKey(date);
            return {key, day: date.getDate(), outside: key.slice(0, 7) !== this.state.shown,
                today: key === this.state.data.today, selected: key === this.state.selectedDate,
                events: this.filtered.filter(event => event.date_start <= key && event.date_end >= key)};
        });
    }
    get recentEvents() {
        const list = this.filtered, today = this.state.data.today;
        const upcoming = list.filter(e => e.date_end >= today && e.status !== "completed");
        const past = list.filter(e => !upcoming.includes(e)).reverse();
        return [...upcoming, ...past].slice(0, 6);
    }
    get selected() { return this.filtered.find(e => e.id === this.state.selectedId); }
    categoryName(value) { return CATEGORIES.find(row => row[0] === value)?.[1] || ""; }
    statusName(value) { return STATUSES.find(row => row[0] === value)?.[1] || ""; }
    day(value) { return parseDate(value).getDate(); }
    month(value) { return parseDate(value).toLocaleDateString("en-US", {month: "short"}); }
    formatDate(value) { return parseDate(value).toLocaleDateString("en-GB", {day: "2-digit", month: "short", year: "numeric"}); }
    async load() {
        if (this.state.loading && this.state.data) return;
        this.state.loading = true; this.state.error = "";
        try {
            this.state.data = await this.orm.call("campus.calendar.event", "get_workspace", []);
            if (!this.state.shown) this.state.shown = this.state.data.today.slice(0, 7);
            if (!this.state.selectedDate) this.state.selectedDate = this.state.data.today;
        } catch (error) { this.state.error = error.data?.message || "Calendar events could not be loaded. Please retry."; }
        finally { this.state.loading = false; }
    }
    moveMonth(delta) {
        const date = parseDate(this.monthStart); date.setMonth(date.getMonth() + delta);
        this.state.shown = dateKey(date).slice(0, 7); this.state.selectedId = null; this.state.selectedDate = "";
    }
    today() {
        this.state.shown = this.state.data.today.slice(0, 7);
        this.selectDate(this.state.data.today);
    }
    selectDate(date) {
        this.state.selectedDate = date; this.state.shown = date.slice(0, 7);
        this.state.selectedId = this.filtered.find(e => e.date_start <= date && e.date_end >= date)?.id || null;
    }
    selectEvent(event) {
        this.state.selectedDate = event.date_start; this.state.selectedId = event.id;
        this.state.shown = event.date_start.slice(0, 7);
    }
    clearSelection() { this.state.selectedId = null; this.state.selectedDate = ""; }
    edit(event = null) {
        this.dialog.add(CollegeCalendarForm, {event, date: this.state.selectedDate || this.state.data.today,
            onSaved: async id => {
                await this.load();
                const saved = this.events.find(row => row.id === id);
                if (saved) {
                    this.state.category = "all"; this.state.status = "all"; this.state.query = "";
                    this.selectEvent(saved);
                    this.notification.add("Event saved to the college calendar.", {type: "success"});
                }
            }});
    }
    async remind() {
        if (!this.selected || this.state.reminderBusy) return;
        this.state.reminderBusy = true;
        try {
            await this.orm.call("campus.calendar.event", "action_set_reminder", [[this.selected.id]]);
            this.notification.add("Personal reminder saved. Find it in your Activities menu.", {type: "success"});
        } catch (error) { this.notification.add(error.data?.message || "The reminder could not be saved.", {type: "danger"}); }
        finally { this.state.reminderBusy = false; }
    }
}
registry.category("actions").add("ideastone_erp.college_calendar", CollegeCalendar);
