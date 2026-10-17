# IMPRES review and ZcERP MVP delivery report

Research date: 17 October 2026 (Asia/Kolkata). Scope: the public IMPRES site, the existing campus codebase, and the college feedback supplied in this chat. This is a product/workflow assessment, not an audit of the competitor's private application or the college's licensed installation.

## Decision

Demonstrate a focused, reliable finance and learning MVP in the accepted ZcERP interface. Give the college evidence that daily work is clearer and safer, then validate that improvement against its actual installation. A longer menu is not, by itself, a reason to migrate.

The only customer complaint reported here is the existing UI. No specific financial loss, missing LMS capability, security failure, performance defect or support failure has been reported. Those must not be invented for the presentation.

## Public evidence and its limits

| Area | What the vendor publicly describes | What remains unverified |
| --- | --- | --- |
| Finance | Demand, concessions, collections, balances, receipt control, accounting reports and optional online payments. [Finance & Billing](https://impreserp.co.in/modules/finance.php) | Installed configuration, reconciliation accuracy, duplicate-transaction behaviour and recovery under simultaneous submissions. |
| Academics | Attendance, lesson planning, marks, timetables and student/parent progress visibility. [Academic Management](https://impreserp.co.in/modules/academics.php) | The college's actual task flow, coursework submission/revision experience and publication controls. |
| Product packaging | Basic, Premium and Elite editions, with different capability bundles. [ERP editions](https://impreserp.co.in/impres-erp.php) | The college's edition, enabled integrations, contract price and implementation/support terms. |
| Examinations | A broad examination lifecycle, including certification and revaluation. [IMPRES CoE](https://www.impreserp.co.in/impres-coe.php) | Actual deployment scope, configuration and the institution's regulatory rules. |

Public pages describe capabilities; they do not establish how well the installed product performs. A feature not explained on those pages is **not proven absent**. Marketing screenshots and counters are not a usability benchmark. The website's brochure could not be retrieved through this research tool, so no brochure-only assertion is included.

## SWOT assessment

**Strengths:** The incumbent advertises broad institutional coverage and connected workflows. Its existing installation also has familiarity, historical data and established operating procedures. Replacing those has real training and migration costs.

**Weaknesses supported by current evidence:** The college has expressed a UI concern and interest in a replacement. We have not yet measured which tasks are confusing or slow. Edition-dependent scope creates a configuration question to investigate, rather than proof of missing functionality. No other product weakness has been demonstrated.

**Opportunities for our MVP:** Prove a consistent role-specific workflow; prevent repeated collection of an entered transaction; make overdue follow-up obvious; connect student work, faculty review and parent feedback; show failed LMS enrolment honestly and provide a retry path. These are implementation and demonstration opportunities, not claims that IMPRES cannot do them.

**Threats:** The incumbent's breadth may exceed our MVP in areas such as CoE and payroll. Poor migration, unconfigured integrations, unproven accounting controls or weak training could outweigh a better-looking interface. A reliable core and a controlled pilot matter more than an unfinished full-suite promise.

## What this delivery strengthens

### Finance and fees

- Non-cash collections require a real transaction reference distinct from the invoice memo, including the native payment-register form.
- A normalized reference is qualified by college and journal and protected with a database uniqueness constraint. Changing payment method or opening a new collection form does not permit the same reference again.
- Native reconciliation remains the balance authority. A rejected duplicate rolls back its payment; partial collections, cash receipts and reasoned reversals retain their existing accounting workflow.
- Reversed receipts retain their original reference evidence. A reversal does not authorize reusing the same external transaction as a fresh collection.
- An Overdue follow-up submodule and invoice filters use posted unpaid invoices, due dates, programme and academic year. They reuse the existing fee records and shell.

This protects manual entry of supplied transaction identifiers. It does not verify that money arrived at the bank or that an identifier supplied by a cashier is genuine. Live provider verification and bank reconciliation remain separate integrations.

### Learning and coursework

- Reuse the native assignment and submission models. Faculty publish work for allocated students in their own teaching section; students see it inside Academics, with a dedicated submodule link.
- Students submit an explanation and a validated supporting file. Repeating a saved submission does not overwrite its evidence or create another student identity.
- Assigned faculty review, return work for revision, reject with a reason, or release a grade and feedback. A zero is explicitly confirmed and remains distinct from a missing grade.
- Students and linked parents see feedback only after release. Parents cannot submit as students. Unlinked users and raw portal model writes are denied.
- Published coursework, submitted evidence and released feedback are protected from silent edits/deletion. Reopening released work requires a reason and records an audit event.
- Staff get assignment review and LMS account/retry submodules within the existing navigation and palette.

### LMS integration

- A failed course enrolment preserves account identity but no longer produces an all-success timestamp. The error remains visible for retry.
- Nightly provisioning includes failures and newly required course enrolments, rather than skipping every student who already has an identity key.
- Only authorized administrators can provision accounts within their permitted colleges. The learning frame obtains its public URL through a narrow staff service instead of requesting privileged configuration access from faculty.
- The external frame reports configuration errors with a retry action. It does not substitute a static mock for OpenOlat.

## How to present a reason to switch

Use the same students and tasks on both products. Record the starting state, elapsed task time, number of screens, correction steps, data outcome and role visibility. Do not announce a speed or usability improvement before measuring it.

1. **Collect and recover:** Assess a fee, record a partial payment, open the receipt, and show the remaining balance. Submit the same external reference from two new forms simultaneously: exactly one collection should survive. Reverse a mistaken collection with a reason and show restored dues and retained history.
2. **Find the next finance action:** Open Overdue follow-up, filter by programme/year, and open the underlying unpaid invoice. Reconcile displayed totals to saved accounting entries.
3. **Teach and review:** Publish one assigned task, submit as the student, review as the allocated faculty member, and release an explicit zero with feedback. Show the same released outcome to the student and linked parent.
4. **Protect the boundary:** Try an unlinked child, another faculty member's assignment, a parent submission and an unpublished grade. Demonstrate denial on the server.
5. **Recover an integration:** Use an isolated integration test to simulate one failed course enrolment, show that it stays pending, then retry. A live OpenOlat demonstration needs its configured service and SSO.

Suggested pilot acceptance gates: exact agreement between demonstrated ledger totals and accounting records; one receipt per entered transaction; no cross-role data leakage in the tested cases; no hidden/unreachable primary actions at the tested widths; and successful completion of the student-to-faculty-to-parent workflow. Task-time improvement is a pilot target, not a result established by this report.

## Future modules and submodules to evaluate

| Priority | Proposed capability | Why it could help | Evidence needed before claiming an advantage |
| --- | --- | --- | --- |
| P1 | Bank reconciliation and collection exceptions desk | Match actual statement/provider records to receipts and surface unmatched, reversed or disputed items. Reuse native accounting first. | Statement samples, supported bank formats, permissions and a verified matching/review procedure. |
| P1 | Migration validation and opening-balance sign-off | Give the college confidence that student counts, invoice totals, outstanding balances and receipt history survived migration. | Approved export samples, mapping rules, reconciliation totals and written sign-off. |
| P1 | Verified online-payment lifecycle | Signed provider events, retry handling and posted receipts without trusting a browser success redirect. | Provider contract, credentials in secure settings, signed callback tests and reconciliation evidence. |
| P1 | Faculty follow-up / student support queue | Bring unsubmitted work, repeated revision and attendance shortage into a useful staff task list. | Faculty priorities, intervention policy and permission boundaries. |
| P2 | LMS offboarding and membership reconciliation | Review and remove remote course access after withdrawal or transfer, with evidence. | Verified OpenOlat API behaviour, retention rules and end-to-end revocation tests. |
| P2 | Course-outcome and intervention reports | Use released assessment evidence to support academic review without fabricated AI scores. | College assessment weights, approved outcome mappings and representative historical records. |

These are proposed next steps, not delivered modules and not verified shortcomings of the incumbent. Confirm which are already covered by the college's installed product before funding them.

## Operating limits and deployment checks

- Existing historical receipts retain their evidence. The new transaction key is assigned to new collections; historical reference cleanup/backfill needs a controlled migration review, not automatic deletion or renumbering.
- References are normalized for case and repeated whitespace within a college/journal. Distinct identifiers or different journals require separate reconciliation; this does not detect every possible human misdescription.
- The coursework portal uses the existing academic placement and explicit allocation. Advanced SCORM, online exams, video and SSO remain OpenOlat capabilities requiring the configured external stack.
- Automated remote membership removal is not implemented; administrators must revoke OpenOlat access during offboarding until that integration is verified.
- The shared sidebar, topbar and accepted role palettes are retained. This delivery adds functional navigation and native controls rather than redesigning the whole application.
- Local validation uses synthetic records in a separate database. No production deployment, real payment-provider connection or live OpenOlat enrolment was performed.

## Actual verification

- Native Odoo 17 with PostgreSQL 16, isolated synthetic database: **78 backend tests passed, 0 failures, 0 errors**. This includes the existing Faculty, Owner, Student and Parent suite and eight new finance/learning tests.
- Real Chrome browser: simultaneous payment attempts produced one receipt; invoice residual totals decreased by exactly one payment. Student file submission, native faculty review of an explicit zero, released student/parent feedback, all three learning submodule views and 1440px/390px layout checks passed without browser JavaScript errors.
- Ruff across `addons/` and `scripts/`, addon XML parsing, browser script syntax and Git whitespace checks passed. The installed-module upgrade also completed successfully.
- These are local results. GitHub CI independently runs installation, the existing role scenarios, the new finance/coursework scenario and a module upgrade. Its live result is on the PR.
- Live OpenOlat/SSO, bank settlement, a payment gateway and an actual competitor installation were not available in this validation.

Screenshots and machine-readable browser results are in [the evidence directory](qa/finance-learning/evidence/). The source fixtures and checks are under `docs/qa/finance-learning/`; the backend cases are in `addons/ideastone_erp/tests/test_finance_learning.py`.
