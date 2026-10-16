# Contributing to Ideastone Campus

## Branch & PR workflow

**Teammates open pull requests; the maintainer (@amalnathkp13-boop) reviews and merges.** Nobody pushes to `main` directly.

1. Update your local `main`: `git checkout main && git pull`.
2. Create a branch: `feature/<short-name>`, `fix/<short-name>` or `client/<college>-<topic>`.
3. Commit in small, logical steps. Message format: `area: what changed` — e.g. `student: add scholarship category field`.
4. Push the branch and open a **pull request** against `main`. Fill in the template (what / why / how tested / screenshots).
5. CI must be green (`lint` + `install`). Fix anything red by pushing more commits to the same branch.
6. The maintainer is requested automatically (CODEOWNERS), reviews, and either **approves and merges** or **requests changes**.
7. If changes are requested, push fixes to the same branch — the earlier approval is dismissed and the PR is reviewed again.
8. After merge, delete your branch and run `./scripts/update.sh` — it pulls `main` and restarts the stack, and Odoo upgrades the modules automatically. Merging alone does not change anyone's running copy.

What GitHub enforces on `main`:

| Rule | Effect |
|---|---|
| Pull request required | No direct pushes to `main` |
| 1 approval from a code owner | Only the maintainer's approval unlocks the merge button |
| Stale approvals dismissed | New commits after approval need a fresh review |
| Approval of the latest push | The person who pushed last cannot be the one who approves it |
| `lint` + `install` checks required, branch up to date | Nothing broken or stale reaches `main` |
| Conversations resolved | All review comments must be addressed |

## Automatic checks (CI)

You never start CI by hand. GitHub Actions runs it:

| When | What runs |
|---|---|
| A PR is opened, or new commits are pushed to it | `lint`, `install`, `docker images` |
| Something is merged to `main` | the same, on the merged code |
| Every night, 02:00 IST | the same, plus a test against the newest upstream OpenEduCat 17.0 — catches upstream breakage early |
| Every Monday | Dependabot opens PRs to update GitHub Actions, OpenEduCat and base Docker images |

* `lint` — ruff, XML and shell syntax, docker-compose config.
* `install` — real install of `ideastone_campus`, `ideastone_lms`, `ideastone_erp` on Odoo 17 + PostgreSQL 16 and the module tests. A summary appears on the run page; the full log is downloadable as an artifact.
* `docker images` — builds the Odoo and OpenOlat images so a broken Dockerfile is caught before deployment.

Pushing again to a PR cancels the run for the older commit. `lint` and `install` must be green before the merge button unlocks. To re-run manually: Actions → CI → *Run workflow*.

## Where code goes

| Change | Location |
|---|---|
| New field, view, report, menu, workflow | `addons/ideastone_campus/` (models / views / data / reports) |
| Large separate feature (e.g. hostel, transport, placement) | new module `addons/ideastone_<feature>/` depending on `ideastone_campus` |
| OpenEduCat behaviour you want different | **inherit and override** in our module — do not edit `vendor/` |
| Infra (Docker, nginx, Keycloak) | `odoo/`, `openolat/`, `keycloak/`, `nginx/`, `docker-compose.yml` |
| Docs | `docs/` |

## Odoo module conventions

* One file per model under `models/`, named after the model (`op_student.py`, `res_company.py`).
* Views inherit the OpenEduCat view by `ref="openeducat_core.view_op_student_form"` and use `xpath`; never copy a whole view.
* Reference data (departments, programmes) → `data/*.xml` with `noupdate="1"`. Demo-only data → `demo/*.xml` listed under `"demo"` in the manifest.
* Bump `"version"` in `__manifest__.py` (last digit) whenever data or views change, so `-u ideastone_campus` picks it up.
* After changing Python/XML: `docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d campus -u ideastone_campus --stop-after-init` then `docker compose restart odoo`.
* Python style: `ruff` (config in `pyproject.toml`). Run `ruff check addons/` before pushing.

## Updating OpenEduCat

`vendor/openeducat_erp` is a git submodule pinned to a commit on branch `17.0`.

```bash
cd vendor/openeducat_erp && git fetch && git checkout origin/17.0 && cd ../..
git add vendor/openeducat_erp && git commit -m "vendor: bump openeducat_erp"
```

Test with a fresh install (`docker compose down -v && docker compose up -d --build`) before merging a vendor bump.

## Reporting issues

Use the issue templates. For bugs include: steps, expected vs actual, screenshot, and `docker compose logs odoo --tail 200` if there is a traceback.
