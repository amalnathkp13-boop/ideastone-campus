# Finance and learning MVP hardening

This change strengthens daily-use finance and coursework workflows inside the existing ERP. It retains the shared Faculty/Owner shell, Student/Parent portal styles, native accounting ledger, OpenEduCat assignment tables and OpenOlat integration.

## Operator workflow

**Accounts:** Fees & Payments now includes Overdue follow-up. Its default search selects posted unpaid college invoices whose due date has passed. Accounts staff can group by programme/year/due month and open the original invoice. Non-cash collection forms, including native Register Payment, ask for the actual transaction reference separately from the invoice memo. Reusing it within the same college/journal is rejected even from another payment form or a different method. Cash partial payments remain separate receipts. Reverse a mistake through the existing reasoned reversal action; the original reference and receipt remain retained.

**Owner/Registrar:** Learning & LMS exposes Assignments, Review submissions and LMS accounts & retries. Assign a subject/section/faculty and allocated students, choose maximum marks (zero for ungraded work), deadline and initial late-submission policy, then publish. The create context enables reviewed campus coursework. Published instructions and allocation are fixed once submissions exist.

**Faculty:** My task list includes Review submissions. Faculty may manage their own allocated coursework; reviewed coursework requires a timetable teaching allocation for that section/subject. Read the student's explanation/file, enter a grade and feedback, then release it. If the grade is zero, explicitly check Grade confirmed so zero is distinguishable from an unentered mark. Return submitted work for revision with instructions. To reopen an accepted result, enter a reason before Return for revision. A faculty-authorized revision may be resubmitted after the original deadline. Submitted evidence and released feedback cannot be silently overwritten.

**Student:** Academics > Assignments & feedback shows allocated published work for the selected placement. Submit an explanation and optional PDF/PNG/JPEG/text file (5 MB maximum). A repeated saved submission returns the existing record. Submitted evidence can be downloaded; historical files remain limited to the same student. A revision request reopens the student's form. Grades and comments appear only after faculty release.

**Parent:** Learning & Homework shows status and released faculty feedback/grade for the selected linked child. Parent accounts cannot submit coursework or impersonate the student.

## Controls and implementation

- `account.payment.campus_transaction_key` stores a normalized transaction reference qualified by company/journal. A unique database constraint provides the final concurrent duplicate barrier. The key is protected from ordinary create/write calls.
- Native college payment posting locks the invoice and touches a dedicated journal revision before sequence generation. Odoo retries a stale concurrent request under its existing transaction retry mechanism. This also protects the first payment entry in a new journal, where there is no prior sequence row to lock.
- Collections continue to use native `account.payment.register` and receivable reconciliation; there is no second balance ledger. The deduplication check occurs before posting and is checked again when issuing the receipt.
- Assignment identity, college, teaching allocation and submitted-student allocation are validated on the server. Global record rules limit staff to their college/assignment and deny raw portal access to assignment/grade/submission models. Curated portal projections and writes revalidate the authenticated student or active guardian link.
- Coursework uses native `op.assignment`, delegated `grading.assignment`, and `op.assignment.sub.line`. A protected submission-slot key and the existing per-student transaction serialization prevent replayed portal submissions from creating another slot. Grade release and revision decisions are audited.
- File uploads reuse the existing server-side validated upload helper. Downloads use the existing authenticated private/no-store portal response handling.
- LMS account provisioning requires administrator authority and permitted colleges. Failed participant enrolments retain the account identity and an error rather than an all-success timestamp. Current-course changes and errors are included in the nightly retry queue. Successful course keys track actual successful enrolment calls.
- `ideastone.lms.workspace.configuration` returns only the public URL to internal staff; faculty no longer need privileged access to all configuration parameters. The frame has a visible configuration error/retry path.

## Migration and boundaries

Upgrade both `ideastone_lms` (17.0.1.0.1) and `ideastone_erp` (17.0.1.0.6) through the existing update process. Fields, constraints, views and access rules are additive; vendor source and existing receipt numbers are retained.

Historical receipts are not silently re-keyed, deleted or renumbered. Review old references before any backfill, especially duplicates or invoice memos used as references. New deduplication protects a supplied transaction identifier, not confirmation of bank settlement. Live gateways, statement reconciliation and migration sign-off still require their own configuration and evidence.

OpenOlat account/course calls are exercised with a deterministic test client for failure/retry cases. No live OpenOlat, SSO or payment-provider connection is claimed in local evidence. Membership removal/offboarding is not automated; administrators must revoke remote access until the removal API/retention workflow is verified.

## Verification

The full ERP suite covers existing Faculty, Owner, Student and Parent behaviour plus finance/learning cases. New backend checks exercise duplicate references across new forms and method changes, native bank references, cash partial receipts, reversal retention, publication/submission/revision/explicit-zero feedback, raw-RPC boundaries, late policy, parent read-only access, partial LMS enrolment/retry and public URL authorization.

`docs/qa/finance-learning/seed.py` requires the disposable `ci` database and adds a labelled sample-college scenario after the existing fixtures. `browser.cjs` performs concurrent collection attempts against two invoices, actual file submission, native faculty review, student/parent release visibility and responsive checks. It checks saved accounting values and a single receipt rather than accepting a success banner alone. CI preserves its screenshots and verification JSON and still runs all existing role scenarios and the installed-module upgrade.

## Manual acceptance cases

1. As an accountant, open Overdue follow-up and verify every row is a posted, unpaid, overdue invoice in the active college. Test programme/year grouping.
2. Collect part of an invoice in cash. Confirm an official receipt and reduced residual, then collect another cash part and confirm a distinct receipt.
3. Try a non-cash collection without a transaction reference in both the college and native forms. An invoice memo alone must not qualify.
4. Collect a bank/UPI reference, then try the same reference with changed case/whitespace from a new form, different method and different invoice. The same journal/college must reject it without another payment.
5. Submit the same reference concurrently on two invoices using a fresh journal. Exactly one collection and one receipt must remain; no entry-number clash should escape to the user.
6. Reverse a receipt with a reason. Confirm restored dues, retained receipt/reference and rejection of that old reference as a fresh collection.
7. Check foreign-college journal, overpayment, zero/negative amount and unauthorized-role denials.
8. Publish a task allocated to one student. Another student, unlinked parent and unassigned faculty must not read/change it through IDs or raw RPC.
9. Submit text and a permitted file, then retry. The original submission evidence must remain one saved record. Reject invalid/oversized evidence.
10. Verify initial late submission is rejected unless explicitly enabled. Return submitted work for revision and confirm a faculty-authorized revision can be submitted.
11. Enter draft feedback/marks and confirm they stay hidden from student/parent. Release an explicit zero and verify it appears as a grade rather than missing data.
12. Try changing accepted marks/feedback or deleting submitted evidence through RPC. Require the reasoned revision workflow and retain the audit.
13. Simulate one failed remote enrolment. Identity remains visible, the error stays pending, and retry success updates the timestamp. Change the current course mapping and confirm a new sync is queued.
14. Open the learning frame as ordinary faculty. Only the public URL should be exposed; invalid configuration gives a retriable message. Verify live OpenOlat/SSO separately before presenting it as connected.
15. Check desktop and 390px layouts, keyboard access, returned validation messages, file downloads, logout, and that all role palettes/navigation remain consistent.

