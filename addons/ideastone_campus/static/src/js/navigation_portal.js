/** @odoo-module **/
import { jsonrpc } from "@web/core/network/rpc_service";
import { NavigationCustomizer } from "./navigation_customizer";
import { navigationItems } from "./navigation_state";

const initialized = new WeakSet();
function call(method, args) {
    return jsonrpc(`/web/dataset/call_kw/res.users/${method}`, {model: "res.users", method, args, kwargs: {}});
}
async function initialize(sidebar) {
    if (initialized.has(sidebar)) return;
    initialized.add(sidebar);
    const button = sidebar.querySelector(".campus_customize_navigation");
    if (!button) return;
    const scope = sidebar.dataset.navigationScope;
    const nav = sidebar.querySelector("nav");
    const originals = new Map([...nav.querySelectorAll("a[data-navigation-key]")].map(link => [link.dataset.navigationKey, link]));
    const catalog = [...originals].map(([id, link]) => ({id, label: link.querySelector("span").textContent.trim(),
        icon: [...link.querySelector("i").classList].find(name => name.startsWith("fa-"))?.slice(3), main: true}));
    let appliedRevision = -1;
    function apply(preferences) {
        if (preferences.revision < appliedRevision) return;
        appliedRevision = preferences.revision;
        nav.querySelectorAll("[data-navigation-shortcut]").forEach(link => link.remove());
        for (const row of navigationItems(catalog, preferences.items)) {
            const source = originals.get(row.target);
            const link = row.id === row.target ? source : source.cloneNode(true);
            if (row.id !== row.target) link.dataset.navigationShortcut = row.id;
            link.querySelector("span").textContent = row.label;
            link.hidden = !row.visible || row.removed;
            nav.append(link);
        }
    }
    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            const preferences = await call("campus_get_navigation", [scope]);
            if (!sidebar.isConnected) return;
            sidebar.querySelector(".campus_nav_load_error")?.remove();
            const customizer = new NavigationCustomizer({catalog, preferences,
                save: (items, revision) => call("campus_save_navigation", [scope, items, revision]), apply});
            customizer.open(button);
        } catch {
            let message = sidebar.querySelector(".campus_nav_load_error");
            if (!message) { message = document.createElement("span"); message.className = "campus_nav_load_error"; message.setAttribute("role", "alert"); button.after(message); }
            message.textContent = "Could not load navigation. Please retry.";
        } finally { button.disabled = false; }
    });
    try {
        const preferences = await call("campus_get_navigation", [scope]);
        if (sidebar.isConnected) apply(preferences);
    } catch { /* Preserve the working server-rendered menu when offline. */ }
}
function scan() { document.querySelectorAll(".student_sidebar[data-navigation-scope]").forEach(initialize); }
function start() {
    scan();
    // Portal page transitions replace the workspace. Initialize that new sidebar
    // once, without touching Owl-owned backend DOM or watching text changes.
    new MutationObserver(records => {
        if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 &&
            (node.matches(".student_sidebar[data-navigation-scope]") || node.querySelector(".student_sidebar[data-navigation-scope]"))))) scan();
    }).observe(document.body, {childList: true, subtree: true});
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
else start();
