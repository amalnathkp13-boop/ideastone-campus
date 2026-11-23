# Owner Campus Placements preview

The owner workspace exposes the seven sections from `Ideastone_Campus_Placements.html`: Overview, Departments, Students, Placement drives, Offers & outcomes, Past records, and AI insights. It retains the existing ERP header and sidebar. The seven sections appear once in the standard owner top navigation, matching the other owner pages; the embedded duplicate tab row is hidden.

## Saved workflows

- Placement profiles supply participation, graduating batch, verified CGPA, readiness, and resume status. Existing placement profile forms include the new fields. Missing scores or participation are shown as unrecorded rather than fabricated values.
- The department form stores the placement coordinator and display order, so department drilldowns use maintained college information.
- Add placement drive validates the selected college, departments, dates, CGPA, and package; creates and approves a native placement drive; and makes it available to the existing student placement workflow. A form request key prevents a repeated network request from creating a second drive.
- Drive shortlists use the same programme, section, percentage, arrears, cohort, and CGPA eligibility checks as the student placement portal. Calendar and shortlist downloads are generated from the selected saved drive.
- Offers come from selected placement candidates. The existing candidate form records acceptance and actual joining dates. Placement totals count distinct students, while the offer register retains multiple offers.
- Improvement plans persist against the college, graduating batch, department, and optional student. The backend recomputes affected students and rejects duplicate plans. Plan progress can be maintained in the native placement improvement plan form.
- Insight cards are transparent rules over recorded readiness, resumes, and department outcomes. The 85% target is a planning scenario, not a predictive model. No external AI service or notification delivery is invoked.

## Isolated sample data

`seed.py` runs only against `owner_placements_preview`, requires `OWNER_PLACEMENTS_PREVIEW_PASSWORD`, and uses `reference_data.json` for three graduating batches. It creates real profiles, enrolments, published academic results, offers, and upcoming drives. It does not add production demo records through the module manifest.

The reset action is available only for the configured sample company in that exact database. It archives drives added during preview and removes preview-created plans; it keeps the original seed and application history.

## Verification

Backend tests: Odoo test tag `/ideastone_erp:TestOwnerPlacements`.

Browser checks: run `node docs/qa/owner-placements/ui.cjs` with Playwright available and `OWNER_PLACEMENTS_PREVIEW_PASSWORD` set. Optional variables are `OWNER_PLACEMENTS_PREVIEW_BASE`, `OWNER_PLACEMENTS_PREVIEW_OUT`, and `OWNER_PLACEMENTS_NONOWNER_LOGIN`. This script is for the isolated preview only: it creates a test drive and plan, checks persistence, then resets preview additions.

Coverage includes seven-section navigation, original shell, reference colors, drilldowns, search, CSV and calendar exports, form validation, saved records after reload, 320/390/768/1440 pixel layouts, modal bounds, print dispatch, and anonymous/non-owner access denial.
