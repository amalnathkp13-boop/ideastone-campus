(() => {
    "use strict";
    let frame;
    let dirty = false;
    let flushing = null;
    let flushPromise;
    let replaying = false;
    let lmsUrl;
    let historyNavigation = 0;
    let navigationExpanded;
    let navigationMobile;
    const navigationObserver = new MutationObserver(syncNavigation);
    function syncNavigation() {
        if (!frame?.isConnected) return;
        const workspace = frame.closest(".student_workspace");
        const mobile = matchMedia("(max-width: 1023px)").matches;
        const expanded = mobile ? workspace.querySelector(".student_sidebar").classList.contains("is-open") :
            !workspace.classList.contains("campus_sidebar_collapsed");
        const focus = mobile && navigationMobile && navigationExpanded && !expanded;
        frame.contentWindow.postMessage({type: "campus-lms-navigation-state", expanded, focus: !!focus,
            label: `${expanded ? (mobile ? "Close" : "Collapse") : (mobile ? "Open" : "Expand")} campus navigation`}, location.origin);
        navigationExpanded = expanded;
        navigationMobile = mobile;
    }
    const route = () => location.hash.startsWith("#lms/") ? location.hash.slice(5) : "dashboard";
    function currentLmsPage() {
        if (!lmsUrl) return false;
        const rendered = new URL(lmsUrl);
        return location.pathname === rendered.pathname && location.search === rendered.search;
    }
    function flush() {
        if (flushPromise) return flushPromise;
        flushPromise = new Promise(resolve => {
            const timeout = setTimeout(() => { flushing = null; resolve(false); }, 15000);
            flushing = value => { clearTimeout(timeout); flushing = null; resolve(value); };
            frame.contentWindow.postMessage({type: "campus-lms-flush"}, location.origin);
        }).finally(() => { flushPromise = null; });
        return flushPromise;
    }
    function size() {
        if (frame?.isConnected) {
            frame.style.height = `${Math.max(280, window.innerHeight - frame.getBoundingClientRect().top)}px`;
        }
    }
    function navigate() {
        if (currentLmsPage()) frame?.contentWindow?.postMessage({type: "campus-lms-navigate", route: route()}, location.origin);
    }
    function enhance() {
        const next = document.getElementById("student_learning_studio");
        if (next === frame) return;
        navigationObserver.disconnect();
        frame = next;
        dirty = false;
        navigationExpanded = undefined;
        navigationMobile = undefined;
        if (frame) {
            lmsUrl = location.href;
            const workspace = frame.closest(".student_workspace");
            navigationObserver.observe(workspace, {attributes: true, attributeFilter: ["class"]});
            navigationObserver.observe(workspace.querySelector(".student_sidebar"), {attributes: true, attributeFilter: ["class"]});
            frame.addEventListener("load", () => { size(); navigate(); syncNavigation(); });
            size();
            // Odoo's lazy frontend bundle can load after the inner document is ready.
            navigate();
            syncNavigation();
        }
    }
    window.addEventListener("message", event => {
        if (!frame || event.origin !== location.origin || event.source !== frame.contentWindow) return;
        if (event.data?.type === "campus-lms-toggle-navigation") {
            const selector = matchMedia("(max-width: 1023px)").matches ? ".student_menu" : ".campus_desktop_toggle";
            frame.closest(".student_workspace").querySelector(selector)?.click();
        }
        if (currentLmsPage() && event.data?.type === "campus-lms-route" && typeof event.data.route === "string" &&
                /^[a-zA-Z0-9/-]{1,100}$/.test(event.data.route)) {
            const hash = `#lms/${event.data.route}`;
            if (location.hash !== hash) history.replaceState(history.state, "", hash);
            lmsUrl = location.href;
        }
        if (event.data?.type === "campus-lms-ready") { navigate(); syncNavigation(); }
        if (event.data?.type === "campus-lms-dirty") dirty = !!event.data.dirty;
        if (event.data?.type === "campus-lms-flushed" && flushing) flushing(!!event.data.saved);
    });
    document.addEventListener("click", async event => {
        if (!frame || replaying || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest("a[href]");
        if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
        const target = new URL(link.href, location.href);
        if (target.pathname === location.pathname && target.search === location.search) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (flushing) return;
        const saved = await flush();
        if (saved && link.isConnected) {
            replaying = true;
            link.click();
            replaying = false;
        } else {
            frame?.focus();
        }
    }, true);
    // Browser history also uses the portal's AJAX navigation; guard it before the
    // shared listener can remove this frame and its pending assignment/test draft.
    window.addEventListener("popstate", async event => {
        if (!frame?.isConnected || replaying || currentLmsPage()) return;
        event.stopImmediatePropagation();
        const sequence = ++historyNavigation;
        const saved = await flush();
        if (sequence !== historyNavigation || !frame?.isConnected) return;
        if (saved) {
            replaying = true;
            window.dispatchEvent(new PopStateEvent("popstate", {state: history.state}));
            replaying = false;
        } else {
            history.pushState({}, "", lmsUrl);
            navigate();
            frame.focus();
        }
    }, true);
    window.addEventListener("beforeunload", event => {
        if (frame?.isConnected && dirty) { event.preventDefault(); event.returnValue = ""; }
    });
    window.addEventListener("hashchange", navigate);
    window.addEventListener("popstate", navigate);
    window.addEventListener("resize", () => { size(); syncNavigation(); });
    new MutationObserver(enhance).observe(document.documentElement, {childList: true, subtree: true});
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance);
    else enhance();
})();
