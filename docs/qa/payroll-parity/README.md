# Admin and faculty payroll parity

The faculty history now calls the same approved-payslip projection as the admin history. Both display the college currency, late days, paid permissions, deducted days/amount/dates, punch entries and identical CSV columns. Month filters select the same payslip for the summary and punch details. Both views use the same typography and colours; the staff selector remains admin-only.

The existing payroll calculator retains its policy: the first punch strictly after 09:00 on a scheduled local working day counts once per day; the first two late days in a month are paid; every later late day deducts a full daily salary. The allowance resets monthly. Holidays and approved leave retain the existing exclusions. Payroll treatment in the history is read from the approved payslip snapshot, while displayed check-in/out times come from attendance.

Staff RPC access is limited to their own linked employee in the active college and approved/completed pay periods. No other staff directory or payroll mutation rights are added. Approved totals are not recalculated when the page opens.

## Validation

- Full clean ERP/AI installation: 130 tests, zero failures/errors.
- Existing-database upgrade and workflow/privacy checks: 35 tests, zero failures/errors.
- Ruff, XML parsing and diff whitespace checks pass.
- Browser comparison: matching summaries, history tables, punch treatments, currency, table font/size/colour and byte-identical CSV exports.
- August filter: one late day, one paid permission, no deduction; September: four late days, two paid permissions, two deducted days and INR 2,000 deduction; an empty month retains the policy and explicitly unprocessed totals.
- Tests retain month reset/local-time, exactly-09:00, full-day salary amounts, attendance-correction snapshot integrity, other-staff/college isolation and read-only payroll guards.

Preview database: `payroll_parity_preview`; container: `ideastone-payroll-parity-preview`; loopback port 18075. The guarded `seed.py` creates only fictional users and payroll in this database, using a password supplied through `PAYROLL_QA_PASSWORD`. It cannot run against the existing campus or examinations preview database.

Faculty preview: <http://payroll-faculty.localhost:18075/web#action=751>.
Admin preview: <http://payroll-admin.localhost:18075/web#action=751>.
Browser evidence and synthetic exports are in this directory. Existing campus and examination services/data are preserved.
