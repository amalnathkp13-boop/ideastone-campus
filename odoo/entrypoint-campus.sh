#!/bin/bash
# First boot: create the database and install the Ideastone Campus module
# (which pulls in the whole OpenEduCat suite). Later boots: just start Odoo.
set -e

: "${HOST:=db}" "${USER:=odoo}" "${PASSWORD:=odoo}" "${ODOO_DB:=campus}" "${ODOO_DEMO:=true}"

export PGPASSWORD="$PASSWORD"
until psql -h "$HOST" -U "$USER" -d postgres -c '\q' >/dev/null 2>&1; do
  echo "campus: waiting for postgres at $HOST..."; sleep 2
done

if ! psql -h "$HOST" -U "$USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$ODOO_DB'" | grep -q 1; then
  echo "campus: first boot — creating database '$ODOO_DB' and installing Ideastone Campus + LMS integration (this takes a few minutes)"
  DEMO_FLAG=""
  [ "$ODOO_DEMO" = "true" ] || DEMO_FLAG="--without-demo=all"
  odoo -c /etc/odoo/odoo.conf -d "$ODOO_DB" -i ideastone_campus,ideastone_lms,ideastone_erp $DEMO_FLAG --stop-after-init \
       --db_host="$HOST" --db_user="$USER" --db_password="$PASSWORD"
  echo "campus: install complete"
fi

exec /entrypoint.sh "$@" --database="$ODOO_DB"
