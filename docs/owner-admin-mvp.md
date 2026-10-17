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

Local Docker Desktop reports “unable to start”; real database/runtime checks executed on the repository's disposable CI Odoo/PostgreSQL environment. Local ruff, XML and JavaScript syntax checks also passed.

Verified application commit: `5517110a15f4663abd61f572cc8604463ab1fdcf`. [Full passing CI run](https://github.com/amalnathkp13-boop/ideastone-campus/actions/runs/39017755544).

- Clean Odoo 17/PostgreSQL 16 install: **48 tests, 0 failures, 0 errors**, including all existing faculty/security/portal regressions and twelve new Owner workflow tests.
- Faculty Playwright regression: real task/assessment persistence and existing responsive/navigation checks passed.
- Owner Playwright: twelve modules, **43 submodule views**, seven real CSV exports, form save/reload, live KPI reconciliation, simultaneous conversion and payment retries, native receipt PDF, shared chart scale, 1024px desktop and 390px mobile drawer/overflow checks passed. Browser console errors: **0**.
- Upgrade of the installed/seeded database passed. Odoo and OpenOlat image builds, ruff/XML/shell/compose validation passed.
- Visually inspected desktop overview, charts, native subject form, mobile screen and rendered receipt PDF. Verified evidence and source provenance are under [`qa/owner-mvp/evidence`](qa/owner-mvp/evidence). Dashboard screenshots show the initial three-student ₹300/₹200 fixture; final verification records show four students and ₹400/₹100 after the concurrent workflow checks.

No known blocking failure remains for the specified Owner MVP. The operational boundaries below remain explicit; production deployment was not performed. This evidence-only documentation commit does not alter the verified application code.

## Changed files and responsibilities

| Files under `addons/ideastone_erp/` | Responsibility |
| --- | --- |
| `models/mvp_academics.py` | Active-college academic defaults, current year uniqueness, semester/section validation, dated enrolment history |
| `models/mvp_admissions.py` | CRM enquiry, document decisions, admission state machine, retry-safe conversion, student profile and withdrawal |
| `models/mvp_attendance.py` | Resource overlap locks, dated rosters, unique session attendance, submission and reasoned correction |
| `models/mvp_fees.py` | Existing fee plans/assessments, concessions, native invoicing/reconciliation, payment retry, receipts/reversal, immutable posted evidence |
| `models/mvp_exams.py` | Assigned-faculty marks, missing/zero distinction, complete grade bands, submit/lock/publish/reopen |
| `models/mvp_audit.py` | Append-only actor/company/reason/details audit and private guard helpers |
| `models/mvp_communication.py` | Native circular scheduling, publication and audience controls; management read-only guard and configuration audit |
| `models/mvp_dashboard.py` | Live metrics, charts, source actions and seven scoped CSV report types |
| `models/mvp_import.py` | UTF-8 CSV preview, field mapping, duplicate/error checks and atomic commit |
| `models/academic_security.py`, `faculty_detail.py`, `attendance_export.py` | Extend existing permission checks for registrar/exam officer and keep faculty shortage calculations consistent |
| `security/mvp.xml`, `security/workspace.xml`, `security/faculty_tools.xml` | Role ACLs, global college/department/assignment/audience rules, existing faculty compatibility |
| `data/mvp.xml` | Student/receipt numbering and notice cron |
| `views/mvp.xml`, `mvp_search.xml`, `mvp_reports.xml` | Native forms, workflow controls, search/filter/grouping, receipt QWeb PDF |
| `static/src/js/dashboard.js`, `static/src/xml/dashboard.xml`, `owner.xml`, `static/src/scss/owner.scss` | Shared faculty shell, twelve Owner modules, live overview, responsive charts and loading/error/empty states |
| `__manifest__.py`, `models/__init__.py`, `tests/__init__.py` | Additive version, model/data/asset/test registration |
| `tests/test_owner_mvp.py` | Database workflow, financial, role, audience and history regression tests |

`.github/workflows/ci.yml` adds real Owner lifecycle/UI verification to the existing install, faculty regression, upgrade and image-build pipeline. `docs/qa/owner-mvp/{seed.py,browser.cjs}` contains the disposable fixture and browser checks.

## Permission behavior

| Role | Allowed workflow scope |
| --- | --- |
| Owner | Registrar + financial/exam/concession roles; users/role administration and sequence configuration |
| Registrar | Academic setup, admissions, student/enrolment history, faculty directory, timetable, notices, imports and academic reports; no fee posting or marks publication unless separately granted |
| Admissions officer | Enquiries, document review, admission decisions and approved conversion; no accounting or marks editing |
| Accountant | Fee plans, assessments, native invoices/payment allocation, receipts/reversals and financial exports; cannot edit admissions or marks |
| Examination officer | Exam setup, grades, assigned marks administration, approve/publish/reopen and result exports; cannot edit payments |
| HOD | Read-only department-scoped academic/student/faculty data; a missing department denies scoped records |
| Faculty | Existing faculty UI and permissions; managed student/exam reads and marks writes limited to teaching/exam assignments |
| Management reporting | Read-only dashboard and authorized academic/financial reports; no business writes or security administration |

All workflow actions check backend ACLs/record rules. Hiding a menu does not grant or remove access. Trusted action-definition metadata alone is read with elevated access; business queries and exports retain caller permissions. Narrow internal existence checks protect history without returning other users' records. Audit creation is internal and append-only.

## Workflow and migration decisions

- Install/upgrade adds fields, rules, views and new checklist/audit/transient tables. It does not rebuild or copy the existing student, academic or accounting tables. No vendor files are changed.
- `campus_managed` opts records into guarded admissions, attendance, fee and exam workflows. New year-configured attendance/exams automatically opt in, including calls from native forms. Legacy records retain existing behavior; new faculty rules explicitly preserve students without legacy enrolments.
- Academic/session/admission/fee defaults use the active college, not the user's default college. Older shared master records remain readable where the existing schema allowed a blank company; Owner action lists and reports select the active college.
- PostgreSQL row locks serialize conversion, intake capacity, timetable resource allocation, roster decisions and payments. Native request transactions keep conversion atomic. Retrying the same saved payment request returns its existing receipt.
- Receipt numbers use the existing `ir.sequence` service and a database uniqueness constraint. Receipts never reuse numbers. A native payment allocated to one college invoice is automatically given the same receipt evidence, including when collected through Odoo's original payment form.
- Invoice payments use native `account.payment.register` and receivable reconciliation. Posted invoice/receipt financial lines cannot be overwritten or reset to draft. Reasoned native journal reversal restores the receivable balance while retaining the original receipt.
- Finishing/transferring an enrolment records its last eligible day; withdrawal/graduation closes running dated placements. Existing attendance, marks and fee rows remain. A fresh placement is used for later semesters/sections.
- Grade rules are configured integer percentage bands, validated for full 0–100 coverage before publication. Missing marks remain missing; entering `0` explicitly records zero. A published/locked grade scale cannot be silently changed.
- Notices reuse `campus.circular`. Staff reads enforce publication date, expiry, group, programme/section teaching allocation, college and audience. Registrar can manage drafts; management reporting can review them without editing.
- The navy/blue faculty shell is intentionally reused in response to the user's latest visual requirement. Owner forms retain native controls and the shared sidebar/topbar, rather than introducing a separate theme/application.

## Demonstration and reset

The QA fixture is **not** a production/demo installation hook. It asserts database name `ci`, creates an explicitly labeled synthetic college and uses `example.test` contacts. No seeded KPI values are embedded in the UI. The initial dashboard derives three students, submitted attendance, a real ₹500 invoice/₹300 receipt and its ₹200 balance from saved records. Browser conversion/payment checks then change those underlying records and assert that the dashboard changes with them.

Reproduce using the existing CI `Owner lifecycle and UI on disposable Odoo` step: pass a newly generated `FACULTY_QA_PASSWORD`, execute `docs/qa/owner-mvp/seed.py` through Odoo shell on the disposable `ci` database, and run `browser.cjs` with `OWNER_QA_OUT` and Playwright available through `NODE_PATH`. It logs in as `owner.ui.qa` and uses no production login. The seed is for a fresh database, not repeated import into an existing college.

Reset by discarding only that disposable database/container and the `faculty-ci-data` CI volume; the workflow teardown already removes them. Do not delete production students, receipts or audit entries to reset a demo.

## Operating boundaries and Phase 2

- Current fee balances use native reconciliation. Historical as-of dues reconstruct retained MVP receipt/reversal dates; historical manual journal allocations imported from another system need reconciliation-history migration before those old as-of balances can be certified.
- Reports are deliberately bounded to three years/50,000 source records per request. Staff can narrow year/programme/date filters and use standard native list pagination. Large institutional analytics should use batched aggregation later.
- Scheduling is in-app publication via hourly cron. No email/SMS/WhatsApp delivery is claimed. Student/parent delivery channels and external payment providers remain Phase 2.
- The existing working LMS/library/transport/hostel/payroll modules are retained; this Owner MVP does not replace them. Production deployment, accounting chart setup, real grade policy and any imported-history backfill remain separate operational work.
