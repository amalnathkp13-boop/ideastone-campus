// Progressive enhancement for the authenticated student's timetable content.
(() => {
    const view = () => document.querySelector(".student_timetable_view");
    const pageForHash = {"#student_timetable_overview": "overview", "#student_timetable_planner": "planner", "#student_timetable_today": "planner"};
    function showPage(name, push = true) {
        const root = view();
        if (!root) return;
        const active = name === "overview" ? "overview" : "planner";
        root.querySelectorAll("[data-timetable-page]").forEach(page => { page.hidden = page.dataset.timetablePage !== active; });
        const breadcrumb = document.querySelector(".student_breadcrumb > span:first-child");
        if (breadcrumb) breadcrumb.textContent = `My campus / ${active === "overview" ? "Timetable overview" : "Timetable"}`;
        const overviewLink = document.querySelector('.student_subnav a[href="#student_main"]');
        if (overviewLink) {
            if (active === "overview") overviewLink.setAttribute("aria-current", "page");
            else overviewLink.removeAttribute("aria-current");
        }
        if (push) {
            history.pushState({}, "", active === "overview" ? "#student_timetable_overview" : "#student_timetable_planner");
            document.getElementById("student_main")?.scrollIntoView({block: "start"});
        }
    }
    function showMode(mode) {
        const root = view();
        if (!root) return;
        if (mode === "today" && (root.dataset.today < root.dataset.weekStart || root.dataset.today > root.dataset.weekEnd)) {
            const day = new Date(`${root.dataset.today}T12:00:00Z`);
            const monday = new Date(day);
            monday.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
            const sunday = new Date(monday);
            sunday.setUTCDate(monday.getUTCDate() + 6);
            const params = new URLSearchParams({enrolment: root.dataset.enrolment, date_from: monday.toISOString().slice(0, 10), date_to: sunday.toISOString().slice(0, 10)});
            location.assign(`/my/campus/student/timetable?${params}#student_timetable_today`);
            return;
        }
        const grid = root.querySelector("[data-timetable-grid]");
        const agenda = root.querySelector("[data-timetable-agenda]");
        grid.hidden = mode !== "week";
        agenda.hidden = mode === "week";
        root.querySelector(".timetable_grid_empty")?.toggleAttribute("hidden", mode !== "week");
        let todayCount = 0;
        agenda.querySelectorAll(".timetable_agenda_item").forEach(item => {
            item.hidden = mode === "today" && item.dataset.day !== root.dataset.today;
            if (!item.hidden) todayCount++;
        });
        const noToday = agenda.querySelector(".timetable_today_empty");
        if (noToday) noToday.hidden = mode !== "today" || todayCount > 0;
        agenda.querySelector(".timetable_empty:not(.timetable_today_empty)")?.toggleAttribute("hidden", mode === "today");
        root.querySelectorAll("[data-timetable-mode]").forEach(button => {
            const selected = button.dataset.timetableMode === mode;
            button.classList.toggle("is-active", selected);
            button.setAttribute("aria-pressed", String(selected));
        });
    }
    function classDetails(button) {
        const root = view();
        const dialog = root?.querySelector(".timetable_dialog");
        if (!dialog) return;
        dialog.querySelector("#timetable_dialog_title").textContent = button.dataset.subject || "Class details";
        for (const key of ["time", "faculty", "room", "code", "status"])
            dialog.querySelector(`[data-timetable-detail="${key}"]`).textContent = button.dataset[key] || "Not assigned";
        dialog.showModal();
    }
    document.addEventListener("click", event => {
        const root = view();
        if (!root) return;
        const sharedOverview = event.target.closest('.student_subnav a[href="#student_main"]');
        if (sharedOverview && document.getElementById("campus_student_workspace")?.contains(sharedOverview)) {
            event.preventDefault();
            showPage("overview");
            return;
        }
        if (!root.contains(event.target)) return;
        const open = event.target.closest("[data-timetable-open]");
        if (open) { showPage(open.dataset.timetableOpen); return; }
        const mode = event.target.closest("[data-timetable-mode]");
        if (mode) { showMode(mode.dataset.timetableMode); return; }
        const entry = event.target.closest(".timetable_class");
        if (entry) { classDetails(entry); return; }
        if (event.target.closest(".timetable_dialog_close")) { root.querySelector(".timetable_dialog")?.close(); return; }
        if (event.target.closest(".timetable_print")) window.print();
    });
    addEventListener("hashchange", () => { if (view()) showPage(pageForHash[location.hash] || "planner", false); });
    addEventListener("popstate", () => { if (view()) showPage(pageForHash[location.hash] || "planner", false); });
    function initialise() {
        if (!view()) return;
        showPage(pageForHash[location.hash] || "planner", false);
        if (location.hash === "#student_timetable_today") showMode("today");
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise, {once: true});
    else initialise();
})();
