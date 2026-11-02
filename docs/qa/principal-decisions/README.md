# Principal Decisions reference

Branch: `codex/principal-decisions-reference`.

The Principal overview and Decisions content use the supplied
`Principal_Decisions_Final_Nav_Order.html` layout. The existing ERP sidebar is
retained. Decisions has exactly these tabs, in order:

1. Pending decisions
2. Staff leave approvals
3. Student leave approvals
4. Event management

The font stack is `Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial, sans-serif`,
as specified by the reference (which does not embed or download a font).
Desktop page titles are 29px / 760, panel titles 15px / 760, ordinary buttons
12px / 700, table cells 11px, and staff-register cells 10px. The canvas is
`#f3f6fb`, primary blue `#1769e8`, title ink `#102f4d`, and body ink `#173653`.
Styles are scoped inside the existing theme layer to Principal content, including
modals. Text, rows, filters, counters, dates and amounts come from saved records.

Staff leave is read from assigned `hr.leave` records. For two-stage leave,
HoD approval must reach `validate1` before the Principal can decide. A guarded
service verifies the college, assigned Principal, final stage, non-self approval,
outcome and remark, then runs Odoo's native validation/refusal. Native allocation
balances and resource calendar leave entries remain the source of truth. HR
officers can set the assigned Principal, recommendation and staffing coverage
on the standard leave form. Administrators may configure a college default
Principal reviewer on the company form.

Student leave uses the existing advisor → HoD → assigned Principal routing.
The student form includes leave category and supporting/continuity details.
Only records at the final Principal stage appear as pending.

Event proposals follow organizer draft → coordinator review → Principal review.
The Principal may return for changes, reject, or approve with a remark. Approval
requires recorded venue, budget and safety checks and creates one linked campus
calendar event. Returning creates no calendar event; resubmission repeats the
coordinator stage. Proposal forms and transitions enforce participant permissions.

Every workspace decision stores immutable source, outcome, actor, timestamp and
remark evidence. Concurrent decisions lock the source row; repeated or stale
submissions fail. General request forms also require a remark and preserve final
decision evidence. Staff/student/event data is scoped to the active college and
assigned Principal; source attachments use Odoo's normal access checks.

## Disposable preview

`seed.py` refuses to run outside a `principal_*` database. It reads
`PRINCIPAL_PREVIEW_PASSWORD` from the environment and creates synthetic records
with stable external IDs. Re-running preserves existing decisions. It supplies
six staff leave requests, five student leave requests, five general requests and
five event proposals. No preview password is stored in this repository.

The current preview runs in Docker container `principal-design-preview`, using
database `principal_publish_qa`, on `http://127.0.0.1:8075/web/login`.
Login: `principal@campus.local`. The main ERP on port 80 uses its existing data.

Run backend tests with Odoo 17 against the disposable database:

```sh
odoo -d principal_publish_qa -u ideastone_principal --test-enable \
  --test-tags=/ideastone_principal --stop-after-init --workers=0 --max-cron-threads=0
```

Backend tests cover native staff approval/calendar effects, required remarks,
reviewer and college isolation, immutable evidence, duplicate decisions,
event return/resubmission/signature, student review routing and exact tab order.
The prior Principal tests also check that Owner/Accountant navigation is retained.

Browser checks cover server refresh after decisions, filtered search and CSV,
supporting-file downloads, details/balance dialogs, quick links and device widths.
Final validation on 2 November 2026:

- Odoo module upgrade and all 12 backend tests passed, with zero failures/errors.
- Ruff and `git diff --check` passed; Python/XML, JavaScript and SCSS validation passed.
- Shared login, all four Decisions tabs, request dialogs, required remarks,
  refresh after saving, search/status filters, filtered CSV and supporting-file
  downloads were checked in the browser. Related staff, attendance, calendar,
  admissions, students and examinations destinations opened successfully.
- Sample staff, student, event and general-request decisions were saved through
  the browser. Event approval published its linked calendar entry; incomplete
  planning checks blocked approval and returning for changes preserved its route.
- A fresh long-title event proposal was created through the native ERP form,
  submitted and forwarded through its coordinator stage. The saved record updated
  the Principal register, queue, calendar and totals without changing the layout.
- Desktop (1440px), tablet (768px), phone (390px) and small phone (320px) were
  checked. The page fits the viewport; wide registers scroll inside their panels.

Screenshots are in `proof/`. The preview uses synthetic data in its own database;
the existing ERP database was not upgraded or reseeded. No PR was created.
