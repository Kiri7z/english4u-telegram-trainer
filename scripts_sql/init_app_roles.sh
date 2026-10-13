#!/bin/sh
set -eu
: "${WEB_DB_PASSWORD:?WEB_DB_PASSWORD is required}"
: "${BOT_DB_PASSWORD:?BOT_DB_PASSWORD is required}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file /scripts_sql/app_roles.sql
