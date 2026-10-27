# Main-admin Academics reference

Branch: `codex/admin-academics-reference`, based on merged `main` (`a0bc5a2`).

The supplied `ideastone_academics_main_dashboard (3).html` is the visual reference for the middle content area. The existing campus sidebar, logo, navigation styling and other modules are unchanged. The Academics menu now opens the new overview and its six directories through registered client actions.

## Delivered pages and data

- Overview: active programmes, recorded lesson delivery, current sections, setup checks, monthly delivery/classes, upcoming semester/exam dates and curriculum readiness.
- Academic years: current year, progress, next-year setup, timeline, searchable records and status/date filters.
- Departments: enrollment, configured intake capacity, sections, faculty and department details.
- Programmes: department, level, duration, directory cards and filters.
- Semesters: academic year, programme, sequence, period type and dates.
- Sections: programme, academic year, semester, mapping status and distribution.
- Subjects & curriculum: department, semester, credits, distribution and setup checks.

Add, view and edit forms use the same scoped typography and palette. All six forms save the existing academic models. The UI renders new and existing records with the same templates. Counts and insights derive from saved records; the reference's illustrative totals and synthetic charts are not hardcoded. Insight cards contain explainable setup/delivery signals and do not call an external AI provider.

Writes require registrar permission plus the model's ACL and record rules. Linked records must belong to the active college. Setting the current academic year locks the college row and flushes the previous current-year flag before creating/updating the new year. Legacy source actions remain available to existing ERP workflows.

## Localhost sample preview

- URL: <http://academics.localhost:18076/web#action=869&cids=1&menu_id=515>
- Database: `academics_reference_preview` (separate from the existing localhost databases).
- Container: `ideastone-academics-reference-preview`, bound to `127.0.0.1:18076`.
- Login: `academics.admin.preview`. The password is supplied through `ACADEMICS_PREVIEW_PASSWORD` when seeding; it is not stored in this repository.
- Addons are mounted from this branch's worktree. Other localhost services were left running.

`sample-records.json` contains illustrative directory names and attributes extracted from the supplied HTML. `seed.py` accepts only this named preview database and refuses to run after its sample administrator exists. It populates actual ERP records, including fictional students, teaching plans and class sessions. It does not modify a live college database.

After browser entry checks, the preview has 5 academic years, 13 departments, 27 programmes, 16 semesters, 21 sections and 12 subjects. There are 24 fictional enrolled students, one sample faculty coordinator and ten teaching plans with 100 planned / 86 delivered hours.

## Validation

- Fresh supported installation of `ideastone_erp,ideastone_ai` with upstream demo fixtures: **156 post-install tests passed, zero failures/errors** (`regression-tests.log`). This includes the existing examination/question-paper and payroll suites.
- Final module-upgrade run of `TestAcademicsUI`: **4 tests passed, zero failures/errors** (`final-tests.log`). Covers all six create projections, editing, current-year switching, real capacity/enrollment/delivery, cross-college denial, read-only/unauthorized accounts and invalid input.
- Ruff, JavaScript syntax, XML parsing and `git diff --check` passed.
- Created a department, programme, year, semester, section and subject through the browser forms. Edited subject credits to 3.50, reloaded the browser and verified persistence. Combined search/credit filters and Clear filters worked.
- Compared 11 representative text styles directly against the rendered reference: font family, size, weight, color and line height all match. New/existing programme card text and backgrounds match each other.
- Checked every page at **1440, 768, 390 and 320 pixels**: 28 checks, no horizontal page overflow. Wide tables scroll within their own containers. The mobile form fits its viewport.
- Final preview reload has zero new client errors. `browser-verification.json` records the earlier corrected form binding error separately.

Screenshots: `overview-desktop.png`, `programmes-desktop.png`, `curriculum-desktop.png`, `curriculum-tablet.png`, `curriculum-phone.png`, `subject-form-phone.png`.

Local raw logs are ignored by Git. No runtime passwords or student information from an actual institution are included in these artifacts.
