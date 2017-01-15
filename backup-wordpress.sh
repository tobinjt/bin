#!/bin/bash

set -e -f -u -o pipefail

PATH="${PATH}:/usr/sbin"

wp_option() {
  local option="$1" config="$2"
  readonly option config

  awk -F \' "/${option}/"' { print $4 }' "${config}"
}

main() {
  local config="$1/wp-config.php" db_password db_name db_user date
  readonly config
  db_password="$(wp_option DB_PASSWORD "${config}")"
  db_name="$(wp_option DB_NAME "${config}")"
  db_user="$(wp_option DB_USER "${config}")"
  date="$(date +%Y-%m-%d-%H-%M)"
  readonly db_password db_name db_user date

  for command in --check --analyze; do
    mysqlcheck "${command}" --auto-repair --silent \
      --user="${db_user}" --password="${db_password}" --databases "${db_name}"
  done
  mkdir -p "${HOME}/wordpress-backups"
  cd "${HOME}/wordpress-backups"
  mysqldump --add-drop-table --host=localhost \
      --user="${db_user}" --password="${db_password}" --databases "${db_name}" \
    | bzip2 -c > "${db_name}_${date}"_sql.bz2
  tmpreaper --mtime 90d .
}

main "$1"
