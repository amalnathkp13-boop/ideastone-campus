// Progressive enhancement of the existing authenticated QWeb routes.
(() => {
    const root = () => document.getElementById("campus_student_workspace");
    let pending = null;
    let retry = null;
    let lastToggle = null;
    // Path + query of the view currently rendered; in-page anchors only change the hash.
    let rendered = location.pathname + location.search;
    function closeMenu() {
        const workspace = root();
        workspace?.querySelector(".student_sidebar")?.classList.remove("is-open");
        if (workspace?.querySelector(".student_backdrop")) workspace.querySelector(".student_backdrop").hidden = true;
        workspace?.querySelector(".student_menu")?.setAttribute("aria-expanded", "false");
        lastToggle?.focus();
    }
    function showProfilePage() {
        const workspace = root();
        const view = workspace?.querySelector(".student_profile_view");
        if (!view) return;
        const pageForHash = {
            "#student_profile_overview": "overview",
            "#student_personal": "personal",
            "#student_guardians": "guardian",
            "#student_documents": "documents",
        };
        const active = pageForHash[location.hash] || "overview";
        const labels = {
            overview: ["My Profile", "Your student identity, contact information and profile records in one place."],
            personal: ["Personal details", "Review your identity, programme and contact details. Official fields may be locked by the college."],
            guardian: ["Guardian contacts", "View parent or guardian information and emergency contact details."],
            documents: ["Documents", "Review documents linked to your student record and check their current status."],
        };
        view.querySelectorAll("[data-profile-page]").forEach(page => { page.hidden = page.dataset.profilePage !== active; });
        workspace.querySelector(".student_page_heading h1").textContent = labels[active][0];
        view.querySelector(".profile_intro p").textContent = labels[active][1];
        workspace.querySelector(".student_breadcrumb > span:first-child").textContent = `My campus / ${labels[active][0]}`;
        workspace.querySelectorAll('.student_subnav a[href^="#student_"]').forEach(link => {
            if (pageForHash[link.getAttribute("href")] === active) link.setAttribute("aria-current", "page");
            else link.removeAttribute("aria-current");
        });
    }
    function enhance() {
        const workspace = root();
        if (!workspace) return;
        const type = workspace.querySelector(".student_request_type");
        if (type) {
            const option = type.selectedOptions[0];
            const form = type.closest("form");
            form.querySelector(".student_type_guidance").textContent = option?.dataset.guidance || "No request type is currently enabled.";
            form.querySelector(".student_type_fee").textContent = option?.dataset.fee || "";
            form.querySelector(".student_upload_guidance").textContent = `PDF, PNG, JPEG or UTF-8 text. Maximum ${option?.dataset.limit || 2} MB. Files are validated by the server.`;
            form.querySelector("input[type=file]").required = option?.dataset.required === "true";
            form.querySelector("button[type=submit]").disabled = !option;
        }
        showProfilePage();
    }
    async function navigate(url, options = {}, push = true, form = null) {
        if (!root()) return;
        pending?.abort();
        const controller = new AbortController();
        pending = controller;
        const workspace = root();
        const previous = new URL(location.href);
        workspace.querySelector(".student_network_error").hidden = true;
        workspace.querySelector(".student_busy").hidden = false;
        try {
            const response = await fetch(url, {...options, signal: controller.signal, credentials: "same-origin", cache: "no-store"});
            if (response.redirected && !new URL(response.url).pathname.startsWith("/my/campus")) {
                location.assign(response.url);
                return;
            }
            if (!response.ok && response.status !== 403 && response.status !== 400) throw new Error("Service unavailable");
            const html = new DOMParser().parseFromString(await response.text(), "text/html");
            const next = html.getElementById("campus_student_workspace");
            if (!next) throw new Error("Student workspace unavailable");
            const destination = new URL(response.url);
            if (form && destination.pathname === previous.pathname) destination.hash = previous.hash;
            if (form && destination.searchParams.has("form_error")) {
                const target = [...next.querySelectorAll("form")].find(candidate =>
                    ["operation", "assignment_id", "request_id", "notice_id"].every(key =>
                        candidate.elements.namedItem(key)?.value === form.elements.namedItem(key)?.value));
                if (target) {
                    for (const field of target.elements) {
                        const original = form.elements.namedItem(field.name);
                        if (!original || !field.name || field.type === "hidden" || field.type === "submit") continue;
                        if (field.type === "file") field.files = original.files;
                        else if (field.type === "checkbox" || field.type === "radio") field.checked = original.checked;
                        else field.value = original.value;
                    }
                    target.closest("details")?.setAttribute("open", "");
                }
            }
            workspace.replaceWith(next);
            if (push) history.pushState({}, "", destination.href);
            rendered = location.pathname + location.search;
            document.title = html.title || document.title;
            enhance();
            document.getElementById("student_main")?.focus({preventScroll: true});
            // Native portal pages scroll inside #wrapwrap rather than the window.
            document.getElementById("wrapwrap")?.scrollTo({top: 0});
            window.scrollTo({top: 0});
        } catch (error) {
            if (error.name === "AbortError") return;
            const banner = root()?.querySelector(".student_network_error");
            if (banner) {
                banner.querySelector("span").textContent = "The next view could not be loaded. You are viewing the last loaded records. Check your connection and retry. ";
                banner.hidden = false;
                banner.scrollIntoView({block: "center"});
                retry = () => navigate(url, options, push, form);
            }
        } finally {
            if (pending === controller) {
                pending = null;
                root()?.querySelector(".student_busy")?.setAttribute("hidden", "hidden");
            }
        }
    }
    document.addEventListener("click", event => {
        const workspace = root();
        if (!workspace || !workspace.contains(event.target)) return;
        const toggle = event.target.closest(".student_menu");
        if (toggle) {
            lastToggle = toggle;
            const open = workspace.querySelector(".student_sidebar").classList.toggle("is-open");
            workspace.querySelector(".student_backdrop").hidden = !open;
            toggle.setAttribute("aria-expanded", String(open));
            if (open) workspace.querySelector(".student_sidebar a")?.focus();
            return;
        }
        if (event.target.closest(".student_backdrop")) { closeMenu(); return; }
        if (event.target.closest(".student_retry")) { retry?.(); return; }
        const profileLink = event.target.closest('a[href^="#student_"]');
        if (profileLink && workspace.querySelector(".student_profile_view")) {
            const target = new URL(profileLink.href, location.href);
            if (target.pathname === location.pathname && target.search === location.search) {
                event.preventDefault();
                history.pushState({}, "", target.href);
                showProfilePage();
                document.getElementById("student_main")?.scrollIntoView({block: "start"});
                return;
            }
        }
        const range = event.target.closest("[data-timetable]");
        if (range) {
            const controls = range.closest(".student_timetable_controls");
            const today = new Date(controls.dataset.today + "T12:00:00Z");
            const monday = new Date(today);
            monday.setUTCDate(today.getUTCDate() - (today.getUTCDay() + 6) % 7);
            const sunday = new Date(monday);
            sunday.setUTCDate(monday.getUTCDate() + 6);
            let count = 0;
            workspace.querySelectorAll(".student_timetable_row").forEach(row => {
                const day = new Date(row.dataset.day + "T12:00:00Z");
                const show = range.dataset.timetable === "all" || (range.dataset.timetable === "today" ? day.getTime() === today.getTime() : day >= monday && day <= sunday);
                row.hidden = !show;
                count += Number(show);
            });
            controls.querySelectorAll("button").forEach(button => {
                button.setAttribute("aria-pressed", String(button === range));
                button.classList.toggle("btn-primary", button === range);
                button.classList.toggle("btn-outline-primary", button !== range);
            });
            workspace.querySelector(".student_timetable_empty").hidden = count > 0;
            return;
        }
        const link = event.target.closest("a[href]");
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute("download")) return;
        const url = new URL(link.href, location.href);
        if (url.origin !== location.origin || !url.pathname.startsWith(workspace.dataset.portalPrefix || "/my/campus/student/") || url.pathname.includes("/download/") || url.hash) return;
        event.preventDefault();
        navigate(url.href);
    });
    document.addEventListener("submit", event => {
        const form = event.target;
        if (!root()?.contains(form) || !form.matches("form")) return;
        event.preventDefault();
        if (form.dataset.saving) return;
        const data = new FormData(form);
        const action = new URL(form.action, location.href);
        if (form.method.toLowerCase() === "get") {
            action.search = new URLSearchParams(data).toString();
            navigate(action.href);
        } else {
            form.dataset.saving = "true";
            const buttons = [...form.querySelectorAll("button[type=submit]")];
            buttons.forEach(button => { button.disabled = true; button.dataset.original = button.textContent; button.textContent = "Saving…"; });
            navigate(action.href, {method: "POST", body: data}, true, form).finally(() => {
                delete form.dataset.saving;
                buttons.forEach(button => { button.disabled = false; button.textContent = button.dataset.original; });
            });
        }
    });
    document.addEventListener("change", event => {
        if (event.target.matches(".student_request_type")) enhance();
        if (event.target.matches(".parent_homework_filter")) {
            root()?.querySelectorAll(".parent_homework").forEach(row => {
                row.hidden = event.target.value !== "all" && (event.target.value === "pending") !== (row.dataset.pending === "true");
            });
        }
    });
    document.addEventListener("input", event => {
        if (!event.target.matches(".student_book_search")) return;
        const query = event.target.value.trim().toLocaleLowerCase();
        root()?.querySelectorAll(".student_books article").forEach(book => { book.hidden = !book.textContent.toLocaleLowerCase().includes(query); });
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && root()?.querySelector(".student_sidebar.is-open")) { closeMenu(); event.stopPropagation(); }
        if (event.key === "Tab" && root()?.querySelector(".student_sidebar.is-open")) {
            const links = [...root().querySelectorAll(".student_sidebar a[href]")];
            const first = links[0], last = links[links.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
    }, {capture: true});
    window.addEventListener("popstate", () => {
        // Chrome fires popstate for same-page #anchor jumps; re-rendering then would discard unsaved form input.
        if (!root()) return;
        if (location.pathname + location.search === rendered) { showProfilePage(); return; }
        navigate(location.href, {}, false);
    });
    window.addEventListener("hashchange", showProfilePage);
    window.addEventListener("pagehide", () => { if (root()) root().hidden = true; });
    window.addEventListener("pageshow", event => { if (event.persisted && root()) location.reload(); else if (root()) root().hidden = false; });
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance); else enhance();
})();
