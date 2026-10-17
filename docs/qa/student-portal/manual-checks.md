# Student Portal manual acceptance checklist

Use a staging or disposable college with two independently linked student portal accounts, a registrar/services operator and an examination officer. Use synthetic student data. These are reproducible acceptance steps, not a claim that every row was manually executed. Actual automated results and screenshots are recorded separately in `evidence/verification.json` after CI.

## Access and identity

| ID | Steps | Expected result |
| --- | --- | --- |
| A01 | Open `/my/campus/student/dashboard` while signed out. Log in with a student account. | Native login is required; successful student login lands on the student workspace. |
| A02 | Sign in as student A; open profile, attendance, fees, results and requests. | Every personal row belongs to A. No owner configuration, other students' names or private faculty notes appear. |
| A03 | Copy student B's enrolment query value into A's URL. | Access is refused; B's placement/details are not rendered. |
| A04 | Change an authorized receipt/document/request download ID to B's ID. | HTTP 404 with no file data. The original authorized file remains downloadable. |
| A05 | Open the new student route with an internal staff login or a parent without a direct student link. | Student service access is refused. Existing staff/parent workspaces remain separate. |
| A06 | With an administrator, remove the student link, archive the student with a reason, or create an ambiguous second link; reload as that portal user. Restore the fixture afterwards. | Clear contact-office access state; no fallback to a random student and no academic/financial data leak. |
| A07 | Disable the Student Portal for this college, then open it as the student. | Clear disabled-college message; no personal projection. Re-enabling restores valid access. |
| A08 | Sign out, press browser Back and revisit a saved student URL. | Protected records are revalidated; native login is shown. Cached personal data is not restored as an active workspace. |

## Dashboard, profile and academics

| ID | Steps | Expected result |
| --- | --- | --- |
| D01 | Compare each of the five dashboard cards with its linked detail page. | Class count, attendance denominator, residual fees, released future exams and unread notices reconcile with saved records. |
| D02 | Select a previous enrolment and date range; follow a dashboard drilldown. | Academic placement and class-record filters persist. Financial totals remain clearly labelled as all posted college invoices. |
| D03 | Open an account with no submitted attendance or posted invoice. | “Not recorded”/empty guidance is shown; an invented percentage or zero paid ledger is not displayed. |
| P01 | Try to edit name, student number, admission status, programme or guardian identity. | Official fields are read-only. The correction request path is available. |
| P02 | With contact editing disabled, inspect the contact panel and submit a forged profile field through a request. | No editable contact form; the server also rejects the write. |
| P03 | Enable contact editing for the college. Change phone/address, save and reload. | Allowed fields persist; invalid phone data is rejected with feedback. Official fields remain protected. |
| P04 | Download an admission document, then try the same URL as another student. | Own file downloads; the other student receives 404. |
| C01 | Open Academics, switch enrolment and inspect programme/year/section/subjects. | Values follow the authoritative enrolment. Credits/faculty show actual values or explicit missing-allocation text. |
| C02 | Publish an approved material for the student's section/subject; retain a draft and an unrelated material. | Only applicable approved materials appear/download. Draft and unrelated IDs are denied. |
| T01 | Open Timetable, use Today, This week and Selected period. | Rows filter by the student's local dates. Empty ranges have an explicit message. |
| T02 | Inspect a class around local midnight, a cancelled session and a changed room/time. | Local date bounds are correct. Cancellation and update timestamp are visible; cancelled classes do not inflate today's remaining count. |

## Attendance, examinations and fees

| ID | Steps | Expected result |
| --- | --- | --- |
| AT01 | Compare student subject totals against the submitted staff register. | Same attended/eligible denominator and configured threshold. Draft register lines do not appear. |
| AT02 | Include present, absent, late, excused and cancelled-session examples; change excused policy using authorized staff. | Late counts as present; excused follows the configured exclude/present/absent rule; cancellation is excluded. |
| AT03 | View two months of submitted attendance, then a single-month period. | Trend uses actual monthly records; it is not fabricated when fewer than two months exist. |
| AT04 | Try a direct attendance edit as a student. Submit a correction request instead. | Direct official edit is denied; request records evidence for staff review without changing attendance. |
| EX01 | Create a managed draft exam. Release its schedule through an examination officer. | Hidden before release, visible afterwards for the enrolled section/subject. An ordinary faculty/student cannot release it. |
| EX02 | Enter marks, submit, lock and publish using existing staff roles. | Draft/submitted/locked marks remain private; published own marks/grades become visible. B's marks stay private. |
| EX03 | Inspect the result page without a configured CGPA/hall-ticket export. | No unofficial CGPA or nonfunctional download action appears. |
| F01 | Post a student's assessed invoice with an approved concession; record partial and final payments. Reload after each step. | Posted invoice discounts/concessions, net assessment and native residual reconcile. Student cannot alter amounts. |
| F02 | Download a receipt and inspect the PDF. | Actual official receipt identifier, student, amount, fee invoice, date, method and institution appear; full PDF is readable. |
| F03 | Reverse a receipt through authorized accounts staff. | Native residual changes; payment history and official receipt show reversal. No client-side subtraction overrides the ledger. |
| F04 | Inspect an outstanding fee with no approved online gateway. | Accounts-office guidance is shown. There is no simulated payment or misleading success flow. |

## Notices, requests and account behavior

| ID | Steps | Expected result |
| --- | --- | --- |
| N01 | Publish notices for students, faculty, another section and an expired period. | Only active notices matching A's college/academic audience are shown as current. |
| N02 | Mark a notice read, reload, mark unread and reload. Disable/re-enable the badge preference. | Persistent unread state and badge reconcile; the preference affects presentation, not publication access. |
| R01 | Choose a request type and inspect requirements/fee guidance. Submit with a valid supporting file. | Server issues one reference; My Requests shows the saved submission and initial status. |
| R02 | Double-click submit, retry the same network submission, or create the same type while it remains open. | Original open request/reference is reused; no duplicate case or file association is created. |
| R03 | Upload a file over the configured limit or HTML renamed as PDF. | Server rejects it. A valid permitted file succeeds. No file content executes in the portal. |
| R04 | Staff asks for information with a public response; student replies; staff approves and attaches a final file; mark Ready. | State history, public responses and student reply persist. Final file is hidden before publication and downloadable after Ready/Completed. |
| R05 | Staff tries rejection/information/completion without a public response. | Workflow blocks the change with an actionable validation error. |
| R06 | Student cancels before review, then attempts cancellation after approval on another request. | First cancellation is allowed by type policy; the later one is denied. History remains. |
| R07 | Attempt to change original requester/student/type/evidence or delete a submitted portal case. | Server rejects identity/evidence rewriting and deletion. Private staff chatter/resolution does not appear in the student projection. |
| R08 | Duplicate a shared catalogue template into the college and change its guidance; then deactivate that override. | Student sees the college version once; deactivation hides that code locally. Global template is not modified. |
| L01 | With applicable library data, inspect loans, fines and catalogue; otherwise inspect navigation. | Only own loans and scoped holdings appear. Library hides when wholly unavailable. Unsupported renewal/reservation actions are absent. |
| H01 | Submit identified feedback for an academic period, then retry that period. | First submission persists; duplicate is rejected. Privacy statement explains staff visibility. |
| H02 | Open Account security and sign out. | Existing secure authentication/password workflow is used; no plaintext password or custom bypass is exposed. |

## Usability and recovery

| ID | Steps | Expected result |
| --- | --- | --- |
| U01 | Check dashboard, tables, fees and requests at 1440, 768 and 390 px. | No page-wide horizontal overflow or obscured primary controls. Wide tables scroll inside their own container. |
| U02 | Open mobile navigation by keyboard; Tab/Shift+Tab through it; press Escape. | Focus remains inside the open drawer and returns to the toggle when closed. |
| U03 | Interrupt the next navigation request while a saved ledger is displayed, then restore connectivity and Retry. | Existing records remain visible with an error banner. Retry loads the intended page; loading state does not remain stuck. |
| U04 | Submit a form with JavaScript disabled, then repeat with progressive enhancement enabled. | Native authenticated/CSRF form workflow remains usable. Enhanced navigation preserves filters and reports saved/error states. |
| U05 | Navigate every visible sidebar destination; inspect headings and browser console. | Consistent faculty/Owner palette and navigation, meaningful empty states, no broken destinations or uncaught JavaScript exceptions. |
