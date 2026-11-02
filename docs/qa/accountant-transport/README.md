# Accountant transport billing

The Transport billing sidebar entry opens the four-view workspace. Fleet, revenue/expenses and driver salary screens use current-college records and the selected academic year.

- A fleet record represents the existing bus/route assignment for an academic year. Its capacity includes approved student allocations and the saved staff rider count. Campus Services retains approval of student allocations and boarding-point fees.
- Student fee bills opens approved allocations. Creating a fee bill links the native student invoice to its route; actual college receipts and reversals drive revenue.
- Add transaction opens a native vendor bill. Select its bus/route, transport category, vendor and expense lines, then post it. Draft bills remain visible in the ledger but do not enter operating expenses. Foreign-currency vendor bills use their signed company-currency amount in totals.
- New payroll run opens a monthly driver salary record. Base salary plus allowance minus deductions determines the linked vendor bill. Create or open salary bill is idempotent; post and pay that bill using Accounting. Paid, Processing and Pending labels follow the linked bill. A salary is counted once, through the bill.
- Maintenance budget allocations are saved on fleet records and shown separately from expenses. They never inflate spending totals.
- Search, fleet/payment/type filters and CSV exports apply to visible records. Opening an existing row opens its saved native record. Reload preserves the selected transport screen.

## Local QA

Use the isolated `accountant_ui_preview` database on port 18069. `seed.py` is intentionally guarded for this database and its INR preview company; it must not run against the working college database. It adds synthetic routes, riders, invoices, receipts, vendor bills and driver salary records.

Run Odoo tests with `--test-tags /ideastone_erp:TestAccountantTransport,/ideastone_erp:TestAccountantWorkspace`. They verify saved riders/receipts, completed allocation history, capacity, salary arithmetic, immutable invoice classification, access restrictions, and no double counting of draft/posted salary bills.

Browser verification covers all four tabs; Manage fleet; View fleet & routes; View all transactions; Add bus and save/refresh; Add transaction; Student fee bills and its invoice redirect; New payroll run; saved receipt/bill/payroll links; search/status/type filters; and all three CSV downloads. Check page overflow at 1440, 820, 390 and 320 pixels. Tables and tabs scroll inside their own containers on narrow screens.

