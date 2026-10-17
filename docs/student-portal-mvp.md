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
