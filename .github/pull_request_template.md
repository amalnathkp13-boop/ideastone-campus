## What

<!-- One or two sentences: what does this PR change? -->

## Why

<!-- Client request / issue link / reason -->

## How was it tested

- [ ] `docker compose up -d --build` from clean (`down -v`) installs without errors
- [ ] `-u ideastone_campus` on an existing database works
- [ ] Manually checked the screens touched (list below)

## Screenshots (UI changes)

## Checklist

- [ ] No files under `vendor/` were modified
- [ ] New data is in `data/` (noupdate) or `demo/` as appropriate
- [ ] `__manifest__.py` version bumped if views/data changed
- [ ] `ruff check addons/` passes
