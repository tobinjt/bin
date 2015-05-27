#!/bin/bash

set -e
set -u

warn() {
    echo -e "$@" 1>&2
}
die() {
    warn "$@"
    exit 1
}
usage() {
    warn "Usage: $0 WORDPRESS-DIRECTORY wordpress VERSION"
    die "Usage: $0 WORDPRESS-DIRECTORY [theme[s]|plugin[s]] NAME VERSION"
}

if [[ "$#" -ne 4 ]]; then
    if [[ "$#" -eq 3 && "$2" == "wordpress" ]]; then
        set -- "$1" "wordpress" "wordpress" "$3"
    else
        usage
    fi
fi
WORDPRESS_BASE="$1"
TYPE="$2"
# Support plurals.
TYPE="${TYPE/plugins/plugin}"
TYPE="${TYPE/themes/theme}"
# Tab completion will add a trailing slash, remove it if present.
NAME="${3%/}"
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
readonly SUBDIRS SEPARATORS
cd "wp-content/${SUBDIRS[${TYPE}]}"

DOWNLOAD_DIR="${HOME}/wordpress"
DOWNLOAD_FILE="${NAME}${SEPARATORS[${TYPE}]}${VERSION}.zip"
DOWNLOAD_PATH="${DOWNLOAD_DIR}/${DOWNLOAD_FILE}"
readonly DOWNLOAD_DIR DOWNLOAD_FILE DOWNLOAD_PATH
declare -A DOWNLOAD_URLS
DOWNLOAD_URLS[wordpress]="https://wordpress.org/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[plugin]="https://downloads.wordpress.org/plugin/${DOWNLOAD_FILE}"
DOWNLOAD_URLS[theme]="https://downloads.wordpress.org/theme/${DOWNLOAD_FILE}"
readonly DOWNLOAD_URLS
mkdir -p "${DOWNLOAD_DIR}"
# Deal with corrupt downloads or HTML output.
if [[ -s "${DOWNLOAD_PATH}" ]]; then
    if ! unzip -l "${DOWNLOAD_PATH}" > /dev/null; then
        rm -f "${DOWNLOAD_PATH}"
    fi
fi
if [[ ! -s "${DOWNLOAD_PATH}" ]]; then
    echo "Downloading ${DOWNLOAD_URLS[${TYPE}]}"
    if ! curl --fail --location --output "${DOWNLOAD_PATH}" \
            "${DOWNLOAD_URLS[${TYPE}]}" ; then
        rm -f "${DOWNLOAD_PATH}"
        die "Failed to download: ${DOWNLOAD_URLS[${TYPE}]}"
    fi
    if [[ ! -s "${DOWNLOAD_PATH}" ]]; then
        die "Missing or empty file: ${DOWNLOAD_PATH}"
    fi
fi

rm -rf "${NAME}"
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
git add -A .
(unset LESS; git diff --cached --shortstat)
git commit --quiet --message "Installed ${NAME} ${VERSION}"
