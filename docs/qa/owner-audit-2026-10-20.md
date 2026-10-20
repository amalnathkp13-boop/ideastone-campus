# Owner workspace audit — 20 October 2026

## Scope

Audit of all 13 owner workspace modules on the local Odoo 17 / OpenEduCat app, using synthetic data in the disposable `ci` database. Covers the dashboard, admissions, students, academics, staff, timetable, attendance, fees, learning, examinations, communication, reports and settings. This branch follows the student and faculty/parent workflow fixes (PRs #34 and #36).

## Reproduced issues and fixes

1. **Staff Profile failed for owners; appraisal was absent.** The owner role could read the staff directory but lacked access to staff qualifications/documents and appraisal records. The UI showed a profile error and hid appraisal. Owner now inherits the existing HR operator role, retaining college record rules. Profile availability checks its supporting model. Profile and appraisal selectors use the active college, excluding unrelated shared demo records. Profile retries clear stale errors and details.
2. **ID & receipt numbering was missing.** The navigation referenced a nonexistent Odoo XML ID. It now uses `base.ir_sequence_form`, with the existing owner-only gate and college domain.
3. **Student filters could count the wrong enrolment.** A selected year could match one enrolment while the programme or section matched another. The KPI and drill-down counted a student absent from the CSV results. A correlated Odoo `any` domain now requires all placement filters on the same enrolment; programme totals apply those filters too. A regression test failed before this fix.
4. **Invalid report filters caused server errors.** The maximum calendar end date overflowed when building an exclusive upper bound; malformed dates/record IDs produced raw exceptions. The common filter boundary now raises actionable validation errors, including checks for invalid ID types and database integer bounds. Normal empty selections still work.
5. **Invalid JSON mappings crashed student import preview.** A JSON array or null passed the initial mapping logic and raised attribute/type errors. Preview now requires an object with named, nonempty string headers before reading rows. Failed preview creates no students.

6. **Empty module screens displayed raw HTML.** Owner navigation supplies action objects directly to Odoo; these bypass its normal action-loader HTML conversion. The shared navigation and dashboard drill-down now use Odoo OWL markup for trusted action help. The browser regression checks the rendered Rooms empty-state paragraph.

## Verification

- Local full Odoo suite: **89 tests, zero failures/errors**. Additional owner test run after the numbering fix: **16 tests, zero failures/errors**.
- Browser: signed in as the owner, opened all 13 module pages, inspected native admissions screens, saved and reloaded a staff qualification, saved an appraisal entry, and checked desktop/mobile behavior.
- All available action definitions and native views compile with owner permissions. The CI owner suite checks all 53 submodule actions, all 13 module pages, seven CSV exports, native subject save/reload, staff qualification save/reload, appraisal save, leave page, numbering settings, reporting error recovery, admission/payment idempotency and receipt PDF.
- Security regressions cover owner HR records, read-only denial, foreign college denial, and restricted staff-profile navigation.
- Ruff, JavaScript syntax and diff whitespace checks pass.

## Limits

Local synthetic-data and CI evidence do not certify every production configuration. External SSO, real LMS synchronization, email delivery and production data were not tested. Apply the module upgrade to enable inherited owner HR permissions; restarting alone does not apply XML security changes.
