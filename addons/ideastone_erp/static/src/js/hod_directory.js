/** @odoo-module **/
import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "campus.hod.directory";
const YEARS = [1, 2, 3, 4];

export class HodDirectory extends Component {
    static template = "ideastone_erp.HodDirectory";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.view = this.props.action.params?.view === "students" ? "students" : "staff";
        this.state = useState({
            data: null, date: "", draftDate: "", query: "", attendance: "", draftAttendance: "",
            category: "Teaching", year: 0, section: 0, filter: "", profile: null, loading: false, error: "",
        });
        this.profileDialog = useRef("profileDialog");
        useEffect((dialog, profile) => {
            if (dialog && profile && !dialog.open) dialog.showModal();
        }, () => [this.profileDialog.el, this.state.profile]);
        useExternalListener(document, "click", (event) => {
            if (this.state.filter && !event.target.closest(".hod-directory .filter-wrap")) this.state.filter = "";
        });
        useExternalListener(document, "keydown", (event) => {
            if (event.key === "Escape") this.state.filter = "";
        });
        onWillStart(() => this.load());
    }

    get staff() { return this.view === "staff"; }
    get data() { return this.state.data; }
    get roster() { return this.data.sections.find((section) => section.id === this.state.section); }
    get teaching() { return this.data.rows.filter((row) => row.category === "Teaching").length; }
    get years() {
        return YEARS.map((year) => {
            const sections = this.data.sections.filter((section) => section.year === year);
            const count = new Set(this.data.rows.filter((row) => row.year === year).map((row) => row.student_id)).size;
            return { year, sections: sections.length, count };
        });
    }
    get sections() { return this.data.sections.filter((section) => section.year === this.state.year); }
    get rows() {
        const query = this.state.query.trim().toLowerCase();
        return this.data.rows.filter((row) =>
            (this.staff ? row.category === this.state.category : row.section_id === this.state.section) &&
            (!this.state.attendance || row.attendance === this.state.attendance) &&
            (!query || [row.name, row.code, row.designation, row.unit, this.staff ? "" : row.contact]
                .some((value) => String(value || "").toLowerCase().includes(query)))
        );
    }
    get stats() {
        const current = this.state.date === this.data.today;
        return [
            [this.staff ? "Department staff" : "Department students", "♙", this.data.total,
                this.staff ? "Teaching and non-teaching" : "Across four academic years"],
            [current ? "Present today" : "Present", "✓", this.data.present, "Attendance for selected date"],
            [current ? "Absent today" : "Absent", "–", this.data.absent,
                this.staff ? "Includes approved and unapproved absence" : "Across active sections"],
            this.staff ? ["Teaching staff", "▤", this.teaching, "Faculty members"] :
                ["Active sections", "▦", this.data.sections.length, "Across four academic years"],
        ];
    }
    get browseTitle() {
        return this.roster ? `Year ${this.roster.year} · ${this.roster.name}` :
            this.state.year ? `Year ${this.state.year} · Current sections` : "Select an academic year";
    }
    get browseSubtitle() {
        return this.roster ? "Student roster with attendance for the selected date." :
            this.state.year ? `Select a section to view the year ${this.state.year} student list.` :
                "Choose a year to view its current sections.";
    }
    initials(name) {
        return (name || "").trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
    }
    tone(attendance) {
        return attendance === "Present" ? "present" : attendance === "Absent" ? "absent" : "neutral";
    }
    async load(date = this.state.date) {
        if (this.state.loading) return;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call(MODEL, "get_directory", [this.view, date || false]);
            this.state.data = data;
            this.state.date = data.date;
            if (this.state.section && !this.roster) this.state.section = 0;
        } catch (error) {
            this.state.error = error.data?.message || "The directory could not be loaded.";
        } finally {
            this.state.loading = false;
        }
    }
    showYears() {
        this.state.year = 0;
        this.backToSections();
    }
    selectYear(year) {
        this.showYears();
        this.state.year = year;
    }
    backToSections() {
        this.state.section = 0;
        this.state.query = "";
        this.state.attendance = "";
        this.state.filter = "";
    }
    selectSection(id) {
        this.backToSections();
        this.state.section = id;
    }
    openFilter(key) {
        this.state.filter = this.state.filter === key ? "" : key;
        this.state.draftDate = this.state.date;
        this.state.draftAttendance = this.state.attendance;
    }
    async applyFilter() {
        const filter = this.state.filter;
        if (filter !== "browse") this.state.attendance = this.state.draftAttendance;
        this.state.filter = "";
        if (filter !== "roster" && this.state.draftDate !== this.state.date) await this.load(this.state.draftDate);
    }
    async resetFilter() {
        const filter = this.state.filter;
        this.state.filter = "";
        if (filter !== "browse") {
            this.state.query = "";
            this.state.attendance = "";
        }
        if (filter !== "roster") await this.load(this.data.today);
    }
    async openProfile(row) {
        try {
            this.state.profile = await this.orm.call(MODEL, "get_profile", [this.view, row.id, this.state.date]);
        } catch (error) {
            this.notification.add(error.data?.message || "The profile could not be opened.", { type: "danger" });
        }
    }
    closeProfile() {
        this.profileDialog.el?.close();
        this.state.profile = null;
    }
    onProfileKeydown(event) {
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            this.closeProfile();
        }
    }
    closeBackdrop(event) {
        if (event.target === this.profileDialog.el) this.closeProfile();
    }
}

registry.category("actions").add("ideastone_erp.hod_directory", HodDirectory);
