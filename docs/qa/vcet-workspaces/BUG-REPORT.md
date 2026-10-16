# VCET workspace findings and fixes

Scope: the supplied VCET blueprint's first integrated workspace milestone, based on `main` at `5fb695b`. All write testing used local synthetic records. No college production system or IMPRES records were accessed.

## Existing behavior corrected

| Finding | Root cause and affected files | Resolution and evidence |
| --- | --- | --- |
| Student/Parent login opened the generic account page without a campus entry | OpenEduCat overrides the normal login destination after authentication; `controllers/portal.py`, `views/portal.xml` | Keep the original authentication call, route authenticated portal users to `/my/campus` when no explicit redirect was supplied, and add a My campus card to `/my`. HTTP login regression and real Student/Parent logins pass. |
| Portal attendance counted unfinished sheets | The attendance domain did not require a completed sheet; `controllers/portal.py` | Count completed records only. The UI says which periods are counted; exports use the same completed-record convention. |
| Faculty attendance access and result publication lacked the requested server boundary | Broad upstream module roles were not equivalent to an approved resource allocation; `models/academic_security.py`, `security/workspace.xml` | Ordinary faculty see their own attendance sheets and must mark a timetable allocation with an enrolled student. Official result release/revision requires the Examination administrator role. API tests reject foreign attendance, ordinary-faculty publication and marks above the configured maximum. Attendance managers retain their existing authority. |
| The full operational directory crowded the navigation and did not provide distinct role overviews | Navigation and overview repeated a large shared catalogue; dashboard Python/Owl/SCSS | Compact persistent navigation plus a searchable categorized directory. Administrators discover installed actions, with unavailable actions disabled. Faculty summaries use their own permissions. Browser checks cover search, empty state, governance ledger and narrow/wide layout. |

## Defects found and fixed while validating this implementation

These were caught before presenting the PR as ready; they are not claims about deployed production defects.

| Finding | Root cause | Fix and check |
| --- | --- | --- |
| Custom PDF unexpectedly opened Odoo's document-layout setup | `report_action()` defaulted to the external company layout configuration although the custom report uses `web.basic_layout` | Use `config=False`; actual wizard downloads a branded A4 PDF, and the UI remains usable afterward. The rendered output was inspected. |
| Escape did not close the mobile sidebar | Odoo consumed the key before the window's bubbling listener | Use Owl's capture listener only while the drawer is open. Actual key test confirms `aria-expanded` returns to `false` and navigation closes. |
| A book search could remove the borrower from the dropdown | One query filtered both copy and card lists | Independent copy/title/barcode and card-number searches. Regression test and browser search → issue → return pass with both search fields populated. |
| Editing a draft nominee left its bound account stale | Draft writes changed the faculty without rebinding the account evidence | Rebind only in an editable draft. Submitted appointments remain immutable; the approval regression checks both draft changes and forged/submitted writes. |
| A reassigned faculty account could still appear effective in the overview | Display computation did not compare the current faculty account with the approved bound account | Match both identities in the effective indicator; circulation separately rechecks the bound account on every call. |
| Small-screen content became cramped beside the desktop sidebar | The desktop sidebar remained beside Odoo's toolbar until a narrow breakpoint | Drawer mode starts at 1023px. Measured document width equals viewport width at 390, 1440 and 1728px; 768px was also checked. Wide tables scroll inside their responsive wrappers. |

## Important acceptance boundaries

- The new appointment workflow supports **Library In-charge only**, with college/collection scope, separate approval and explicit effective dates. Other role templates require their own resource policies.
- The existing broad Campus manager role is not relabelled as a restricted college owner. Governance groups do not imply Settings, payroll or accounting.
- Before a multi-college deployment, review the new copy-level college field's migration default against the actual library inventory. Ordinary faculty correcting old unscheduled attendance need an attendance manager.
- The PDF/CSV is an internal draft snapshot. It cannot publish results or alter attendance. Other blueprint report formats, institutional SSO/MFA/LMS acceptance and IMPRES migration remain separate gates.
- Automated geometry review flags the retained Odoo utility-menu spacing and table descendants outside the viewport. These are accepted framework/local-scroll behaviors, not document overflow: wrappers clip and scroll locally, and the document width is unchanged. Custom card gaps and primary touch targets were corrected. No visual perfection or zero-production-bug guarantee is inferred from a geometry score.

## Manual reproduction and acceptance

1. Install/upgrade both custom modules; use the existing Odoo administrator sign-in. Open Overview, All modules, Reports and Access control. Verify directory search and an unmatched-query empty state.
2. With two separately authorized governance accounts, nominate an internal faculty member, choose collections and effective dates, request approval, and approve with the second account. Self-approval and edits after submission must fail.
3. Sign in as that faculty member. Search for a specific copy/title and a specific borrower card separately, issue a copy and return it. Revoke or expire the appointment; subsequent circulation calls must fail.
4. Sign in as a linked student and parent. Both land on `/my/campus`; only linked students are selectable. An unrelated student ID must show no linked record. A `campus_role=Admin` parameter must grant no privileges.
5. Generate the attendance PDF and spreadsheet using period/year/semester filters. Confirm counts, internal-draft status, actor/time, report ID and checksum; close the wizard and navigate again.
6. Review at 390, 768, 1440 and 1728px. Open the mobile navigation and press Escape. Use a table's own horizontal scroll when necessary; the document must not scroll sideways.

Test results and cleanup are recorded in [verification.json](evidence/verification.json). Synthetic preview screenshots are in [evidence](evidence/).
