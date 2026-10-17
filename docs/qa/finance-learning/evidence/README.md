# Finance and learning verification

Captured on 17 October 2026 against a separate synthetic `campus_mvp_qa` database, native Odoo 17 and PostgreSQL 16, with real Chrome. Existing local previews were not upgraded.

- Full ERP backend suite: **78 tests, 0 failures, 0 errors**. The eight new cases are in `addons/ideastone_erp/tests/test_finance_learning.py`.
- Installed-module upgrade completed. The final follow-up list view was upgraded and checked in the browser after the suite.
- Browser: concurrent collection attempts on different invoices produced exactly one receipt and one reduction in outstanding balance; all three learning submodule views loaded; a student submitted a real text file; faculty explicitly confirmed and released zero marks; student and linked parent saw the released result. Layout checks covered 1440px and 390px with no page JavaScript errors.
- Static checks: Ruff across `addons/` and `scripts/`, all addon XML parsing, browser syntax, and Git whitespace checks passed.

`verification.json` is the final browser output. Screenshots contain labelled synthetic college/student records only. Repeated local runs left several demonstration assignments; they are real saved records, not mock API responses. Use a newly seeded disposable database when the fixture invoices have been fully collected.

CI adds the same scenario after existing Faculty/Owner/Student/Parent checks and preserves its evidence as `finance-learning-proof`. Local results do not imply that the GitHub run has finished. Docker execution itself was unavailable on this Windows host; the local suite used native Odoo/PostgreSQL.

OpenOlat provisioning failure/retry uses a deterministic client in backend tests. No live external LMS, SSO, bank settlement or payment-provider result is claimed. New transaction keys apply to new collections; historical receipt-reference review remains an explicit migration task.
