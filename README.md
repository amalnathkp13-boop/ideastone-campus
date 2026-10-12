# Ideastone Campus

College ERP + LMS for Indian engineering and arts colleges, built by **Ideastone Technologies Pvt Ltd** on open-source foundations:

| Layer | Component | Licence | Role |
|---|---|---|---|
| ERP | [Odoo 17 Community](https://github.com/odoo/odoo) + [OpenEduCat 17.0](https://github.com/openeducat/openeducat_erp) | LGPL-3 | Admissions, students, faculty, fees & receipts, timetable, attendance, exams, library, parents portal, accounting, HR |
| LMS | [OpenOlat 21](https://www.openolat.com) | Apache-2.0 | Course content, SCORM, assessments, question banks, forums, e-portfolios |
| SSO | [Keycloak 26](https://www.keycloak.org) | Apache-2.0 | One login (OpenID Connect) for ERP and LMS |
| Ours | `addons/ideastone_campus`, `addons/ideastone_lms` | Proprietary (Ideastone) | Branding, Indian-college fields & master data, SSO wiring, LMS embedded in the ERP, user provisioning |

**One platform, one address, one login.** nginx serves everything from a single domain — `/` is the ERP, `/lms/` is the LMS, `/sso/` is the identity server — and Keycloak signs users in to both. The LMS opens *inside* the ERP's "Learning" app; students and faculty created in the ERP get their LMS accounts automatically.

![Ideastone Campus home](docs/screenshots/02-home.png)

## Quick start (Docker)

```bash
git clone --recurse-submodules https://github.com/<org>/ideastone-campus.git
cd ideastone-campus
cp .env.example .env            # change passwords for anything beyond local demo
docker compose up -d --build    # first start takes ~5 min: installs OpenEduCat + demo data
```

| What | URL | Login |
|---|---|---|
| **Ideastone Campus** (everything) | http://localhost | `admin` / `admin`, or **Log in with Ideastone SSO** → `demo.admin` / `demo1234` |
| Learning platform (OpenOlat) | http://localhost/lms/ — also inside the ERP under **Learning** | SSO, or `administrator` / `openolat` (change on first login) |
| Identity server (Keycloak admin console) | http://localhost/sso/admin/ | `admin` / `admin` |

Set `CAMPUS_DOMAIN` / `CAMPUS_PUBLIC_URL` in `.env` to the real hostname before deploying for a college.

`ODOO_DEMO=true` (default) loads OpenEduCat's demo students, courses and fees so the system is presentable immediately. Set it to `false` in `.env` before the first start for a clean production database.

Watch the first-boot install: `docker compose logs -f odoo`.

## Running without Docker (development)

Tested on Ubuntu 24.04 / Python 3.12 / PostgreSQL 16:

```bash
git clone --recurse-submodules <repo> && cd ideastone-campus
git clone --depth 1 -b 17.0 https://github.com/odoo/odoo.git ../odoo
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r ../odoo/requirements.txt psycopg2-binary
cp dev/odoo-dev.conf.example dev/odoo-dev.conf   # edit addons_path / db settings
python ../odoo/odoo-bin -c dev/odoo-dev.conf -d campus -i ideastone_campus
```

Then open http://localhost:8069 (admin / admin).

## What the Ideastone modules add

`ideastone_lms`
* **Campus home** — one launcher screen with a tile per module (Admissions, Students, Faculty, Fees, Attendance, Exams, Timetable, Library, Learning).
* **Learning** app — OpenOlat embedded inside the Ideastone Campus UI (iframe on the same domain, same SSO session), plus "Open in new tab".
* **LMS accounts** — *Create LMS account* on every student/faculty record (and a list action for bulk), nightly cron for automatic provisioning, OpenOlat course key on each programme so students are enrolled on sync. Settings under *Ideastone Campus → Settings*.

`ideastone_campus`
* **Single sign-on** — Keycloak OIDC provider pre-configured; the login page shows *Log in with Ideastone SSO*. New SSO users get an Odoo account on first login.

* **Ideastone Campus** top-level menu grouping the office's daily screens: Admissions, Students, Faculty, Fee terms, Attendance sheets, Exams.
* Student record: **university register no** (unique), **admission quota** (Govt / Management / NRI), **community** (for scholarships), **hosteller**, **college bus**, Aadhaar last-4; list/search filters for these.
* Company: **affiliation** (e.g. Anna University), **approval** (AICTE), **NAAC grade**, **college code** – for receipts and marksheets.
* Reference data: 8 departments, 9 programmes (B.E./B.Tech/M.E./MBA), 2026 batches, academic year 2026-27 with odd/even semesters.
* Branding: login page, window title, brand colours, footer; INR + Asia/Kolkata + India defaults on install.

Everything the client asks for goes into this module (or a new sibling module under `addons/`). **Never edit files under `vendor/`** – see [docs/architecture.md](docs/architecture.md) for why and how to extend instead.

## Screenshots

| Login | Students | Student form |
|---|---|---|
| ![](docs/screenshots/01-login.png) | ![](docs/screenshots/03-students.png) | ![](docs/screenshots/07-student-form.png) |

## Repository layout

```
addons/ideastone_campus/   our Odoo module: branding, Indian-college fields, master data, SSO
addons/ideastone_lms/      our Odoo module: Campus home, embedded LMS, OpenOlat provisioning
vendor/openeducat_erp/     OpenEduCat 17.0 – git submodule, unmodified
odoo/                      Odoo image build, config, first-boot installer
openolat/                  OpenOlat on Tomcat 10.1 – image build + config templates
keycloak/                  realm export with ERP/LMS clients and demo users
nginx/                     reverse-proxy config
scripts/                   DB init and helper scripts
dev/                       local (non-Docker) development config
docs/                      architecture, SSO setup, screenshots
.github/                   CI (lint + install smoke test), PR & issue templates
```

## Contributing

Work happens on branches and lands through pull requests – see [CONTRIBUTING.md](CONTRIBUTING.md). CI must pass (lint + a real `-i ideastone_campus` install against Odoo 17) before merge.

## Licensing summary

* Odoo Community and OpenEduCat are LGPL-3: we use them unmodified and extend them from our own module. If we ever patch a file under `vendor/`, that patch must be shared with the customer who receives it; keeping vendor code untouched avoids this entirely.
* OpenOlat and Keycloak are Apache-2.0: free to modify and redistribute with attribution.
* `addons/ideastone_campus` and everything else in this repository is © Ideastone Technologies Pvt Ltd.
* "OpenEduCat", "Odoo", "OpenOlat" and "Keycloak" are trademarks of their owners; the product is marketed as **Ideastone Campus**.
