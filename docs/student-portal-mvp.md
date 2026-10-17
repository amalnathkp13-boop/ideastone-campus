# Student Portal implementation map

Specification: complete Student Portal blueprint (Markdown; companion PDF has 11 pages; package also contains DOCX and README). This work extends the Owner/Admin implementation in PR #15, which depends on faculty PR #14.

## Discovery before implementation

- Authentication: native Odoo portal users, `/web/login`, existing `CampusHome.web_login` redirect to `/my/campus`. Keep existing sessions, CSRF and password/security flow.
- Identity: existing `op.student.user_id`; parent access through `res.users.child_ids` remains a separate legacy parent workflow. The Student service must require one active, directly linked student in a permitted college; no client-supplied student identifier is authoritative.
- Existing HTTP routes/templates: `controllers/portal.py`, `views/portal.xml`; preserve parent and faculty behavior while extending the student entry.
- Academics: `op.student.course`, `op.course`, `op.subject`, `op.session`. Use dated enrolments and the existing timetable.
- Attendance: `op.attendance.line/sheet`, company-configured threshold/excused policy and Owner aggregation logic. No independent attendance ledger.
- Finance: `account.move/payment`, posted student fee assessments and native receipt report from Owner MVP. No new balance ledger, simulated settlement or unconfigured payment button.
- Exams: `op.exam/result.line`; existing native schedule state and MVP publication state. Add a guarded schedule-release marker for managed exams; do not invent hall tickets or CGPA rules.
- Notices/materials: `campus.circular` and `campus.digital.resource`; add per-student read state and enforce student-specific academic audiences in the projection.
- Requests/help: extend `campus.service.request`, its existing staff workflow and secure document storage. Add a small configurable request catalogue and public status history, rather than duplicate certificate/ticket tables.
- Library: existing `op.media.movement`, college-scoped media units and approved digital resources. Enable only when the college has applicable data.
- UI: reuse the faculty/Owner navy/blue design tokens, icons and sidebar/submodule pattern; provide a calmer portal shell without owner controls. Native website/QWeb pages and progressive enhancement, not a new application/framework.
- Tests: existing Odoo TransactionCase/HttpCase and disposable Odoo/PostgreSQL Playwright CI. Owner/faculty suites remain enabled.

## Ordered phases

1. Strict identity, authenticated routes, student-only shell, no-store responses and native logout/security.
2. Saved-record dashboard/profile, controlled contact edits and correction requests.
3. Enrolments, scoped materials, timetable and policy-consistent attendance.
4. Posted ledger, receipt history and authenticated official receipt download.
5. Released schedules and published results; honest absence of configured hall tickets/payment gateway.
6. Notice read state, reusable request/support workflow, secure uploads/downloads and scoped library data.
7. Role/IDOR, persistence, upload, responsive, navigation and regression verification; demo-only fixture and previews.

## What is implemented

The native `/my/campus` student landing opens the new shell. Its twelve applicable destinations are Dashboard, Profile, Academics, Timetable, Attendance, Examinations & Results, Fees & Payments, Notices & Calendar, Requests & Certificates, Library, Help & Feedback and Account & Preferences. Library is omitted when there are no applicable holdings, loans or approved digital resources. Parent logins retain the existing separate child-selection workflow.

| Area | Saved source and behavior |
| --- | --- |
| Dashboard | Five scoped drilldowns: remaining classes, policy-calculated attendance, posted fees due, released upcoming exams and unread targeted notices. Attendance bars and collection progress use the same returned records as the detail pages. |
| Profile | Official student number, register number, admission status, programme and guardians are read-only. The college can enable the narrow phone/mobile/address edit form; official corrections go through a request. Own admission documents have authenticated downloads. |
| Academics | Dated enrolment selection, actual programme subjects, credits and timetable faculty allocations. Only approved resources for the student's subjects and permitted sections can be downloaded. |
| Timetable | Confirmed/cancelled authoritative sessions, local timezone dates, faculty, room and update timestamp. Today/week/selected-period filters do not manufacture classes. |
| Attendance | Submitted attendance only, own student and selected section/period. Cancelled sessions are excluded; late and excused behavior match Owner policy. Subject percentages, shortage text, eligible denominator and monthly trend are derived from records. A trend needs at least two recorded months. |
| Examinations | Examination officers explicitly release managed schedules independently of marks. Results require native completion and managed publication; only entered own marks and configured grades appear. |
| Fees | All own posted college invoices across academic periods; programme/year, fee heads, invoice discounts/concessions, net assessment, settled amount, due date and residual. Payments use existing receipt identifiers and reversals. PDF downloads render the existing official server report. |
| Notices | Active, published, nonexpired college/student notices, including programme/section/group targeting. Per-student read/unread state is durable and drives the badge. Published notice attachments use the same scope. |
| Requests | Configurable institution catalogue with shared read-only templates and college overrides. Durable server-generated reference, retry key, serialized open-request deduplication, size/type-checked evidence, public event history and staff response. Information requests accept a student reply. Only ready/completed official documents can be downloaded. |
| Staff operations | Owner communication navigation includes Student requests/support; settings includes Student request catalogue. Registrar/services/manager operators review cases. Rejection/information/completion require a public response. Original submission identity/evidence cannot be rewritten or deleted. Existing nonportal staff requests retain their original workflow. |
| Help/account | Identified institutional feedback with duplicate-period protection; existing request centre handles support. Native account security/password/logout routes are reused. In-app notice badge preference persists on the linked student. |

## Permissions and trust boundaries

- Every service entry derives exactly one active linked student from the authenticated portal user and allowed companies. Supplied student IDs never confer access. Internal users, unlinked/inactive/ambiguous links and disabled-college portals receive an actionable access state.
- Students receive no new direct ORM access to official academic/finance models. The service performs narrow `sudo` searches with its own student/company/publication domains and returns explicit scalar projections. Private faculty notes, admission notes, administrative audit data, private request resolution and other students' records are excluded.
- Mutations use native authenticated POST + CSRF. Download handlers recheck identity and record scope on every request. Receipt rendering has no arbitrary report/model selector. Responses use private `no-store` headers; protected content is hidden on page exit and revalidated on restored browser history.
- Contact writes have a server field whitelist and college switch. Request type, original requester/student/company, evidence reference, idempotency key and history are fixed after submission. Public history is append-only. Catalogue global templates are protected by a write rule; duplicate one into the active college to override its code, and deactivate that override to disable the type locally.
- The request workflow locks its original record; submission and notice mutations serialize on the linked student. A repeated network submission returns the original request reference. Requests that entered review cannot be cancelled by the student.
- Uploads allow PDF/PNG/JPEG or UTF-8 text, verify extension/content signature, cap the configured size at 1–10 MB and normalize filenames. This repository has no antivirus service; do not describe this validation as malware scanning.

## Files and upgrade

All application changes live in the existing `addons/ideastone_erp` addon; the pinned upstream vendor tree is unchanged.

- `models/student_portal.py`: college switches, student preferences, request catalogue/events, conditional existing request workflow and exam schedule release.
- `models/student_service.py`: authenticated identity, bounded scoped projections, narrow mutations and document authorization.
- `controllers/student_portal.py`: existing portal integration, QWeb GET pages, CSRF POST actions and private downloads.
- `security/student_portal.xml`, `data/student_portal.xml`: staff ACLs/company rules, request sequence and six configurable templates.
- `views/student_portal.xml`, `static/src/js/student_portal.js`, `static/src/scss/student_portal.scss`: same-app QWeb shell, progressive navigation, retry/loading/error states, responsive drawer and faculty/Owner design palette.
- `views/student_operations.xml`, `models/mvp_dashboard.py`: existing staff shell navigation and native staff forms.
- `tests/test_student_portal.py`: identity, direct-model denial, profile policy, attendance consistency, result privacy, ledger/receipt scope, notices, request lifecycle/retries/files, catalogue override and timezone boundary tests. Shared Owner test setup is reused without rerunning duplicate inherited tests.
- `docs/qa/student-portal/{seed.py,browser.cjs}`, `.github/workflows/ci.yml`: real disposable Odoo browser workflows and screenshot evidence.

Upgrade `ideastone_erp` with the same Odoo 17/OpenEduCat addons path used by the existing deployment. The manifest advances to `17.0.1.0.4`. Schema additions are additive; existing ledger/attendance/result rows are reused. Global catalogue seeds are `noupdate`; existing company catalogue edits survive upgrades. Managed exams remain unreleased until an authorized examination officer uses **Release schedule to students**. Existing native completed/public schedules remain available according to their native state.

Before enabling a college, verify each student account is a portal user linked to exactly one active `op.student`, with the correct permitted company. College configuration controls portal access and contact editing. Do not grant student users internal, faculty, registrar or accounting roles.

## Reproducible QA and preview data

The CI workflow installs all existing modules on disposable Odoo 17/PostgreSQL 16, runs the existing and Student backend tests, then the real faculty, Owner and Student Playwright suites, followed by an installed-database upgrade. The Student fixture extends the Owner demonstration college after its workflow checks. It creates two synthetic portal users, posted receipts, released/published exam examples, approved learning material, admission evidence and targeted notices. The interface labels this data **DEMONSTRATION COLLEGE · SAMPLE DATA**.

Passwords are generated per CI run through environment variables and are not committed. The fixture asserts that the database is named `ci`; it is not a production seed or a migration. The workflow removes its disposable container and named volume on completion. Reset by rerunning CI against a fresh disposable database, not by deleting operational college records.

The browser suite checks every visible destination, saved profile reload, direct-model/official-field denial, durable notice acknowledgement, concurrent request retry, staff information/reply/approval/issued document, actual receipt PDF bytes, another student's download and request denial, CSRF rejection, failed-navigation recovery, 1440/768/390 px layouts, keyboard drawer dismissal and logout/back reauthentication. Artifacts include actual screenshots, an official receipt PDF and machine-readable verification; no static UI mockup substitutes for these checks.

## Explicit integration limits

- No approved online gateway credentials or callback workflow were supplied. There is no online settlement button or simulated “paid” state. Existing native posted collections and receipts are functional; the accounts office remains the payment path.
- No official hall-ticket/result-export or SGPA/CGPA scheme is configured. Those actions/totals are not invented. Grades come from the existing examination grading configuration.
- Attendance corrections remain staff-controlled; a request is evidence for review, not permission to change a submitted register.
- Library circulation is read-only. Reservations/renewal are not exposed without a supported student workflow. The catalogue currently lists up to 200 scoped titles with a local filter; staff retain the circulation desk.
- Assignments, hostel, transport, placement and wallet are optional later-phase portal modules. They remain hidden rather than presenting empty navigation or fake balances.
- Local Docker Desktop cannot start on this Windows host. Runtime and browser verification therefore run on the disposable Linux CI host; local checks cover Ruff, JavaScript syntax, XML and diff validation.
