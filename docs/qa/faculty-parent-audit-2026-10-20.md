# Faculty and parent workflow audit — 20 October 2026

This repair builds on student PR #34 (`a8af702`). Writes and negative tests used
the separate `ci` database with synthetic records.

## Defects reproduced and fixed

- Faculty available casual leave included expired/future allocations and did not
  reserve pending requests. A fixture with 10 expired and 5 current days displayed
  15 instead of 5. Reuse Odoo's allocation calculation and virtual remaining
  balance. A submitted working day now changes availability from 5 to 4.
- The public faculty leave RPC accepted malformed payloads until raw Python
  exceptions occurred. Validate the payload, type identifier and reason before
  creating leave. Explicit employee/identity overrides are rejected. Odoo retains
  allocation, overlap, approval and company rules.
- Parent snapshots inherited student submission explanations and file identifiers;
  the parent download route also returned student coursework files. Remove the
  student-only assignment projection and restrict parent document kinds to
  receipts, approved materials, released admission documents, own request results
  and published notice attachments. Released homework feedback remains available.
- An explicit numeric child `0` or `false` silently selected the first child.
  Reject those invalid selections instead of falling back. An omitted child still
  selects the first authorized child for initial sign-in.

## Verification

- Local full Odoo module run: 85 tests, zero failures/errors. A later focused run
  of 16 faculty/parent tests passed after adding officer approval and invalid-child
  regressions.
- Faculty sign-in and all 11 available main modules rendered in the browser.
  All 51 distinct native screen actions compiled their views and queried permitted
  records under an ordinary faculty identity without errors.
- Faculty browser writes: leave submission changed availability from 5 to 4 and
  showed Pending; qualification and appraisal records saved and survived reload.
  Model tests cover half days, pending balance, approved balance, officer approval,
  self-approval denial, other-employee history, malformed input, portal denial and
  missing employee configuration.
- Parent browser: all 11 default modules for both linked children (22 destinations)
  rendered with the correct child. Existing request, receipt, document, revoked
  link, publication, official-record immutability and transport-gating tests passed.
  New tests deny student draft/file access and invalid child zero/false selections.
- Existing faculty CI browser scenario now checks expired allocations, a saved
  leave application, pending balance and appraisal persistence. Parent CI adds
  private coursework to the fixture and verifies API redaction and HTTP 404 on
  its download route. Existing CI retains student, owner, finance/coursework,
  mobile browser checks, installation and module upgrade.

## Boundaries

This is evidence for the scenarios above, not a guarantee that every possible
configuration is free of errors. Check the PR's current CI result before merging.
SSO identity provisioning, the external LMS, production email delivery and a
production deployment were not validated. Faculty leave approval remains with
the configured Odoo approver; no staff roles or permissions were expanded.
