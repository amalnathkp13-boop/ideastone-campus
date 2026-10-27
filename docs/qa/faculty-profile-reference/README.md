# Faculty profile and payroll reference

Branch: `codex/faculty-profile-payroll-reference`, based on `origin/main` (`a0bc5a2`).
Reference: the user-supplied `Faculty_Profile_Payroll_Leave_Application_FINAL_VERIFIED.html`.

Only the faculty middle content and the staff module's submodule entries change.
The existing sidebar, logo, navigation styling and main-admin screens are retained.
The seven reference submodules replace the previous faculty staff-module list:

1. My staff profile — the default whenever the module is opened or reopened.
2. Staff qualifications and documents.
3. Faculty development and appraisal.
4. Salary agreements.
5. Monthly payroll.
6. Payroll History.
7. Leave requests.

The reference's initial development tab does not control the implementation's
landing page. The profile action and the module entry explicitly open My staff
profile. Explicit submodule URLs remain reloadable on their selected page.

## Saved records and permissions

Contact edits update the linked faculty's permitted contact fields. Official
employment fields remain maintained by HR. Documents use the existing faculty
detail register and its HR verification workflow; supported uploads are PDF, PNG
and JPEG, up to 10 MB. Development records and M.Phil supervision use the existing
achievement register. Only drafts can be edited in this workspace; submission and
review keep the existing approval transitions.

Salary agreements expose only the linked employee's approved terms in the active
college, through a limited read projection; bank references are excluded. Monthly
payroll and history read the same approved/completed campus payslips as the main
admin, including paid late permissions and full-day late deductions. No payroll
calculation or approval logic is replaced. Payslip PDFs use the existing report.

Leave requests use `campus.faculty.leave.ui` and Odoo's allocation, half-day and
approval rules. The HOD status tab shows the faculty member's own requests; it does
not give faculty approval permission. Insight cards describe saved records and
clearly state that no external AI provider is configured.

## Local preview

- URL: `http://faculty-profile.localhost:18084/web#action=772&cids=47`
- Login: `faculty.profile.preview` (password supplied separately).
- Database: `faculty_profile_reference_preview`.
- Container: `ideastone-faculty-profile-reference-preview`, bound only to
  `127.0.0.1:18084`.
- Other localhost previews and databases were left running and unchanged.

`seed.py` is an opt-in, one-time fixture guarded to this named database. Supply its
password through `FACULTY_PROFILE_PREVIEW_PASSWORD`; no password is committed.
It creates a synthetic college and faculty/employee, six supporting documents,
six development activities, three approved salary agreements/payslips, actual
sample attendance, an eight-day casual leave allocation, and approved/pending
leave requests. Reviewer actions use an explicitly permissioned sample HR user.

The October sample has three late days, two paid permissions and one deducted day:
gross INR 70,000, late deduction INR 3,684.21, net INR 58,765.79. August and September
net pay is INR 62,750. These are calculated synthetic records, not copied totals.

After browser-entry verification there are seven document records and eight
development/supervision records. The contact mobile was changed and saved, and
an additional sample leave request was submitted for 23 November 2026. All sample
names, evidence files, contacts and financial amounts are for interface testing.

## Verification

- Full ERP + AI module regression upgrade: **156 tests passed, zero failures or
  errors** (`regression-tests.log`). Four new tests cover seven-entry navigation,
  profile-first routing metadata, protected fields, own/cross-college records,
  uploads and verification, development submission, approved-only salary access,
  bank-field exclusion and agreement/payslip isolation. Two initial test-fixture
  mistakes were corrected before this successful complete rerun.
- Ruff across `addons/` and `scripts/`, JavaScript syntax, XML parsing and Git
  whitespace checks passed.
- **28 responsive checks:** all seven pages at 1440, 768, 390 and 320 px. No page
  overflow, overlapping sibling cards or incorrectly narrow panels. Wide tables
  scroll inside their containers. The document form also fits at 390 and 320 px.
- **10 typography comparisons** matched font family, size, weight, color and line
  height against the rendered reference.
- Browser entry: contact save/reload, a PDF upload/save, an activity with evidence,
  M.Phil supervision save/reload, leave submission/reload, readonly approval
  status view, readonly approved agreement details, payroll month selection and
  an actual payslip PDF download all passed.
- Payroll filters selected September and Salary only. Export produced one row
  with Period and Net columns, matching the selected view.
- Returning to the main module from development opened My staff profile. Final
  validation recorded no browser errors. Corrected development-time binding and
  scoped grid issues are recorded in `browser-verification.json`.

Screenshots show each desktop page, selected phone layouts, and the phone upload
form. Raw local logs are ignored by Git. The supplied source document is unchanged.
