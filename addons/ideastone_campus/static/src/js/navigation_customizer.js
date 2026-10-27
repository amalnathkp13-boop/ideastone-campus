/** @odoo-module **/
import { moveNavigation, navigationItems } from "./navigation_state";

function element(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}
function icon(name) {
    const node = element("i", `fa fa-${/^[a-z0-9-]+$/.test(name || "") ? name : "th-large"}`);
    node.setAttribute("aria-hidden", "true");
    return node;
}

export class NavigationCustomizer {
    constructor({catalog, preferences, save, apply}) {
        this.catalog = catalog;
        this.preferences = preferences;
        this.save = save;
        this.apply = apply;
        this.draft = navigationItems(catalog, preferences.items);
    }
    open(trigger = document.activeElement) {
        this.trigger = trigger;
        this.dialog = element("dialog", "campus_nav_dialog");
        this.dialog.setAttribute("aria-labelledby", "campus_nav_dialog_title");
        this.dialog.innerHTML = `
            <div class="campus_nav_dialog_frame">
              <header class="campus_nav_dialog_header"><div><h2 id="campus_nav_dialog_title">Customize Navigation</h2>
                <p>Arrange, rename and choose the sidebar buttons for your workspace.</p></div>
                <button type="button" class="campus_nav_icon" data-command="close" aria-label="Close customization">×</button></header>
              <div class="campus_nav_dialog_body"><div class="campus_nav_editor">
                <div class="campus_nav_section_head"><h3>Sidebar buttons</h3><span>Drag or use ↑ ↓ to reorder</span></div>
                <div class="campus_nav_edit_list" aria-label="Navigation items"></div>
                <form class="campus_nav_rename" hidden><label>Button name<input maxlength="40" required name="rename"/></label>
                  <button class="btn btn-primary" type="submit">Save name</button><button class="btn btn-outline-primary" type="button" data-command="cancel-name">Cancel rename</button></form>
                <h3 class="campus_nav_add_title">Add a navigation button</h3>
                <form class="campus_nav_add"><label>Destination<select name="destination" required aria-label="Navigation destination"></select></label>
                  <label>Button name<input name="label" maxlength="40" required placeholder="e.g. My timetable"/></label>
                  <button class="btn btn-primary" type="submit">Add button</button></form>
                <p class="campus_nav_hint">Choose an existing destination available to your account. Removing a button only removes your shortcut; Reset restores the default menu.</p>
              </div><section class="campus_nav_preview"><h3>Live preview</h3><p>Review the order and visibility before saving.</p><nav aria-label="Navigation preview"></nav>
                <p>Your actual sidebar updates only after Save changes.</p></section></div>
              <div class="campus_nav_message" role="status" aria-live="polite"></div>
              <footer class="campus_nav_dialog_footer"><button class="btn btn-outline-primary" type="button" data-command="reset"><i class="fa fa-undo" aria-hidden="true"></i> Reset to default</button>
                <div><button class="btn btn-outline-primary" type="button" data-command="close">Cancel</button><button class="btn btn-primary" type="button" data-command="save">Save changes</button></div></footer>
            </div>`;
        for (const item of this.catalog) {
            const option = element("option", "", item.group ? `${item.group} / ${item.label}` : item.label);
            option.value = item.id;
            this.dialog.querySelector("select").append(option);
        }
        const addForm = this.dialog.querySelector(".campus_nav_add");
        addForm.elements.label.value = this.catalog[0]?.label || "";
        addForm.elements.destination.addEventListener("change", () => {
            addForm.elements.label.value = this.catalog.find(item => item.id === addForm.elements.destination.value)?.label || "";
        });
        addForm.addEventListener("submit", event => { event.preventDefault(); this.add(); });
        this.dialog.querySelector(".campus_nav_rename").addEventListener("submit", event => { event.preventDefault(); this.rename(); });
        this.dialog.addEventListener("click", event => {
            const button = event.target.closest("[data-command]");
            if (button && !this.busy) this.command(button.dataset.command, button.dataset.id);
            else if (event.target === this.dialog && !this.busy) {
                const rect = this.dialog.getBoundingClientRect();
                if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.close();
            }
        });
        this.dialog.addEventListener("cancel", event => { event.preventDefault(); if (!this.busy) this.close(); });
        // Keep keyboard focus inside the editor, including at the browser's
        // first/last tab stop, and keep background drawer/Odoo shortcuts out.
        this.dialog.addEventListener("keydown", event => {
            event.stopPropagation();
            if (event.key !== "Tab") return;
            const controls = [...this.dialog.querySelectorAll("button,input,select")]
                .filter(node => !node.disabled && node.getClientRects().length);
            const first = controls[0], last = controls[controls.length - 1];
            if (!first) { event.preventDefault(); return; }
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        });
        const list = this.dialog.querySelector(".campus_nav_edit_list");
        list.addEventListener("dragstart", event => {
            if (this.busy || !event.target.closest(".campus_nav_edit_row")) return;
            this.dragId = event.target.closest(".campus_nav_edit_row").dataset.id;
            event.dataTransfer.setData("text/plain", this.dragId);
            event.dataTransfer.effectAllowed = "move";
        });
        list.addEventListener("dragover", event => { event.preventDefault(); event.dataTransfer.dropEffect = "move"; });
        list.addEventListener("drop", event => {
            event.preventDefault();
            const target = event.target.closest(".campus_nav_edit_row")?.dataset.id;
            if (this.busy || !this.dragId || !target) return;
            moveNavigation(this.draft, this.dragId, this.draft.findIndex(row => row.id === target));
            this.dragId = null;
            this.render();
        });
        list.addEventListener("dragend", () => { this.dragId = null; });
        document.body.append(this.dialog);
        this.render();
        this.dialog.showModal();
        this.dialog.querySelector('[data-command="close"]').focus();
    }
    message(text) { this.dialog.querySelector(".campus_nav_message").textContent = text; }
    render(focusId, command) {
        const list = this.dialog.querySelector(".campus_nav_edit_list");
        const preview = this.dialog.querySelector(".campus_nav_preview nav");
        list.replaceChildren();
        preview.replaceChildren();
        const rows = this.draft.filter(row => !row.removed);
        for (const [index, row] of rows.entries()) {
            const target = this.catalog.find(item => item.id === row.target);
            const line = element("div", `campus_nav_edit_row${row.visible ? "" : " is-hidden"}`);
            line.draggable = true;
            line.dataset.id = row.id;
            const grip = element("span", "campus_nav_grip", "⠿");
            grip.title = "Drag to reorder";
            grip.setAttribute("aria-hidden", "true");
            const label = element("div", "campus_nav_row_label");
            label.append(icon(target.icon), element("span", "", row.label));
            if (!row.visible) label.append(element("small", "", "Hidden"));
            line.append(grip, label);
            const actions = element("div", "campus_nav_row_actions");
            for (const [action, glyph, name, disabled] of [
                ["up", "arrow-up", `Move ${row.label} up`, index === 0],
                ["down", "arrow-down", `Move ${row.label} down`, index === rows.length - 1],
                ["rename", "pencil", `Rename ${row.label}`],
                ["toggle", row.visible ? "eye" : "eye-slash", `${row.visible ? "Hide" : "Show"} ${row.label}`],
                ["remove", "trash-o", `Remove ${row.label}`],
            ]) {
                const button = element("button", "campus_nav_icon");
                button.type = "button";
                button.dataset.command = action;
                button.dataset.id = row.id;
                button.setAttribute("aria-label", name);
                button.title = name;
                button.disabled = Boolean(disabled);
                button.append(icon(glyph));
                actions.append(button);
            }
            line.append(actions);
            list.append(line);
            if (row.visible) {
                const item = element("div", "campus_nav_preview_item");
                item.append(icon(target.icon), element("span", "", row.label));
                preview.append(item);
            }
        }
        if (!preview.children.length) preview.append(element("p", "", "Keep at least one button visible."));
        if (focusId) [...list.querySelectorAll("button")].find(button => button.dataset.id === focusId && button.dataset.command === command)?.focus();
    }
    command(command, id) {
        this.message("");
        const row = this.draft.find(item => item.id === id);
        const rows = this.draft.filter(item => !item.removed);
        const index = rows.findIndex(item => item.id === id);
        if (command === "close") return this.close();
        if (command === "save") return this.commit();
        if (command === "cancel-name") { this.editId = null; this.dialog.querySelector(".campus_nav_rename").hidden = true; return; }
        if (command === "reset") {
            this.draft = navigationItems(this.catalog);
            this.command("cancel-name");
            this.render();
            this.message("Default menu restored in the preview. Save changes to apply it.");
            return;
        }
        if (!row) return;
        if (command === "up" || command === "down") {
            const neighbor = rows[index + (command === "up" ? -1 : 1)];
            if (neighbor) moveNavigation(this.draft, id, this.draft.findIndex(item => item.id === neighbor.id));
        } else if (command === "toggle") row.visible = !row.visible;
        else if (command === "remove") {
            if (row.id === row.target) { row.removed = true; row.visible = false; }
            else this.draft.splice(this.draft.indexOf(row), 1);
        } else if (command === "rename") {
            this.editId = id;
            const form = this.dialog.querySelector(".campus_nav_rename");
            form.hidden = false;
            form.elements.rename.value = row.label;
            form.elements.rename.focus();
            return;
        }
        this.render(id, command);
    }
    validName(value, except) {
        const label = value.trim();
        if (!label || label.length > 40 || /[\x00-\x1f]/.test(label)) { this.message("Enter a button name with 1–40 characters."); return false; }
        if (this.draft.some(row => !row.removed && row.id !== except && row.label.toLocaleLowerCase() === label.toLocaleLowerCase())) {
            this.message("A button with this name already exists."); return false;
        }
        return label;
    }
    add() {
        const form = this.dialog.querySelector(".campus_nav_add");
        const label = this.validName(form.elements.label.value);
        if (!label) return;
        const target = form.elements.destination.value;
        if (!this.catalog.some(item => item.id === target)) return;
        // Re-add a removed default rather than leaving a permanent duplicate.
        const removed = this.draft.find(row => row.id === target && row.removed);
        if (removed) Object.assign(removed, {label, visible: true, removed: false});
        else {
            if (this.draft.length >= 100) { this.message("Keep at most 100 navigation buttons."); return; }
            const id = [...crypto.getRandomValues(new Uint8Array(16))].map(value => value.toString(16).padStart(2, "0")).join("");
            this.draft.push({id: `shortcut-${id}`, target, label, visible: true, removed: false});
        }
        this.message("");
        this.render();
    }
    rename() {
        const label = this.validName(this.dialog.querySelector(".campus_nav_rename").elements.rename.value, this.editId);
        if (!label) return;
        const row = this.draft.find(item => item.id === this.editId);
        if (row) row.label = label;
        this.command("cancel-name");
        this.render(row?.id, "rename");
    }
    async commit() {
        if (!this.draft.some(row => row.visible && !row.removed)) { this.message("Keep at least one button visible."); return; }
        if (this.editId) { this.message("Save or cancel the button name before saving navigation."); return; }
        this.busy = true;
        const controls = [...this.dialog.querySelectorAll("button,input,select")].map(node => [node, node.disabled]);
        controls.forEach(([node]) => { node.disabled = true; });
        this.message("Saving navigation…");
        try {
            const saved = await this.save(this.draft, this.preferences.revision);
            this.apply(saved);
            this.close();
        } catch (error) {
            this.message(error.data?.message || "Navigation could not be saved. Your menu is unchanged; please retry.");
        } finally {
            this.busy = false;
            controls.forEach(([node, disabled]) => { node.disabled = disabled; });
        }
    }
    close() {
        this.dialog?.close();
        this.dialog?.remove();
        if (this.trigger?.isConnected) this.trigger.focus();
    }
}
