# Parent Portal MVP

The Parent Portal extends the installed `ideastone_erp` application. It uses the same Odoo authentication, portal shell, college records, published academic data and staff request queue as the Faculty, Owner and Student workspaces. There is no separate application or parallel attendance, fee or assignment ledger.

## Entry and navigation

An authenticated guardian opens `/my/campus`. Parent accounts enter `/my/campus/parent/dashboard`; student accounts retain their existing workspace. The default navigation is Overview, My Child, Attendance, Learning & Homework, Timetable & Calendar, Exams & Results, Fees & Payments, School Updates, Requests & Contact, Documents, and Account & Help.

Every page and chart follows the selected child. The header displays a child selector only for guardians with multiple active linked children. Academic placement and date filters remain in the URL, so refresh and browser history retain the context. Switching children starts with that child's academic placement rather than carrying another child's enrolment ID.

The parent workspace reuses Student QWeb components and progressive navigation, with scoped purple accents and responsive navigation. Other role palettes and navigation remain unchanged.

## Provisioning and access

1. Upgrade `ideastone_erp` after installing the prerequisite Owner and Student changes.
2. Create or select an external Odoo user with **Portal** access. Do not give parent users Internal User or staff groups.
3. On the existing OpenEduCat parent record, link the user and the permitted students using `op.parent.user_id` and `student_ids`. The guardian and student records must be active.
4. Assign only the relevant colleges to the parent user. The selected student's company must be one of the user's allowed companies.
5. The college's **Enable Parent Portal** policy defaults to enabled. Disable it to deny that college's parent access.

The native active guardian relationship is authoritative. Cached user `child_ids`, posted form values and URL IDs cannot grant access. Every projection, write and download revalidates the relationship. Removing a child, archiving the guardian/student, removing college access or disabling the policy takes effect on the next request. A missing or unauthorized child produces a private error; it never falls back to a different child.

Parents cannot edit official identity, enrolment, attendance, marks, invoices, payment state or student submissions. They cannot call the Student/Owner dashboard services to bypass these restrictions. Views and downloads use `Cache-Control: no-store`; form mutations retain Odoo CSRF protection. Parent notice acknowledgements have no public model ACL.

## Data sources and publication rules

| Surface | Existing authoritative source and rule |
| --- | --- |
| Attendance | Submitted `op.attendance.sheet` / `op.attendance.line`; the same configured shortage and excused-session policy used by the Student workspace; cancelled classes excluded. |
| Timetable | Confirmed/cancelled `op.session` records for the child's placement and enrolled subjects; dates shown in the user's timezone. |
| Homework | Published/finished `op.assignment` records explicitly allocated to the child and selected batch/subject. Submission status comes from `op.assignment.sub.line`; parents cannot submit. |
| Results | Released exam schedules and officially published `op.result.line` values. Draft/unpublished marks never appear. |
| Fees | Posted child invoices, residual amounts, saved payment records and existing official receipt reports. All posted periods are included and labelled accordingly. |
| Notices | Active, published/approved parent or all-audience circulars, constrained by college, programme, section, group and publication dates. Pinned notices appear first. Read status is private to each parent and child. |
| Materials | Existing approved digital resources scoped to the child's subjects/batches. |
| Documents | Verified admission documents explicitly released by authorized admissions/registrar staff; existing official receipts and ready/completed responses to that parent's requests. |
| Transport | Only when the college enables it and an active approved allocation exists for the child's academic year, active route and boarding point. |

The Overview aggregates these same records, including subject/monthly attendance charts, pending work and nearest deadline, chronological classes/exams/deadlines, latest published marks, notices and fee balances. Missing data has explicit empty states. Production views do not contain fixed KPI values.

## Parent requests and staff review

The installation adds three parent-only request templates: absence/leave intimation, teacher meeting request, and school enquiry/profile correction. Existing student-only request types remain student-only. A college can create its own template with the same code to customize or disable a global default, and can choose Student, Parent or Both audiences.

The existing `campus.service.request` workflow handles submission, requests for additional information, parent replies, approval, completion, cancellation and ready-file downloads. History is scoped to both the authenticated requester and selected child. A second guardian does not receive another guardian's private correspondence.

Absence intimation requires a valid date range of at most one year and a reason. It records evidence for staff; it never changes attendance or automatically approves leave. Idempotent submission keys preserve the original request and dates when a request is retried. Meeting requests become confirmed only through the college response. Office staff can see the requester and recorded absence dates in their existing review form.

Admissions/registrar staff release or revoke verified documents using **Toggle parent release** on the existing document form. This action changes only the dedicated sharing flag after access, company, role, verification and lock checks, and records an audit event. It cannot alter a verified document's file or its approved admission.

## Supported boundaries

- Online payment initiation is unavailable until a trusted payment provider is configured. The portal shows real balances, recorded payment status and receipts; it does not simulate a successful payment.
- The current data model does not provide an approved holiday/event feed, separate released teacher comments, automated hall tickets, or an official report-card generator. These are not replaced with invented records. Authorized verified letters/report cards may be released through Documents.
- Transport displays recorded pickup time, boarding point and contact. It does not claim live GPS or a drop time that is not stored.
- Account security uses the existing Odoo account page. The saved notification preference controls the in-app badge only; it does not promise SMS, email, WhatsApp or push delivery.
- The portal inherits bounded record retrieval from the Student service. Very large institutional histories may require server-side pagination in a later change.

## Verification

Backend tests cover linked-child selection, revoked/archived/company access, official-record immutability, fee isolation, receipt authorization, publication rules, private notice read state, staff request lifecycle, absence evidence and document release. The browser scenario exercises real saved records and server routes rather than route mocks.

`docs/qa/parent-portal/seed.py` only runs on the disposable `ci` database, after the Owner and Student seeds. Its synthetic college is explicitly labelled as demonstration data. `browser.cjs` uses an environment-provided temporary password and produces desktop/mobile screenshots and `verification.json`; credentials are not committed.

CI retains the existing install, Faculty, Owner, Student and upgrade checks, then adds the Parent scenario and evidence artifact. See the manual checklist for acceptance cases and local verification results.
