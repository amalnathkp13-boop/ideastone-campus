#!/bin/bash
# Bring a running Ideastone Campus to the latest main.
#   ./scripts/update.sh
# Pulls the code (and OpenEduCat submodule), rebuilds images if needed and restarts.
# On restart Odoo sees the code changed and upgrades the modules by itself.
set -e
cd "$(dirname "$0")/.."

echo "==> Pulling latest main"
git pull --ff-only
git submodule update --init --recursive

echo "==> Rebuilding and restarting"
docker compose up -d --build

echo "==> Waiting for Odoo to finish the upgrade (Ctrl+C to stop watching; it keeps running)"
docker compose logs -f --since 1m odoo | sed -u '/campus: \(upgrade complete\|code unchanged\|install complete\)/q'

echo "==> Done. Hard-refresh the browser (Ctrl+Shift+R) to load the new screens."
