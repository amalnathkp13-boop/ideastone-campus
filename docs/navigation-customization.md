# Personal sidebar navigation

Select **Customize Navigation** at the bottom of the existing sidebar. This is
available in student, parent, owner/admin, faculty, HOD, COE, and ordinary internal
staff workspaces. Page content, top navigation, module titles and business
operations are retained.

- Reorder by dragging a row or using its Up/Down buttons (also usable by touch or keyboard).
- Rename sidebar labels, show/hide buttons, or remove them from your personal menu.
- Add a named shortcut by selecting a destination already available to your account.
  Internal workspaces also offer their permitted submodule actions.
- The live preview changes immediately. The actual sidebar changes only after
  **Save changes** succeeds. Cancel, Escape and Close discard the draft.
- **Reset to default** updates the draft; Save applies it and Cancel discards it.
  Removed default buttons can also be re-added through the destination selector.

Preferences are saved on the authenticated user's account, separated by company
and workspace role, and survive reloads and sign-ins on another device. There is
no shared global menu change. A stale save from another tab is rejected rather
than overwriting newer preferences. At least one button must remain visible.

Only IDs, labels, order and visibility are stored. Runtime destinations always
come from the current authorized menu catalogue, never from a user-supplied URL
or action handler. Revoked destinations disappear; newly available default
modules are appended. Existing server ACLs, record rules and action handlers
remain in force. Customize Navigation and Sign out remain outside the editable
list, so the editor stays reachable after hiding other buttons.

## Local verification, 27 October 2026

Branch: `codex/sidebar-navigation-customization`, based on main `a0bc5a2`, carrying
the earlier local shared typography changes.

- 23 selected backend tests passed: four new navigation-preference tests plus
  the existing VCET workspace regression suite. These cover account/role/company
  isolation, malformed input, anonymous access, concurrent-edit revisions, field
  access, and preserved role memberships.
- `node docs/qa/navigation-state.cjs` passed: order, reset, duplicate IDs, newly
  granted modules, revoked destinations, and recovery from an empty menu.
- Browser checks passed for saving and reloading in all seven workspace types.
  Parent tests covered reorder, rename, hide, remove, add, working filtered links,
  cancel, reset, and conflicting saves in two tabs. Faculty/HOD shortcuts opened
  their existing question-paper pages. Ordinary staff opened a native maintenance
  action; COE opened its question-paper workspace.
- Desktop and actual 320px/390px phone layouts were inspected. Portal and backend
  editors had no horizontal overflow. Keyboard focus wraps inside the dialog.
- Ruff, XML/manifest parsing, JavaScript syntax checks, SCSS compilation and
  `git diff --check` passed.

The preview is isolated from the running ERP on port **18082**, using container
`ideastone-navigation-preview` and database `campus_navigation_preview`, copied
from the earlier role-preview database. Main `campus` records and current port-80
deployment are untouched. Test changes affect only this preview's personal menus.

Preview hosts: `student-nav.localhost`, `parent-nav.localhost`,
`admin-nav.localhost`, `faculty-nav.localhost`, `hod-nav.localhost`,
`coe-nav.localhost`, and `staff-nav.localhost`, all on port 18082.

## Apply after merging

Both addon versions are bumped: `ideastone_campus` to `17.0.1.0.5` and
`ideastone_erp` to `17.0.1.0.24`. The base addon registers the shared styles and
editor in both Odoo asset bundles. The ERP upgrade loads the student/parent
templates; internal staff, faculty, HOD, COE and owner screens share the same
backend navigation component. No per-user installation or preview account is
required on the deployed ERP.

From the deployment's main checkout, pull the merged code and force the Odoo
container to restart so the existing startup upgrade runs even when its image
has not changed:

```sh
git pull --ff-only
git submodule update --init --recursive
docker compose up -d --build --force-recreate odoo
docker compose logs -f --since 1m odoo
```

With the default `CAMPUS_AUTO_UPGRADE=true`, startup upgrades all campus addons.
Wait for `campus: upgrade complete`, then hard-refresh each already-open browser
tab. Deployments managing Odoo directly must upgrade both `ideastone_campus` and
`ideastone_erp`, restart Odoo, and refresh the browser assets. Existing users will
see the default menu plus Customize Navigation; their menu stays unchanged until
they save personal changes.
