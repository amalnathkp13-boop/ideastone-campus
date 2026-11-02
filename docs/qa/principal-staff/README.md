# Principal Faculty & Staff workspace

Reference: Faculty_Staff_Principal_Workspace.html. Only the main content and Principal staff submodule links are changed. Existing sidebar/top bar templates and other login workspaces are unchanged.

## Saved workflows

- Staff directory: department → teaching/non-teaching category → filtered staff list → basic profile. Includes linked faculty/employee records, standalone employees, and approved leave status in the active college.
- New staff applications: saved applicant, position, department, qualifications, experience, supporting documents, interview date and panel review. Principal decisions are serialized, recorded with reviewer/time/note, and locked after approval/rejection. Approval requires verified documents; rejection requires a reason. HR can prepare applications and schedule interviews. No employment account is created automatically.
- Staff Attendance & Payroll: company-scoped punch reporting plus approved payroll totals. Year/month filters and all three report views work. CSV export follows the selected report and filters and protects spreadsheet text cells from formula injection. Existing payroll classification handles working days, holidays, approved leave, and late permission; this screen never computes or posts deductions.

The reference's prototype-only reset/toast actions are connected to saved workflows. Reset clears filters; application details and document editing open functional popups. A New application button provides record entry. Sample-only labels are conditional on the college's demonstration flag.

## Local verification

- Eight Principal backend tests: access/navigation, recruitment validation/audit/immutable decisions, unique application references across colleges, directory scope, punch filtering, and approved-only payroll totals.
- Ruff, XML/Python/JavaScript syntax, and Sass compilation.
- Browser: department/category/profile navigation, search/designation filtering, recruitment search/status/reset, application creation and document editing, blocked incomplete-document approval, audited approval, required rejection reason, modal keyboard focus/Escape, salary/deduction views, and CSV download (header + 20 staff rows).
- Desktop 1440/1280, tablet 820 and phones 390/320. Tables scroll within their panels; popups fit and scroll vertically when needed.
- Reference fonts, heading sizes, colors, gradients and cards are scoped to this workspace so new data uses the same styles.

## Preview

Database: `principal_staff_preview`; Docker: `ideastone-principal-staff-preview`, port 18096.

- Directory: http://principal-staff.localhost:18096/web#action=943&cids=27
- Applications: http://principal-staff.localhost:18096/web#action=944&cids=27
- Attendance/payroll: http://principal-staff.localhost:18096/web#action=945&cids=27

`seed.py` refuses other database names. It creates an isolated demonstration college with the reference's 20 staff, seven initial recruitment records, sample attendance, and seven staff payroll histories. Browser verification adds one clearly named synthetic applicant. Payroll samples use the normal compute/submit/approve workflow. Passwords are generated at runtime and are not committed.

The sample JSON is a data-only extraction of the supplied reference. No samples are automatically installed on production databases. No push or PR before preview approval.
