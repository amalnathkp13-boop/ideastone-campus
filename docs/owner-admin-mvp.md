# Owner/Admin MVP implementation map

Specification: ZcERP College ERP MVP Blueprint v1.0, 17 October 2026 (complete Markdown and 19-page PDF reviewed; ZIP contains the same two files).

## Phase 0: inspected architecture and reuse

- Runtime: Odoo 17 / PostgreSQL 16; `docker-compose.yml`, `odoo/`, `.github/workflows/ci.yml`.
- Auth: native Odoo sessions and existing OAuth/Keycloak configuration (`addons/ideastone_campus/data/sso.xml`). Keep `/web/login`, native `/web/dataset/call_kw`, record rules and ACLs. No alternate login or API application.
- Shell: existing OWL `CampusNavigation` / `CampusDashboard` in `addons/ideastone_erp/static/src/{js,xml}/dashboard.*`, and `faculty_workspace.scss`. Owner uses the same sidebar, utility header, responsive drawer and submodule strip as faculty.
- Academics: extend `op.academic.year`, `op.academic.term`, `op.department`, `op.course`, `op.batch`, `op.subject`; do not create parallel academic tables.
- Admissions: extend `crm.lead`, `op.admission`, `op.admission.register`; add only the missing verified-document checklist. Conversion reuses `op.student` and `op.student.course`.
- Students/guardians: existing persistent student and delegated `res.partner` contacts. Retain existing university register number separately from internal student number.
- Staff: existing `op.faculty` and `hr.employee`, not a new people directory.
- Teaching: existing `op.session`, `op.attendance.register/sheet/line` and faculty allocation rules. Preserve historic roster rows.
- Finance: extend `op.fees.terms/line`, `op.student.fees.details`, `account.move` and `account.payment`. Payment allocations use native receivable reconciliation, never a parallel balance ledger.
- Exams: extend `op.exam.session`, `op.exam`, `op.result.line` and existing grade definitions. Add guarded publication and explicit missing-entry state.
- Notices: extend `campus.circular`; preserve existing approval data.
- Tests: `addons/ideastone_erp/tests`, Odoo TransactionCase, ruff/XML checks, real clean install + upgrade, Playwright faculty regression in CI.

## Ordered delivery

1. Academic foundation, role ACLs, college boundaries and append-only audit.
2. Enquiry/application/documents/decisions and atomic retry-safe student enrolment.
3. Faculty allocation, timetable conflicts, roster/attendance/correction and shortage.
4. Native accounting fee assessment, partial/final payment, unique receipt and reversal.
5. Exam roster, missing/invalid marks, submission/lock/publication and reasoned reopen.
6. Saved-record dashboard, scoped source actions/reports, notices.
7. Validated import, demo-only seed, backend/browser/upgrade regression checks.

The new branch starts from the tested faculty workspace (PR #14), preserving that UI and its working modules. Existing legacy records are retained; additive fields opt existing workflows into the guarded MVP where appropriate. Global upstream uniqueness constraints are retained where stricter than organization-level uniqueness.

## Verification environment

Local Docker Desktop reports “unable to start”; database/runtime checks must execute on the repository's disposable CI Odoo/PostgreSQL environment. Local syntax, lint and XML checks are available. Actual results and remaining limitations will be recorded after implementation, without treating static checks as runtime proof.
