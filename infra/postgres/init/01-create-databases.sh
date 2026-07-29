#!/bin/sh
set -eu

create_database() {
  db_name="$1"
  db_user="$2"
  db_password="$3"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$db_user') THEN
    CREATE ROLE $db_user LOGIN PASSWORD '$db_password';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE $db_name OWNER $db_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db_name')\gexec
GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;
SQL
}

create_database "$IDENTITY_DB" "$IDENTITY_DB_USER" "$IDENTITY_DB_PASSWORD"
create_database "$HQA_DB" "$HQA_DB_USER" "$HQA_DB_PASSWORD"
create_database "$SYNC_DB" "$SYNC_DB_USER" "$SYNC_DB_PASSWORD"
create_database "$HQS_DB" "$HQS_DB_USER" "$HQS_DB_PASSWORD"
