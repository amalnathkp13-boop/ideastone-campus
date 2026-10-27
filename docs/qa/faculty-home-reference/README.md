# Faculty Home reference implementation

Reference: `faculty_dashboard_with_departments.html` supplied by the user.
Branch: `codex/faculty-home-reference` (based on `a0bc5a2`).

## Scope

The faculty Home content follows the reference overview and department directory.
Home's subnavigation contains only Faculty overview and My departments; Find a
module remains available under the existing Search module.
The existing campus sidebar, top bar, personal tasks, attendance, assessments and
faculty → HOD → COE question-paper workflows remain in place. Home links open those
existing workflows. This Home is enabled for faculty accounts; management, HOD and
COE continue to use their existing overviews.

The reference's typography, colors, gradient, spacing, borders, rounded cards and
directory table are scoped to the new content. Long content wraps, card grids
collapse on smaller devices, and wide tables scroll within their own panels.

Overview values come from saved records: confirmed teaching allocations in the
current academic year, active current enrolments, completed attendance registers,
published assessment results, the faculty member's personal tasks, question-paper
submissions and published notices. The current-year lookup also supports an
academic year covering today's date when no year has been explicitly marked current.
Teaching insights explain those records; they do not claim to run an AI model.

My departments follows department → year of study → section → student roster.
Each request checks the complete allocation hierarchy and active college. Student
details are returned only for an allocated section. Normal ORM ACLs and record
rules apply, in addition to explicit college and faculty filters.

## Local preview

- URL: `http://faculty-home.localhost:18078/web`
- Login: `faculty.home.preview`
- Database: `faculty_home_reference_preview`
- Container: `ideastone-faculty-home-reference-preview`
- The host port is bound to `127.0.0.1` only.

The password is supplied separately; it is not stored in this repository.
The existing localhost previews and their databases were not modified.

`seed.py` is a guarded, one-time Odoo-shell seed for this named database only.
Supply the password through `FACULTY_HOME_PREVIEW_PASSWORD` and copy
`sample-students.json` into the shell container as `/tmp/faculty-home-students.json`.
It requires the installed campus modules and a current academic year covering today.

Synthetic preview data at verification on 27 October 2026:

- 3 departments, 10 allocated sections and 126 current students.
- 4 classes today, 2 completed, 2 awaiting attendance submission.
- Attendance rates of 82%, 76% and 91% from 30 completed registers.
- Published assessment averages of 78%, 72% and 86%.
- 5 open tasks, 2 draft question papers and a published timetable notice.

Dates and next-class status use the logged-in faculty member's timezone. These
live counts naturally change as time passes or saved records change.

## Validation

- ERP + AI module regression upgrade: **157 tests passed, 0 failures, 0 errors**.
- Faculty Home focused tests: **5 tests passed, 0 failures, 0 errors**.
  They cover navigation, new allocation/enrolment refresh, unpublished marks,
  attendance submission, archived students, personal task privacy, historic years,
  malformed IDs and attempts to access unallocated or foreign-college records.
- Ruff checks across `addons/` and `scripts/`, JavaScript syntax checks, XML parsing
  and `git diff --check` passed.
- **20 responsive checks:** overview, departments, years, sections and student
  roster at 1440, 768, 390 and 320 px. No page/content horizontal overflow or
  sibling card overlap; table overflow remains local to scrollable panels.
- **12 typography comparisons** with the supplied HTML matched font family, size,
  weight, color and line height.
- Native UI new-entry check: creating a personal task changed the Home task count
  from 5 to 6; browser reload retained 6; completing the task restored 5. The saved
  sample remains in recent activity as completed.
- Timetable and examination buttons opened existing faculty workspaces. The
  department hierarchy, roster and all Back steps were verified in the browser.
- No browser console errors were recorded during this verification.

Detailed results are in `browser-verification.json`. Screenshots show the desktop
overview, department cards and student roster, plus phone overview and roster.
Those reference-alignment screenshots precede the navigation cleanup;
`home-navigation-updated.png` shows the final two-item Home navigation after reload.
Raw local Odoo logs are ignored by Git.
