# Rupee display throughout the ERP

Branch: `codex/inr-currency-uniformity`.

The requested change is presentation only. Existing monetary numbers, stored currency IDs/codes/symbols, company currencies, rounding rules, rates, conversions, posting/reconciliation, and payroll calculations remain unchanged. Currency configuration fields still show their true stored values; amounts use ₹. No migration rewrites financial records.

## Changes by login and module

| Area | Amount displays covered | Implementation |
| --- | --- | --- |
| Every backend login: owner/admin, accountant, Principal, faculty/staff, HOD, COE | Native monetary fields in forms, lists, popups, totals, and charts that use Odoo's currency metadata | `ideastone_campus/models/currency_display.py`: copies web/frontend session metadata with the rupee display glyph; retains currency IDs, position, precision and cached source metadata |
| All printed reports | Monetary fields in fee receipts, payslips, invoices, vendor bills, purchase reports, including tax totals, subtotals and cash-rounding labels | Same shared model extension; native HTML markup and number formatting are retained. Only `formatted_*` tax-summary strings change |
| Shared server formatting | Plain-text currency formatting and student/parent portal amounts | `ideastone_campus/currency_display.py`, `ideastone_erp/controllers/student_portal.py`, `controllers/parent_portal.py` |
| Shared money icons | Dollar aliases and the dollar banknote icon, including the upstream OpenEduCat payment icon | `ideastone_campus/static/src/scss/brand.scss`: substitutes the FontAwesome rupee glyph, preserving font, size and color |
| Owner/admin | Overview fee collection/outstanding cards, monetary summaries, chart labels, financial insights, fee follow-ups; Fees & Payments amounts | `ideastone_erp/models/mvp_dashboard.py`, `models/admin_overview_ui.py`, `static/src/js/dashboard.js`, `static/src/js/owner_fees.js` |
| Accountant | Dashboard; collections overview, fee structures, assignments, invoices, receipts, dues and CSVs; student fee directory, pending students and fee accounts | `ideastone_erp/static/src/js/dashboard.js`, `static/src/js/accountant_directory.js`; native detail forms use the shared layer |
| Accountant spending | Maintenance/event spending cards, charts, bill amounts, tables and new-bill popup label | `ideastone_erp/static/src/js/accountant_spending.js`, `static/src/xml/accountant_spending.xml` |
| Accountant transport | Transport revenue/expenses, route amounts and salary displays | `ideastone_erp/static/src/js/accountant_transport.js`; native entries use the shared layer |
| Faculty/staff/HOD and owner staff reports | Salary agreements, monthly salary, salary trends, payroll history, deductions, contributions and CSV column units | `ideastone_erp/static/src/js/faculty_profile_workspace.js`, `static/src/xml/faculty_profile_workspace.xml`, `static/src/js/payroll_history.js` (also inherited by owner payroll) |
| Principal Faculty & Staff | Attendance/payroll, salary and deduction report amounts | `ideastone_principal/static/src/js/staff_workspace.js` |
| Student and parent | Dashboard fee summaries, fee structures, invoices, dues, payments/receipts, library fines and request fees wherever the portal money helper is used | `ideastone_erp/models/student_service.py` and the two portal controllers; existing ₹-formatted screens stay as they are |
| AI insights | Student-success radar overdue amounts/CSV unit; Campus Assistant monetary display instruction | `ideastone_ai/models/success_radar.py`, `models/assistant.py`, `static/src/js/success_radar.js`. Stored/source currency codes are retained; the provider is instructed to display ₹ without conversion |

Version bumps in the four affected manifests load the updated models and assets. The sidebar, workflow buttons, layouts, heading styles and amount typography are unchanged. JavaScript template placeholders, regular expressions, shell variables and other non-currency uses of `$` are intentionally retained. Vendor source and historical reference screenshots are not rewritten.

## Verification

- Four Odoo currency regression tests cover zero/negative/large amounts, original currency precision/position, escaped symbols, session metadata isolation, tax totals and native invoice cash rounding.
- Eight Principal backend tests passed during the upgrade check.
- Seventeen JavaScript checks pass, including USD-backed formatter examples, unchanged compact chart scales, payroll rounding, source data preservation, CSV escaping, session navigation and faculty OD behavior.
- Ruff, XML validation, JavaScript syntax, navigation reconciliation and diff whitespace checks pass.
- Browser verification: the USD-backed owner dashboard shows ₹92,000.00 collected and ₹192,000.00 outstanding; native invoice 206 shows ₹112,000.00 total, ₹92,000.00 paid and ₹20,000.00 due while its currency configuration still reads USD. The printable native invoice shows ₹ for line amounts and total.
- Before/after checksums match for all invoice amount/residual/state/currency/company tuples, all currency definitions, all company currency assignments and all exchange-rate records in the cloned preview database.

The isolated preview is `http://inr.localhost:18097`, database `inr_display_preview`, cloned from the existing Principal staff preview. Credentials remain outside Git. Other localhost preview containers have not been upgraded by this task. No push or PR was created.

Deployment, when approved: upgrade `ideastone_campus,ideastone_erp,ideastone_ai,ideastone_principal`, restart Odoo and reload each browser session so its currency metadata and assets refresh. Omit optional modules that are not installed in the target database.
