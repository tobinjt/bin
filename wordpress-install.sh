#!/bin/bash

set -e
set -u

die() {
    echo -e "$@" 1>&2
    exit 1
}
usage() {
    die "Usage: $0 WORDPRESS-DIRECTORY [theme|plugin|wordpress] NAME VERSION"
}

if [[ "$#" -ne 4 ]]; then
    usage
fi
WORDPRESS_BASE="$1"
TYPE="$2"
NAME="$3"
VERSION="$4"
readonly WORDPRESS_BASE TYPE NAME VERSION SUBDIR
if [[ "${TYPE}" != "plugin" && "${TYPE}" != "theme" \
        && "${TYPE}" != "wordpress" ]]; then
    usage
fi
cd "${WORDPRESS_BASE}"
git_status="$( git status --short )"
if [[ -n "${git_status}" ]]; then
    die "Uncommitted changes:\n" "${git_status}"
fi

declare -A SUBDIRS SEPARATORS
SUBDIRS[wordpress]=".."
SUBDIRS[plugin]="plugins"
SUBDIRS[theme]="themes"
SEPARATORS[wordpress]="-"
SEPARATORS[plugin]="."
SEPARATORS[theme]="."
if [[ -z "${VERSION}" ]]; then
    # This happens with WP Minify.
    SEPARATORS[plugin]=""
fi
readonly SUBDIRS SEPARATORS
cd "${WORDPRESS_BASE}/wp-content/${SUBDIRS[${TYPE}]}"

DOWNLOAD_DIR="${HOME}/wordpress"
DOWNLOAD_FILE="${NAME}${SEPARATORS[${TYPE}]}${VERSION}.zip"
DOWNLOAD_PATH="${DOWNLOAD_DIR}/${DOWNLOAD_FILE}"
readonly DOWNLOAD_DIR DOWNLOAD_FILE DOWNLOAD_PATH
declare -A DOWNLOAD_URLS
DOWNLOAD_URLS[wordpress]="http://wordpress.org/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[plugin]="http://downloads.wordpress.org/plugin/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[theme]="http://wordpress.org/extend/themes/download/${DOWNLOAD_FILE}"
readonly DOWNLOAD_URLS
mkdir -p "${DOWNLOAD_DIR}"
if [[ ! -s "${DOWNLOAD_PATH}" ]]; then
    if ! curl --output "${DOWNLOAD_PATH}" "${DOWNLOAD_URLS[${TYPE}]}" ; then
        rm "${DOWNLOAD_PATH}"
        die "Failed to download: ${DOWNLOAD_URLS[${TYPE}]}"
    fi
    if [[ ! -s "${DOWNLOAD_PATH}" ]]; then
        die "Missing or empty file: ${DOWNLOAD_PATH}"
    fi
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
