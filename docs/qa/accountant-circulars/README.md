# Accountant fee circulars

The Fee circulars sidebar entry and dashboard draft-circular shortcut open the reference-based workspace. The existing sidebar is retained. Typography, palette, card geometry, activity panels, register and circular form follow `Fee_Circulars_Module.html`; totals and rows come from saved college records.

- New circular saves a real `campus.circular` record. Blank references use the `FC/year/number` sequence; references are unique within each college.
- Drafts can be reopened and edited. A stale edit is rejected instead of overwriting a newer change. Released circulars are protected from edits and can be archived.
- Categories are financial notice subtypes. Every record remains in the Fees permission boundary, including Examination, Event and General notices.
- Audience and department scope control student and guardian portal visibility. Accounts office notices require Staff and target the Accountant group.
- Scheduled publication uses the signed-in user's timezone. The existing publication cron releases notices at the saved time and respects effective/expiry dates. Published details show actual portal acknowledgement counts.
- Search, audience/category filters, status buttons, Reset and View archive filter the saved register. Navigation arrows paginate ten records at a time; Fee related circulars scrolls to the register.

## Local preview

Use the isolated `accountant_ui_preview` database on port 18069 and its INR company 13. `seed.py` asserts that database before adding synthetic drafts, published notices, future schedules, an archive and an acknowledgement. It is idempotent and must not run against the working college database.

Upgrade `ideastone_erp` before running the seed in `odoo shell`. The preview data is stored in PostgreSQL; fresh entries use the same shared styles as existing rows.

## Verification

Run Odoo with `--test-enable --stop-after-init --test-tags /ideastone_erp:TestAccountantFeeCirculars,/ideastone_erp:TestAccountantWorkspace`. The six post-install tests pass, covering persistence, safe message conversion, publication/archive, stale edits, schedules, acknowledgements, audience/department scope and college permissions. Existing parent portal tests also pass. Targeted owner publication and student acknowledgement tests cover the shared notice paths.

Browser checks cover saved draft creation, reload/reopen, edit, publish, immutable published details, archive, future schedule validation/save/reopen, category/audience/status/search filters, empty results, Reset, pagination boundaries, archive navigation, modal close/cancel and register scrolling. A form-created circular and future schedule remain in the preview database.

At 1440, 820, 390 and 320 pixels, the page has no horizontal overflow. Cards use four, two and one columns as space allows. Narrow tables and module tabs scroll locally; the modal has one column on phones and scrolls vertically within the viewport. Computed desktop styles confirm Inter/Segoe UI/Arial, 30px/700 headings, 27px/750 KPI values, 17px/700 panel headings, 12px/700 table headers and the reference colors after new records are saved.

Repository Ruff checks, XML parsing, JavaScript syntax, navigation reconciliation and the ten session/navigation Node tests pass. No PR is created for this branch.
