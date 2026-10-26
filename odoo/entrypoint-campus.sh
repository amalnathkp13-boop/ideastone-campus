#!/bin/bash
# Ideastone Campus — Odoo startup.
#   First boot : create the database and install all Ideastone modules (+ OpenEduCat).
#   Every boot : if the add-on code changed since the last start (git pull / merged PR),
#                upgrade the Ideastone modules automatically, then start Odoo.
# So "git pull && docker compose up -d" is all anyone needs to get the latest version.
set -e

: "${HOST:=db}" "${USER:=odoo}" "${PASSWORD:=odoo}" "${ODOO_DB:=campus}" "${ODOO_DEMO:=true}"
: "${CAMPUS_MODULES:=ideastone_campus,ideastone_lms,ideastone_erp,ideastone_ai}"
: "${CAMPUS_AUTO_UPGRADE:=true}"
STAMP=/var/lib/odoo/.campus-code-hash
DB_ARGS=(--db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD")

export PGPASSWORD="$PASSWORD"
until psql -h "$HOST" -U "$USER" -d postgres -c '\q' >/dev/null 2>&1; do
  echo "campus: waiting for postgres at $HOST..."; sleep 2
done

# Fingerprint of everything that can change module behaviour: our add-ons + OpenEduCat.
code_hash() {
  find /mnt/ideastone-addons /mnt/openeducat -type f \
       \( -name '*.py' -o -name '*.xml' -o -name '*.csv' -o -name '*.js' -o -name '*.scss' -o -name '*.json' \) \
       -not -path '*/__pycache__/*' -print0 2>/dev/null \
    | sort -z | xargs -0 sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1
}
CURRENT=$(code_hash)

if ! psql -h "$HOST" -U "$USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$ODOO_DB'" | grep -q 1; then
  echo "campus: first boot — creating database '$ODOO_DB' and installing $CAMPUS_MODULES (this takes a few minutes)"
  DEMO_FLAG=""
  [ "$ODOO_DEMO" = "true" ] || DEMO_FLAG="--without-demo=all"
  odoo -c /etc/odoo/odoo.conf -d "$ODOO_DB" -i "$CAMPUS_MODULES" $DEMO_FLAG --stop-after-init "${DB_ARGS[@]}"
  echo "$CURRENT" > "$STAMP"
  echo "campus: install complete"
elif [ "$CAMPUS_AUTO_UPGRADE" = "true" ] && [ "$CURRENT" != "$(cat "$STAMP" 2>/dev/null)" ]; then
  echo "campus: code changed since last start — upgrading $CAMPUS_MODULES"
  # -i installs any module that is new in CAMPUS_MODULES; -u upgrades the rest.
  odoo -c /etc/odoo/odoo.conf -d "$ODOO_DB" -i "$CAMPUS_MODULES" -u "$CAMPUS_MODULES" --stop-after-init "${DB_ARGS[@]}"
  echo "$CURRENT" > "$STAMP"
  echo "campus: upgrade complete"
else
  echo "campus: code unchanged — starting"
fi

exec /entrypoint.sh "$@" --database="$ODOO_DB"
