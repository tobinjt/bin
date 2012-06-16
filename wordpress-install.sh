#!/bin/bash

set -e
set -u

die() {
    echo "$@" 1>&2
    exit 1
}
usage() {
    die "Usage: $0 [themes|plugins] NAME VERSION"
}

if [[ "$#" -ne 3 ]]; then
    usage
fi
TYPE="$1"
NAME="$2"
VERSION="$3"
readonly TYPE NAME VERSION
if [[ "${TYPE}" != "plugins" && "${TYPE}" != "themes" ]]; then
    usage
fi

WORDPRESS_BASE="/var/www/sites/arianetobin.ie/blog"
readonly WORDPRESS_BASE
cd "${WORDPRESS_BASE}/wp-content/${TYPE}"
if [[ -n "$( git status --short )" ]]; then
    die "Uncommitted changes."
fi

DOWNLOAD_DIR="/home/ariane/wordpress"
DOWNLOAD_FILE="${NAME}.${VERSION}.zip"
DOWNLOAD_PATH="${DOWNLOAD_DIR}/${DOWNLOAD_FILE}"
if [[ "${TYPE}" == "themes" ]]; then
    DOWNLOAD_URL="http://wordpress.org/extend/themes/download/${DOWNLOAD_FILE}"
elif [[ "${TYPE}" == "plugins" ]]; then
    DOWNLOAD_URL="http://downloads.wordpress.org/plugin/${DOWNLOAD_FILE}"
fi
readonly DOWNLOAD_DIR DOWNLOAD_FILE DOWNLOAD_PATH DOWNLOAD_URL
if [[ ! -f "${DOWNLOAD_PATH}" ]]; then
    curl --output "${DOWNLOAD_PATH}" "${DOWNLOAD_URL}" || rm "${DOWNLOAD_PATH}"
fi

unzip -q -o "${DOWNLOAD_PATH}"
git add "${NAME}"
(unset LESS; git diff --cached --shortstat)
git commit --quiet --message "Installed ${NAME} ${VERSION}"
