# VCET workspace implementation and acceptance

This change implements the blueprint's first integrated workspace and permissions milestone on Odoo 17. It uses inherited Odoo/OpenEduCat models, QWeb, Owl and SCSS; vendor and framework sources are unchanged. The supplied HTML files are visual references, not an authentication or storage implementation. Their sample people, metrics and localStorage logic are not used.

## Delivered

- Supplied navy/blue styling, exact embedded wordmark and campus photograph, responsive login, compact administrator/faculty overview, searchable categorized module directory and report workspace. The existing Odoo account/session controls remain available in a white navbar. The login role labels explain the audiences; they cannot select privileges.
- Administrator catalogue discovery is separate from permission to open an action. Unreadable installed models are labelled Permission required and disabled; underlying Odoo ACLs remain authoritative. KPIs use current records with current record rules. Faculty do not receive institution-wide KPI queries.
- Distinct College administrator and Responsibility approver groups. Neither implies Settings administrator, accounting or payroll. The older Campus manager group retains its existing broad powers; this PR does not rename it as a limited owner role. Only platform administrators should assign these governance groups.
- Collection- and college-scoped Library In-charge appointments: draft, request, independent approval, rejection, immediate revocation, immutable decision evidence, explicit start/end dates and a bound account identity. The effective grant is checked at every circulation RPC, including expiry, active account and faculty status. This is the first supported additional-role template. No group or password is changed when an appointment is approved.
- The faculty library desk lists permitted copies/cards and outstanding loans, persists canonical issue/return transactions, serializes copy and borrower capacity checks and delegates fines to the existing finance workflow. It cannot grant stock correction, invoice creation, payroll or user administration. A copy now has a college field; review its migration default before a multi-college upgrade.
- Attendance record rules restrict ordinary faculty to their own sheets/lines; marking requires the authoritative timetable allocation, matching batch and enrolled student. Attendance managers retain their existing role. Publishing/revising official results requires the existing Examination administrator group; marks must be within the examination maximum.
- Student and Parent workspaces use the existing linked account relationships, completed attendance, confirmed upcoming timetable and published exam results. Changing a student ID or a `campus_role` URL parameter grants no additional access. Normal portal sign-in lands on the campus page, and the standard account portal also links to it.
- Branded PDF and CSV attendance exports include academic year, semester, period, programme/batch, threshold, counts/totals, publication state, generating identity/time, export ID and snapshot hash. Only completed attendance is counted. Ordinary faculty exports additionally restrict to their own classes. Outputs and immutable audit snapshots can be read only by their creator in their permitted college. CSV formula-leading identifiers and names are escaped. A report export is a draft, never a publication action.

## MVP coverage against the eight requested areas

| Area | Running implementation used by this PR | Boundary |
| --- | --- | --- |
| Dashboard & analytics | Permission-aware administrator/faculty overview, live counts, role approval queue | No mock finance totals or invented trends |
| Administration & admissions | Existing admission, student/faculty directory, departments, programmes and batches | User provisioning remains platform administration; audited delegation is the new controlled path |
| Academic management | Existing subjects, allocations, timetable and class attendance; new attendance export | Faculty marking now requires a timetable session; existing legacy unscheduled records need an attendance manager to correct |
| Examination & results | Existing schedules, marks/results and review workflow; server publication and mark-bound guards | Uses the installed Examination administrator role; no unapproved exam/HOD delegation template |
| Finance & fees | Existing fee terms, invoices, posted accounting and student billing portal | Financial calculations/payment verification are not rewritten or claimed audited end to end by a UI check |
| HR & payroll | Existing restricted salary agreements, payslips, leave, staff attendance and staff profile | Sensitive identifiers remain behind HR field permissions; no globally visible staff-profile sample data |
| Mentorship & student support | Existing counseling, shared mentor remarks, service requests | Existing permissions and approval workflow retained |
| Communication & student portal | Existing targeted circulars plus Student/Parent workspaces and confirmed timetable | Only linked identities and published academic data are exposed |

## Discovery and remaining blueprint gates

`module-inventory.json` records the repository's custom and pinned OpenEduCat manifest versions/licenses. Local verification uses the Odoo 17 image and PostgreSQL 16 from compose. This is a source inventory, not certification of an external college deployment or license entitlement.

The whole multi-phase blueprint is **not** claimed complete by this PR. IMPRES contracts, authorized exports/API/database access, historical reconciliation and cutover are not available. No IMPRES connection or real college import is attempted. Keycloak MFA/SSO/logout and OpenOlat roster/grade-return integration require their separate running stack and institutional identity configuration. HOD, Exam Coordinator, Warden and other delegation templates require resource policies before adding rights. Module entitlement/activation controls and the other 14 blueprint report formats are not simulated in the UI. The existing payslip report remains available only to authorized users. No XLSX export is advertised.

The supplied screenshot-derived logo/photo are retained exactly as provided; replace with approved high-resolution originals for production. No claim of zero bugs or production readiness follows from local testing. The maintainer reviews and merges; no production deployment is part of this work.

## Validation

The PR description and `evidence/verification.json` record the final clean-install, upgrade, browser, output and static checks. Odoo tests run with `--test-tags=/ideastone_erp`; fixtures run in transactions and roll back. Existing payroll, capacity, import idempotency, record boundaries and portal tests remain part of the regression gate.

To upgrade a local database, stop the HTTP service, run Odoo with `-u ideastone_campus,ideastone_erp --stop-after-init`, then restart it. Do not run schema upgrade and the HTTP server concurrently. For a local ERP-only preview, bind Odoo to loopback and use `--db-filter=^campus$`.

PDF rendering needs `report.url` (or a correctly reachable `web.base.url`) to point to this deployment's own Odoo HTTP endpoint so wkhtmltopdf can load styles and the wordmark. The localhost preview uses the container's internal `http://127.0.0.1:8069`; this is a local database setting, not a production configuration change.


### Browser and visual evidence

The browser pass covered administrator navigation/search/empty state, the appointment ledger, PDF generation followed by further navigation, faculty copy/card search and persisted issue/return, authenticated Student/Parent sign-in, and document overflow at desktop/mobile widths. Screenshots contain synthetic/demo records only. A PDF exported by the running Odoo wizard was rendered and inspected; its numbers came from a completed synthetic attendance record.

The runtime geometry capture covered 390, 1440 and 1728px plus the mobile drawer open state. The review identified custom card-gap and touch-target fixes. Retained Odoo menu padding and clipped, locally scrollable tables are documented review exceptions in `BUG-REPORT.md`; the geometry heuristic is not advertised as a visual-approval score. Native Escape was retested after fixing Odoo's event-order conflict.

Local preview: `http://localhost:8070/web/login`. Its loopback-only proxy forwards both HTTP and Odoo websocket traffic. The ERP-only preview disables the unreachable SSO provider in the local `campus` database; no repository SSO configuration or credential was changed. The full SSO/LMS stack is a separate acceptance gate.
