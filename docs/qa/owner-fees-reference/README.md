# Owner Fees & payments reference

Reference: `FeeStructure_DepartmentCards.html`, supplied by the user.
Branch: `codex/owner-fees-reference`, based on main `072223a`.

## Scope

The owner Fees & payments middle section follows all eight reference pages:
Financial overview, Fee heads, Fee structures, Student fee accounts, Assign fee
structure, Invoices & dues, Overdue follow-up and Receipts. The existing sidebar
and top navigation shell are retained. Reference typography overrides are confined
to this workspace, including its entry dialogs; native accounting forms retain
the shared campus theme.

Department cards show actual GQ/MQ plans, annual amounts, publication status,
versions, effective dates and saved fee installments. Plan amounts show a range
when a department has different amounts across programmes, semesters or study
years. Counts and balances are computed from saved records rather than the
prototype's illustrative totals.

New department plans follow draft → review → owner publication. Published plans
and their lines cannot be edited; a new version retains the old assessments.
Assignments require matching college, academic year, programme, admission quota
and study year. Missing admission quotas are excluded, and repeated assignments
do not duplicate installments. Existing legacy fee structures keep their original
assignment workflow.

Invoice creation uses the existing fee assessment/invoice service. Posting,
concessions, receipt numbering, reconciliation, reversals and PDF acknowledgements
use native accounting controls. The payment form retains its prepared request
after a connection failure so a retry uses the same payment. Contact logs record
completed contact and a next action; they do not send communications. Insights
summarise saved finance records and never change student balances.

## Local preview

- URL: `http://fees.localhost:18086/web#action=880&cids=50`
- Login: `owner.fees.preview`
- Database: `owner_fees_reference_preview`
- Container: `ideastone-owner-fees-reference-preview`
- Host port bound only to `127.0.0.1:18086`.

The password is supplied separately and is not committed. Other local previews
and their databases were not modified.

`seed.py` is an opt-in, one-time Odoo-shell seed guarded to this database. Supply
`OWNER_FEES_PREVIEW_PASSWORD` through the environment and copy
`reference-records.json` to `/tmp/owner-fees-reference-records.json` in the shell
container. It creates six departments, twelve annual GQ/MQ plans, eight fee heads,
eighteen enrolled students, posted invoices, cash/UPI receipts, supplier payments
and internal follow-up logs. Academic year dates are April 2026–March 2027.

Browser verification added a ninth fee head, a posted ₹1,500 invoice, a ₹100 cash
receipt and a completed contact log. It published the EEE MQ plan and assigned its
six installments to the matching enrolment, then created version 2 and submitted
it for review. These
synthetic records remain available for review.

## Verification

- **183 ERP + AI regression tests passed**, zero failures/errors. The suite ran on
  a disposable copy; inherited preview students were archived in that test copy
  so existing tests that expect an empty student population remain isolated.
- Five new tests cover college/role access, review/publication, immutable plans,
  quota matching, duplicate-safe assignment, payment retries and balances,
  immutable internal contacts, and supplier reversals across academic periods.
- **32 responsive checks:** all eight pages at 1440, 768, 390 and 320 px, with no
  document/content horizontal overflow or overlapping grid children. Wide tables
  and installment editors scroll inside their own containers.
- **38 reference widget comparisons** match font family, size, weight, line height,
  letter spacing, text/background colors, border radius and padding.
- Native keyboard scrolling reached the bottom and returned to scroll position 0.
  The payment and structure dialogs fit a 320 px viewport.
- UI saves/reloads verified fee-head and contact persistence, invoice posting,
  the 40th receipt, and updated balances. Publishing a plan made it assignable;
  after assignment/reload the preview showed one already-assigned student, six
  existing installments, zero new charges and a disabled repeat button.
- Ruff, JavaScript syntax, XML parsing and Git whitespace checks passed.

`browser-verification.json` records layout/style checks and the browser scenarios.
Screenshots show desktop, phone, entry and department-breakdown views. Raw local
runtime/test logs are ignored by Git.
