# Contributing to Ideastone Campus

## Branch & PR workflow

1. **Never commit to `main` directly.** `main` is always deployable.
2. Create a branch from `main`:
   `feature/<short-name>` for new features, `fix/<short-name>` for bug fixes, `client/<college>-<topic>` for client-specific customisation.
3. Commit in small, logical steps. Message format: `area: what changed` — e.g. `student: add scholarship category field`.
4. Push and open a **pull request** against `main`. Fill in the PR template (what / why / how tested / screenshots for UI changes).
5. CI runs automatically: lint + a real install of `ideastone_campus` on Odoo 17. Fix anything red.
6. At least **one reviewer approves**, then **squash-merge**. Delete the branch.

Set this up once on GitHub → Settings → Branches → *Add rule* for `main`: require a pull request, require 1 approval, require status checks (`lint`, `install`) to pass.

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
