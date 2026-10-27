# Shared campus theme verification

Verified locally on 27 October 2026 (Asia/Kolkata), on branch
`codex/campus-ui-uniformity`.

The visual contract and reference choices are in [the design guide](../campus-design-system.md).
The base addon includes the same stylesheet in the frontend and backend bundles.
No business model, controller, permission, navigation structure or stored ERP
record was changed by the implementation.

## Rendered UI checks

| Area | Coverage |
| --- | --- |
| Student | All 13 modules at actual 319px and 1440px viewport widths |
| Parent | All 11 portal pages at 390px |
| Owner/admin | 13 module landing pages and 62 distinct submodule navigation entries, including native lists, forms and dialogs |
| Faculty | 12 module landing pages; examination upload workspace |
| HOD | Populated examination review workspace and approval-history dialog |
| COE | All 21 submodule pages, waiting for each page's own heading to render |
| Phone layouts | Faculty, HOD and COE pages at 319px; no document overflow |

`campus-theme.cjs` checks computed heading family, size, weight and color, metadata,
white card surfaces and 15px radius, primary-button typography and palette,
theme tokens and preserved FontAwesome glyph fonts. It was also executed through
the desktop browser's DOM API against the student, parent and representative role
pages. Text-font and document-overflow checks accompanied the page audits.

Status variants were audited from the compiled stylesheets. Present/approved,
pending/withheld, absent/invalid, excused/on-duty, issued and neutral states use
the shared semantic palette. User-assigned category colors and chart series stay
distinct. Saved HOD records confirmed the colored review chips and table styling.

## Regression checks

- 27 student/parent backend tests: zero failures and errors.
- 44 owner, VCET workspace, faculty leave and examination backend tests: zero
  failures and errors.
- Ruff, all addon XML, manifest parsing, changed JavaScript syntax, SCSS compilation
  and `git diff --check` passed.

These are local verification results; a new GitHub CI run has not been started.
The existing authenticated browser suites now call the shared visual assertions.

## Local previews

The working ERP is served at `http://localhost`. Faculty/HOD/COE workflow previews
use port 18081 on `faculty.localhost`, `hod.localhost` and `coe.localhost`.
Those three previews use the isolated `campus_uniform_preview` database, copied
from the existing question-paper preview, with dedicated temporary review users.
Existing preview services and their working branches were left intact.

The role preview loads the COE worktree's existing functional code with the same
shared theme overlaid on its base branding asset. Its combined temporary branding
file is local preview infrastructure, not a repository change. The implementation
in this branch is the independently registered shared stylesheet.

Screenshots and detailed audit results are saved locally in
`%TEMP%/campus-uniformity-preview/`. The database backup before deployment is
`%TEMP%/campus-before-uniformity-20261026.dump`.

No PR was created and no changes were pushed.
