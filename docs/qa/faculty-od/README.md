# Faculty OD reference preview

Reference: `Faculty_OD_Management_AI_Insights_Pending_Final.html`.
The faculty main content is scoped to `campus_faculty_od_reference`; the existing HOD template,
sidebar, top bar, request state machine and review permissions are preserved.
Shared Roboto typography remains in use. Reference gradients, white cards, icon tints,
pending/approved badges and pending-date layout apply to saved data as well as empty states.

## Verification

- `node --test docs/qa/faculty-od/ui.test.cjs`: 3 tests passed (class response ordering,
  note isolation and required return notes, pending-date ordering and expansion).
- Odoo `--test-tags=/ideastone_erp:TestStudentOD`: 8 tests passed, 0 failures/errors.
  Includes mentor/HOD boundaries, General/Special OD lifecycle, student resubmission,
  local submission-date analytics and incomplete class mapping.
- Ruff on `addons/ scripts/` and this preview seed; XML parsing; `git diff --check`.
- Browser: populated and empty lists, request details/history, class selection after refresh,
  search, paging, notes, return, student resubmission, forward to assigned HOD,
  Week/Month analytics, CSV contents and pending-action expansion.
- Viewports 1440, 768 and 320: no page/content overflow; tables scroll internally;
  mobile workflow stacks and review dialog/footer fit the viewport.

## Isolated local sample

`preview_seed.py` only accepts the database `campus_faculty_od_preview` and requires
`OD_FACULTY_PASSWORD` and `OD_HOD_PASSWORD` in its environment. Run it once through Odoo shell.
It uses the native student, mentor and HOD workflows. It creates a separate sample college,
24 students in ECE III A, a second class and an unrelated mentor for scope checks.
Primary class totals: 3 pending, 12 approved, 2 on OD today at seed time.
The insights are explainable rules over stored records, without an external AI service.
Sample data and preview accounts are not installed by the addon.
