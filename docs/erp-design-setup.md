# VCET design and deployment

## Design source

The user-provided `Logo/VCET_Staff_Profile_Complete.html` defines the visual system. The supplied wide VCET PNG is used directly as an original college asset. Its source was inspected; its browser-local sample data was not imported. Old ERP screenshots informed fields and workflows only. No ImpresERP code or assets were copied.

| Token | Value |
|---|---|
| Navy / secondary navy | `#062743` / `#0b3554` |
| Text / muted text | `#102b50` / `#697c96` |
| Primary / hover | `#0666e7` / `#0655cf` |
| Page / surface | `#f4f8fc` / white |
| Border | `#e4ebf4` |
| Success / warning / danger | `#159d55` / `#e99612` / `#e54856` |
| Radius / shadow | 12px / `0 5px 20px rgba(15,50,91,.045)` |
| Font stack | Inter, Segoe UI, Arial, sans-serif (no external font download) |

The global token file is `addons/ideastone_campus/static/src/scss/brand.scss`. Native Odoo forms, lists, controls and dialogs use the same colors, border treatments and focus outlines. Campus cards, navigation and portal reuse those tokens. The 222px navy sidebar stays beside all backend actions through Odoo's `main_components` registry. The white Odoo header retains working account, messaging and application controls. Cards use 13px gaps; page padding is 22–23px. Headings follow the supplied 25px page and 15.5px section hierarchy.

At 1100px the module grid and summaries become two columns. Below 768px the navigation becomes a toggle-controlled drawer, tables retain horizontal scrolling, and modules become a single column. Below 440px summary cards become a single column. Buttons are semantic and keyboard operable, search fields have labels, focus rings are visible, and status/error content uses live roles. The original logo is clipped with CSS for the compact sidebar and shown at its natural ratio in the portal/login.

Browser automation rejected localhost URLs with `ERR_BLOCKED_BY_CLIENT`; therefore desktop/mobile visual appearance, focus traversal, drawer interaction and screenshot comparison have **not** been certified. HTTP checks and compiled CSS/JS checks complement the model tests but do not replace browser QA. These outstanding checks must be completed before production release.

## Installation and upgrade

The extension uses standard Odoo 17 Community modules already supplied by the Odoo image: HR attendance/leave, purchase/stock, maintenance, CRM, surveys, events/forums, payment and portal. There is no additional backend runtime dependency. Development smoke tests require `requests`; lint requires `ruff`.

Fresh startup installs `ideastone_campus,ideastone_lms,ideastone_erp`. Existing databases require an explicit install, with a backup beforehand:

```bash
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d campus -u ideastone_campus -i ideastone_erp --stop-after-init
docker compose restart odoo
```

Odoo creates tables, foreign keys, constraints, permissions, actions and views during installation. Existing OpenEduCat tables are extended by inheritance; there is no destructive migration or vendor modification. No reference screenshot records or operational demo fixtures are added. Existing OpenEduCat demo data remains controlled by `ODOO_DEMO`. College company identity is retained; the user can set its supplied logo and approved institutional details under Companies.

Assign Campus Operations roles under Settings → Users. The campus manager can approve records and has all operations roles. Academic, services, HR/payroll, outreach, purchasing and finance roles are separate. Faculty can maintain their own extended records where their OpenEduCat identity is linked. HR employee `user_id`, faculty `user_id`, student `user_id`, and OpenEduCat parent `child_ids` must be correctly mapped by an administrator. These relationships are never inferred from matching names or email strings. Company-wide directory access is read-only for operational roles.

Configure the employee work calendar and attendance ownership before payroll. Salary agreements define pay, contribution bases/rates and deductions; there are no hardcoded statutory rates. Paid leave is classified by the payroll operator against approved leave records. These calculations are a configurable payroll foundation, not a certified statutory filing package. Accounting journals, income accounts, products, taxes, currency and payment providers must be configured before posting invoices. Procurement creates a draft PO and does not commit funds automatically.

Existing Keycloak and OpenOlat configuration is retained. Live gateway, device API, SMS and WhatsApp credentials/protocols were not supplied or verified. Biometric events can be imported through authenticated Odoo ORM/CSV with unique device references. Connecting a particular device remains adapter work. Odoo invoice portal payment works only after an administrator configures a supported provider. Parent invoice payment delegation is not automatically widened. Outbound email requires the existing Odoo mail-server configuration.

## Verification commands

Three startup corrections already present in the user's original checkout were carried into the isolated feature branch: bind Odoo to its configured database, create OpenOlat directories without shell brace expansion, and enable Tomcat deployment at startup. The original checkout and its uncommitted edits remain unchanged. Both Docker images built successfully; the Odoo entrypoint passed Bash syntax validation. The existing LMS homepage and Keycloak discovery endpoint returned HTTP 200. Those endpoint checks establish reachability, not a complete live SSO or LMS workflow test.

```bash
ruff check addons/
python -c "import glob,xml.etree.ElementTree as E; [E.parse(f) for f in glob.glob('addons/**/*.xml', recursive=True)]"
docker compose config -q
# Use a separate disposable database for fixtures and workflow tests:
odoo -d erp_qa -i ideastone_erp --test-enable --test-tags=/ideastone_erp --stop-after-init
# HTTP smoke test against that same disposable database:
ERP_QA_PASSWORD=admin python scripts/test-erp-http.py --database erp_qa --url http://localhost:18069
```

The HTTP script creates only named QA fixtures and refuses database names lacking `qa`, `ci`, or `test`. Its password is read from the environment. Do not run it against the college's operational database. `scripts/generate-erp-views.py` regenerates checked-in model views, actions, navigation and access rules; review its diff after regeneration.

CI installs the complete dependency graph in PostgreSQL, runs the extension's critical tests and retains diagnostic logs. There is no separate JavaScript bundler or TypeScript compiler: Odoo builds its assets on first HTTP request. Upstream OpenEduCat emits existing field-label/tracking warnings; test assertions and Odoo process results establish success.
