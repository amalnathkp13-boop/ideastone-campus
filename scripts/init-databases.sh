#!/bin/bash
# Runs once when the PostgreSQL volume is first created.
# Odoo creates its own database; OpenOlat and Keycloak need theirs ready.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE DATABASE openolat;
    CREATE DATABASE keycloak;
EOSQL
