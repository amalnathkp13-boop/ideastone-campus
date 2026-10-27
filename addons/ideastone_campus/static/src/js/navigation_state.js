/** @odoo-module **/

// Preferences only reference this session's authorized catalogue. Stored data
// cannot supply a URL, action handler, icon markup or a newly granted module.
export function navigationItems(catalog, saved = []) {
    const available = new Map(catalog.map(item => [item.id, item]));
    const seen = new Set();
    const result = [];
    for (const row of saved) {
        if (!row || typeof row.id !== "string" || seen.has(row.id) || !available.has(row.target)) continue;
        if (row.id !== row.target && !row.id.startsWith("shortcut-")) continue;
        if (row.id === row.target && !available.get(row.target).main) continue;
        seen.add(row.id);
        result.push({id: row.id, target: row.target,
            label: typeof row.label === "string" && row.label.trim() ? row.label.trim().slice(0, 40) : available.get(row.target).label,
            visible: row.visible !== false, removed: row.removed === true});
    }
    for (const item of catalog.filter(item => item.main)) {
        if (!seen.has(item.id)) result.push({id: item.id, target: item.id, label: item.label, visible: true, removed: false});
    }
    // A revoked permission must never leave a user with an empty, unusable menu.
    if (result.length && !result.some(row => row.visible && !row.removed)) {
        result[0] = {...result[0], visible: true, removed: false};
    }
    return result;
}

export function moveNavigation(items, id, to) {
    const from = items.findIndex(row => row.id === id);
    if (from < 0 || to < 0 || to >= items.length) return;
    items.splice(to, 0, items.splice(from, 1)[0]);
}
