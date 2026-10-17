// Progressive enhancement of the existing authenticated QWeb routes.
(() => {
    const root = () => document.getElementById("campus_student_workspace");
    let pending = null;
    let retry = null;
    let lastToggle = null;
    function closeMenu() {
        const workspace = root();
        workspace?.querySelector(".student_sidebar")?.classList.remove("is-open");
        if (workspace?.querySelector(".student_backdrop")) workspace.querySelector(".student_backdrop").hidden = true;
        workspace?.querySelector(".student_menu")?.setAttribute("aria-expanded", "false");
        lastToggle?.focus();
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
    }
    async function navigate(url, options = {}, push = true) {
        if (!root()) return;
        pending?.abort();
        const controller = new AbortController();
        pending = controller;
        const workspace = root();
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
            workspace.replaceWith(next);
            if (push) history.pushState({}, "", response.url);
            document.title = html.title || document.title;
            enhance();
            document.getElementById("student_main")?.focus({preventScroll: true});
            window.scrollTo({top: 0});
        } catch (error) {
            if (error.name === "AbortError") return;
            const banner = root()?.querySelector(".student_network_error");
            if (banner) {
                banner.querySelector("span").textContent = "The next view could not be loaded. You are viewing the last loaded records. Check your connection and retry. ";
                banner.hidden = false;
                banner.scrollIntoView({block: "center"});
                retry = () => navigate(url, options, push);
            }
        } finally {
            if (pending === controller) pending = null;
            root()?.querySelector(".student_busy")?.setAttribute("hidden", "hidden");
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
        const link = event.target.closest("a[href]");
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute("download")) return;
        const url = new URL(link.href, location.href);
        if (url.origin !== location.origin || !url.pathname.startsWith("/my/campus/student/") || url.pathname.includes("/download/") || url.hash) return;
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
            navigate(action.href, {method: "POST", body: data}).finally(() => {
                delete form.dataset.saving;
                buttons.forEach(button => { button.disabled = false; button.textContent = button.dataset.original; });
            });
        }
    });
    document.addEventListener("change", event => { if (event.target.matches(".student_request_type")) enhance(); });
    document.addEventListener("input", event => {
        if (!event.target.matches(".student_book_search")) return;
        const query = event.target.value.trim().toLocaleLowerCase();
        root()?.querySelectorAll(".student_books article").forEach(book => { book.hidden = !book.textContent.toLocaleLowerCase().includes(query); });
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && root()?.querySelector(".student_sidebar.is-open")) { closeMenu(); event.stopPropagation(); }
    }, {capture: true});
    window.addEventListener("popstate", () => { if (root()) navigate(location.href, {}, false); });
    window.addEventListener("pagehide", () => { if (root()) root().hidden = true; });
    window.addEventListener("pageshow", event => { if (event.persisted && root()) location.reload(); else if (root()) root().hidden = false; });
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance); else enhance();
})();
