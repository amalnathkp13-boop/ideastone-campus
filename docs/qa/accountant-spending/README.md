# Accountant Spending preview

Reference: `Spending_Module_Updated.html` (main content only).

The Spending navigation opens Event bills and Maintenance bills. Both screens use saved
`account.move` vendor bills/credits, restricted to the active company and the accountant role.
Drafts appear as unpaid and cancelled bills are excluded. Foreign-currency figures are converted
to the company currency at the bill date. Charts show bill totals and the settled amount for
bills dated in each month, rather than cash payments made in that month.

New bill saves a draft with a real partner, department, date, reference and expense line.
Changing category redirects to the matching tab after saving. View opens the details popup;
Open bill uses the existing Odoo posting/payment workflow. No accounting approvals or access
rules are bypassed. The sidebar and shared top bar retain their existing implementation.

## Local verification

- Accountant transaction tests: draft creation, totals, cancellation, invalid amounts/fields,
  role access, college/department isolation, and both client-action redirects.
- Ruff, XML/Python syntax, JavaScript syntax and Sass compilation.
- Browser: both tabs, search/empty/reset, department/payment filters, chart periods,
  details/native bill popups, required fields and a newly saved maintenance draft.
- Desktop 1280/1440, tablet 820, phones 390/320; wide tables scroll within the panel.
  Popup fits a 320px viewport; keyboard focus wraps and Escape closes it.
- Live typography and palette checked against reference CSS: title 29px/700,
  section titles 16px/700, main text Inter/Segoe UI/Arial, navy #102c46,
  canvas #f4f8fc, borders #dce7f3 and blue #1769d2. Scoped overrides preserve these
  values when the shared campus theme is loaded.

Preview database: `accountant_spending_preview`, cloned from the existing sample accountant
preview. Additional sample bills and settlements exist only in that local database.
Preview: http://spending.localhost:18092/web#action=938&cids=13

Branch: `codex/accountant-spending-reference`. No push or pull request before preview approval.
