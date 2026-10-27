# Owner Faculty & Staff reference preview

Reference: `Faculty_Staff_Module.html` supplied by the user.

The owner workspace exposes Staff directory, Leave Management and Payroll History.
The directory uses existing `op.faculty` records, including their teaching/non-teaching
classification and linked employee leave status. Department, category, search and
basic-profile views are projections of those records. Manage staff records and
Open staff record retain the native Odoo forms and access rules.

Leave applications reuse `campus.faculty.leave.ui`. The approval queue reads the
active college through the caller's record rules and uses native Odoo approval,
second approval and refusal actions. Insights are calculated from saved records;
no external AI integration or automatic payroll sync is claimed.

Payroll reuses `campus.payslip.get_history_data` and its existing employee scope,
currency, approval state and attendance treatment. Complete, salary and deductions
reports use the same year/month filters; CSV exports match the selected report.
Punch details remain available in an expandable section.

The shared sidebar, top bar and typography remain unchanged. The old owner staff
tabs are hidden; their underlying models and actions are retained for other
workspaces and native record management. The new skin is scoped to these three
owner client actions.

## Validation (27 October 2026)

- Module upgrade plus 33 selected backend integration tests: zero failures/errors.
  Includes directory counts, current-college isolation even when a user can access
  multiple companies, native leave decisions and the existing owner/leave workflows.
- Repository Ruff checks, XML parsing, JavaScript syntax and whitespace checks pass.
- Browser checks at 1440, 768 and 320 pixels: no page overflow; narrow tables scroll
  inside their panels. Mobile directory/profile, leave form/approval and payroll
  layouts were checked with populated records.
- Staff search, profile and native form opening, sample leave submission/approval,
  staff selection, report modes, date filters and a salary CSV download were checked.
- Rendered Roboto typography: desktop H1 31px, mobile H1 28px, H2 17px,
  H3 15px; the directory's navy welcome banner uses the shared 21px white heading.

## Local preview

The isolated `campus_owner_staff_preview` database contains a separate sample
college with INR, eight departments, 20 sample staff, leave requests and approved
August–October 2026 payslips. Main accounting data and the existing previews were
not modified. The preview runs at `http://owner-staff.localhost:18083`.

For deployment, upgrade `ideastone_campus` and `ideastone_erp` to load the three
client actions and refresh the shared assets. The existing theme, navigation,
Academics and Faculty Home integrations are retained.
