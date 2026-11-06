// Placement controls also work after the student shell replaces the page.
document.addEventListener("click", event => {
    const view = event.target.closest(".placements_view");
    if (!view) return;
    const dialog = event.target.closest("dialog.placement-dialog");
    const trigger = event.target.closest("[data-placement-open]");
    if (trigger) {
        const next = document.getElementById(trigger.dataset.placementOpen);
        if (next && view.contains(next)) {
            dialog?.close();
            next.showModal();
        }
        return;
    }
    if (event.target.closest("[data-placement-close]") || (dialog && event.target === dialog)) {
        dialog?.close();
        return;
    }
    const filter = event.target.closest("[data-placement-filter]");
    if (!filter) return;
    const state = filter.dataset.placementFilter;
    view.querySelectorAll("[data-placement-filter]").forEach(button => {
        button.setAttribute("aria-pressed", String(button === filter));
    });
    let visible = 0;
    view.querySelectorAll("[data-placement-state]").forEach(row => {
        row.hidden = state !== "all" && row.dataset.placementState !== state;
        if (!row.hidden) visible += 1;
    });
    view.querySelector("[data-placement-empty]").hidden = visible > 0;
});
