#!/bin/bash

set -e
set -u

die() {
    echo -e "$@" 1>&2
    exit 1
}
usage() {
    die "Usage: $0 [theme|plugin|wordpress] NAME VERSION"
}

if [[ "$#" -ne 3 ]]; then
    usage
fi
TYPE="$1"
NAME="$2"
VERSION="$3"
readonly TYPE NAME VERSION SUBDIR
if [[ "${TYPE}" != "plugin" && "${TYPE}" != "theme" \
        && "${TYPE}" != "wordpress" ]]; then
    usage
fi

declare -A SUBDIRS SEPARATORS
SUBDIRS[wordpress]=".."
SUBDIRS[plugin]="plugins"
SUBDIRS[theme]="themes"
SEPARATORS[wordpress]="-"
SEPARATORS[plugin]="."
SEPARATORS[theme]="."
readonly SUBDIRS SEPARATORS
WORDPRESS_BASE="/var/www/sites/arianetobin.ie/blog"
readonly WORDPRESS_BASE
cd "${WORDPRESS_BASE}"
git_status="$( git status --short )"
if [[ -n "${git_status}" ]]; then
    die "Uncommitted changes:\n" "${git_status}"
fi
cd "${WORDPRESS_BASE}/wp-content/${SUBDIRS[${TYPE}]}"

DOWNLOAD_DIR="/home/ariane/wordpress"
DOWNLOAD_FILE="${NAME}${SEPARATORS[${TYPE}]}${VERSION}.zip"
DOWNLOAD_PATH="${DOWNLOAD_DIR}/${DOWNLOAD_FILE}"
declare -A DOWNLOAD_URLS
DOWNLOAD_URLS[wordpress]="http://wordpress.org/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[plugin]="http://downloads.wordpress.org/plugin/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[theme]="http://wordpress.org/extend/themes/download/${DOWNLOAD_FILE}"
readonly DOWNLOAD_URLS DOWNLOAD_DIR DOWNLOAD_FILE DOWNLOAD_PATH
if [[ ! -f "${DOWNLOAD_PATH}" ]]; then
    curl --output "${DOWNLOAD_PATH}" "${DOWNLOAD_URLS[${TYPE}]}" \
        || rm "${DOWNLOAD_PATH}"
fi

unzip -q -o "${DOWNLOAD_PATH}"
if [[ "${TYPE}" == "wordpress" ]]; then
    # Wordpress extracts into a directory named wordpress, and unzip doesn't
    # have an option to strip a leading directory, so move it with tar, then
    # delete it.
    tar cf - -C wordpress . | tar xf -
    rm -rf wordpress
    echo "You must go to dashboard/updates for a database update."
    echo "If that loops, rename wp-super-cache plugin, or force reload."
fi
git add .
(unset LESS; git diff --cached --shortstat)
git commit --quiet --message "Installed ${NAME} ${VERSION}"
