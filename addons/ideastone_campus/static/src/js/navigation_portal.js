/** @odoo-module **/
import { jsonrpc } from "@web/core/network/rpc_service";
import { NavigationCustomizer } from "./navigation_customizer";
import { navigationItems, sidebarCollapsed, saveSidebarCollapsed } from "./navigation_state";

const initialized = new WeakSet();
function call(method, args) {
    return jsonrpc("/web/dataset/call_kw/res.users/" + method, {model: "res.users", method, args, kwargs: {}});
}
async function initializeMenu(nav, button, scope, module = null) {
    const top = module !== null;
    const links = [...nav.querySelectorAll(top ? "a" : "a[data-navigation-key]")];
    const originals = new Map(links.map(link => {
        const url = new URL(link.href);
        return [top ? url.hash.slice(1) || url.pathname : link.dataset.navigationKey, link];
    }));
    const catalog = [...originals].map(([id, link]) => ({
        id, label: link.textContent.trim(), main: true,
        icon: [...(link.querySelector("i")?.classList || [])].find(name => name.startsWith("fa-"))?.slice(3),
    }));
    if (!catalog.length) return;
    if (top) {
        const strip = document.createElement("div");
        strip.className = "campus_portal_subnav_links";
        nav.insertBefore(strip, links[0]);
        strip.append(...links);
        nav = strip;
        button.hidden = false;
    }
    let appliedRevision = -1;
    function apply(preferences) {
        if (preferences.revision < appliedRevision) return;
        appliedRevision = preferences.revision;
        nav.querySelectorAll("[data-navigation-shortcut]").forEach(link => link.remove());
        for (const row of navigationItems(catalog, preferences.items)) {
            const source = originals.get(row.target);
            const link = row.id === row.target ? source : source.cloneNode(true);
            if (row.id !== row.target) link.dataset.navigationShortcut = row.id;
            (top ? link : link.querySelector("span")).textContent = row.label;
            link.title = row.label;
            link.hidden = !row.visible || row.removed;
            nav.append(link);
        }
    }
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            const preferences = await call("campus_get_navigation", [scope, module]);
            if (!button.isConnected) return;
            button.parentElement.querySelector(".campus_nav_load_error")?.remove();
            const customizer = new NavigationCustomizer({catalog, preferences, top,
                save: (items, revision) => call("campus_save_navigation", [scope, items, revision, module]), apply});
            customizer.open(button);
        } catch {
            if (!button.isConnected) return;
            let message = button.parentElement.querySelector(".campus_nav_load_error");
            if (!message) {
                message = document.createElement("span");
                message.className = "campus_nav_load_error";
                message.setAttribute("role", "alert");
                button.after(message);
            }
            message.textContent = "Could not load navigation. Please retry.";
        } finally { button.disabled = false; }
    });
    try {
        const preferences = await call("campus_get_navigation", [scope, module]);
        if (button.isConnected) apply(preferences);
    } catch { /* Preserve the working server-rendered menu when offline. */ }
}
function initialize(sidebar) {
    if (initialized.has(sidebar)) return;
    initialized.add(sidebar);
    const workspace = sidebar.closest(".student_workspace");
    const scope = sidebar.dataset.navigationScope;
    const button = sidebar.querySelector(".campus_customize_navigation");
    if (button) initializeMenu(sidebar.querySelector("nav"), button, scope);
    const top = workspace.querySelector(".student_subnav[data-navigation-module]");
    if (top) initializeMenu(top, top.querySelector(".campus_customize_top_navigation"), scope, top.dataset.navigationModule);

    const toggle = workspace.querySelector(".campus_desktop_toggle");
    if (!toggle) return;
    const key = sidebar.dataset.navigationUser + ":" + scope;
    function applyCollapsed(collapsed) {
        workspace.classList.toggle("campus_sidebar_collapsed", collapsed);
        toggle.setAttribute("aria-expanded", String(!collapsed));
        toggle.title = (collapsed ? "Expand" : "Collapse") + " campus navigation";
        toggle.setAttribute("aria-label", toggle.title);
    }
    applyCollapsed(sidebarCollapsed(key));
    toggle.addEventListener("click", () => {
        const collapsed = !workspace.classList.contains("campus_sidebar_collapsed");
        applyCollapsed(collapsed);
        saveSidebarCollapsed(key, collapsed);
    });
}
const sidebarSelector = ".student_sidebar[data-navigation-scope]";
function scan() { document.querySelectorAll(sidebarSelector).forEach(initialize); }
function start() {
    scan();
    // Reinitialize only when a portal page transition replaces the workspace.
    new MutationObserver(records => {
        if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 &&
            (node.matches(sidebarSelector) || node.querySelector(sidebarSelector))))) scan();
    }).observe(document.body, {childList: true, subtree: true});
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
else start();
