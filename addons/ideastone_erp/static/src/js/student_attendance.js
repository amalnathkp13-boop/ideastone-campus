// Enhances only the student Attendance content; the shared navigation stays intact.
(() => {
    const view = () => document.querySelector(".attendance_view");
    const pages = {
        "#student_attendance_overview": "overview",
        "#student_attendance_summary": "summary",
        "#student_attendance_register": "register",
        "#student_attendance_calendar": "calendar",
    };
    const labels = {overview: "My Attendance", summary: "Attendance Summary", register: "Session Register", calendar: "Attendance Calendar"};
    const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const statuses = ["absent", "late", "excused", "present"];
    const dateFrom = value => new Date(`${value}T12:00:00`);
    const isoDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    const moveDay = (date, amount) => { const next = new Date(date); next.setDate(next.getDate() + amount); return next; };
    const records = attendance => [...attendance.querySelectorAll(".attendance_register_row")].map(row => ({
        date: row.dataset.date, status: row.dataset.status, row,
    }));

    function showPage() {
        const attendance = view();
        if (!attendance) return;
        const active = pages[location.hash] || "overview";
        attendance.querySelectorAll("[data-attendance-page]").forEach(page => { page.hidden = page.dataset.attendancePage !== active; });
        attendance.querySelectorAll("[data-attendance-tab]").forEach(link => link.classList.toggle("active", link.dataset.attendanceTab === active));
        const crumb = attendance.closest("#campus_student_workspace")?.querySelector(".student_breadcrumb > span:first-child");
        if (crumb) crumb.textContent = `My campus / ${labels[active]}`;
        attendance.closest("#campus_student_workspace")?.querySelectorAll('.student_subnav a[href^="#student_attendance_"]').forEach(link => {
            if (pages[link.getAttribute("href")] === active) link.setAttribute("aria-current", "page");
            else link.removeAttribute("aria-current");
        });
        if (!attendance.dataset.initialized) {
            attendance.dataset.initialized = "true";
            attendance.dataset.month = attendance.dataset.today.slice(0, 7);
            renderWeek(attendance);
            renderMonth(attendance);
            filterRegister(attendance);
        }
    }

    function dayState(rows, iso, today) {
        const matches = rows.filter(row => row.date === iso);
        const status = statuses.find(value => matches.some(row => row.status === value));
        return {status: status || "future", label: matches.length ? `${matches.length} ${matches.length === 1 ? "class" : "classes"} · ${status[0].toUpperCase() + status.slice(1)}` : iso > today ? "Future" : "No class"};
    }
    function dayCard(date, rows, today, heading = false) {
        const iso = isoDate(date);
        const state = dayState(rows, iso, today);
        const cell = document.createElement("div");
        cell.className = `attendance_day ${heading ? "heading" : state.status}`;
        const dow = document.createElement("div"); dow.className = "dow"; dow.textContent = dayNames[date.getDay()];
        cell.append(dow);
        if (!heading) {
            const number = document.createElement("div"); number.className = "date"; number.textContent = date.getDate();
            const mark = document.createElement("div"); mark.className = "mark"; mark.textContent = state.label;
            cell.append(number, mark);
            cell.title = `${iso}: ${state.label}`;
        }
        return cell;
    }
    function renderWeek(attendance) {
        const host = attendance.querySelector("[data-attendance-week]");
        const today = dateFrom(attendance.dataset.today);
        const monday = moveDay(today, (today.getDay() + 6) % 7 * -1);
        const rows = records(attendance);
        host.replaceChildren(...Array.from({length: 7}, (_, index) => dayCard(moveDay(monday, index), rows, attendance.dataset.today)));
    }
    function renderMonth(attendance) {
        const host = attendance.querySelector("[data-attendance-month-grid]");
        const [year, month] = attendance.dataset.month.split("-").map(Number);
        const first = new Date(year, month - 1, 1, 12);
        const days = new Date(year, month, 0).getDate();
        const label = first.toLocaleDateString("en-GB", {month: "long", year: "numeric"});
        attendance.querySelector("[data-attendance-month-label]").textContent = label;
        attendance.querySelector("[data-attendance-month-title]").textContent = label;
        const cells = dayNames.map(name => {
            const cell = document.createElement("div"); cell.className = "attendance_day heading";
            const text = document.createElement("div"); text.className = "dow"; text.textContent = name;
            cell.append(text); return cell;
        });
        for (let index = 0; index < first.getDay(); index++) {
            const blank = document.createElement("div"); blank.className = "attendance_day heading"; blank.setAttribute("aria-hidden", "true"); cells.push(blank);
        }
        const rows = records(attendance);
        for (let day = 1; day <= days; day++) cells.push(dayCard(new Date(year, month - 1, day, 12), rows, attendance.dataset.today));
        host.replaceChildren(...cells);
    }
    function filterRegister(attendance) {
        const section = attendance.querySelector('[data-attendance-page="register"]');
        const subject = section.querySelector('[data-attendance-filter="subject"]').value;
        const status = section.querySelector('[data-attendance-filter="status"]').value;
        const from = section.querySelector('[data-attendance-filter="from"]').value;
        const to = section.querySelector('[data-attendance-filter="to"]').value;
        const search = section.querySelector('[data-attendance-filter="search"]').value.trim().toLocaleLowerCase();
        let visible = 0;
        section.querySelectorAll(".attendance_register_row").forEach(row => {
            row.hidden = (subject !== "all" && row.dataset.subject !== subject) || (status !== "all" && row.dataset.status !== status)
                || Boolean(from && row.dataset.date < from) || Boolean(to && row.dataset.date > to)
                || !row.textContent.toLocaleLowerCase().includes(search);
            if (!row.hidden) visible++;
        });
        section.querySelector("[data-attendance-count]").textContent = `Showing ${visible} of ${section.querySelectorAll(".attendance_register_row").length} submitted sessions`;
        section.querySelector(".attendance_no_matches").hidden = visible !== 0 || section.querySelectorAll(".attendance_register_row").length === 0;
    }
    function exportTable(table, name, rows) {
        const lines = [...rows].map(row => [...row.cells].map(cell => {
            let value = cell.textContent.trim().replace(/\s+/g, " ");
            if (/^[=+\-@]/.test(value)) value = `'${value}`;
            return `"${value.replaceAll('"', '""')}"`;
        }).join(","));
        const blob = new Blob(["\uFEFF", lines.join("\r\n")], {type: "text/csv;charset=utf-8"});
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a"); link.href = url; link.download = name; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    document.addEventListener("click", event => {
        const attendance = view();
        if (!attendance) return;
        const link = event.target.closest('a[href^="#"]');
        if (link && (attendance.contains(link) || link.closest(".student_subnav"))) {
            const destination = link.getAttribute("href");
            if (pages[destination] || destination === "#student_main") {
                event.preventDefault();
                history.pushState({}, "", link.href);
                showPage();
                document.getElementById("wrapwrap")?.scrollTo({top: 0});
                window.scrollTo({top: 0});
                return;
            }
        }
        const month = event.target.closest("[data-attendance-month]");
        if (month && attendance.contains(month)) {
            const current = dateFrom(`${attendance.dataset.month}-01`);
            const next = month.dataset.attendanceMonth === "today" ? dateFrom(attendance.dataset.today) : new Date(current.getFullYear(), current.getMonth() + (month.dataset.attendanceMonth === "next" ? 1 : -1), 1, 12);
            attendance.dataset.month = isoDate(next).slice(0, 7);
            renderMonth(attendance);
        }
        if (event.target.closest("[data-attendance-reset]")) {
            const section = attendance.querySelector('[data-attendance-page="register"]');
            section.querySelector('[data-attendance-filter="subject"]').value = "all";
            section.querySelector('[data-attendance-filter="status"]').value = "all";
            section.querySelector('[data-attendance-filter="from"]').value = attendance.dataset.periodStart;
            section.querySelector('[data-attendance-filter="to"]').value = attendance.dataset.periodEnd;
            section.querySelector('[data-attendance-filter="search"]').value = "";
            filterRegister(attendance);
        }
        const exportButton = event.target.closest("[data-attendance-export]");
        if (exportButton && attendance.contains(exportButton)) {
            const summary = exportButton.dataset.attendanceExport === "summary";
            const table = attendance.querySelector(summary ? "[data-attendance-summary-table]" : "[data-attendance-register-table]");
            const bodyRows = [...table.tBodies[0].rows].filter(row => !row.hidden && (summary ? row.querySelector(".attendance_status") : row.classList.contains("attendance_register_row")));
            exportTable(table, summary ? "attendance-summary.csv" : "attendance-session-register.csv", [table.tHead.rows[0], ...bodyRows]);
        }
    });
    document.addEventListener("input", event => { if (event.target.matches("[data-attendance-filter]")) { const attendance = view(); if (attendance?.contains(event.target)) filterRegister(attendance); } });
    document.addEventListener("change", event => { if (event.target.matches("[data-attendance-filter]")) { const attendance = view(); if (attendance?.contains(event.target)) filterRegister(attendance); } });
    window.addEventListener("hashchange", showPage);
    window.addEventListener("popstate", showPage);
    function watch() {
        new MutationObserver(changes => {
            if (changes.some(change => [...change.addedNodes].some(node => node.nodeType === 1 && (node.matches?.(".attendance_view") || node.querySelector?.(".attendance_view"))))) showPage();
        }).observe(document.body, {childList: true, subtree: true});
        showPage();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", watch);
    else watch();
})();
