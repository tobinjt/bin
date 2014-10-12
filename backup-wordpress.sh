#!/bin/sh

set -e -f -u -o pipefail

PATH="${PATH}:/usr/sbin"

db_password="$( awk -F \' '/DB_PASSWORD/ { print $4 }' \
                /home/ariane/arianetobin.ie/blog/wp-config.php )"
date="$( date +%Y-%m-%d-%H-%M )"
cd "${HOME}/wordpress-backups"
mysqlcheck --analyze --auto-repair --check --repair --silent \
  --password="${db_password}" --databases ariane_blog
mysqldump --add-drop-table -h localhost -u ariane --password="${db_password}" \
        ariane_blog \
    | bzip2 -c > ariane_blog_"${date}"_sql.bz2
tmpreaper --mtime 30d .
