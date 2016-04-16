#!/bin/bash

set -e -f -u -o pipefail

warn() {
    echo -e "$@" 1>&2
}
die() {
    warn "$@"
    exit 1
}
usage() {
    warn "Usage: $0 WORDPRESS-DIRECTORY wordpress VERSION"
    die "Usage: $0 WORDPRESS-DIRECTORY theme[s]|plugin[s] NAME [VERSION]"
}

if [[ "$#" -ne 4 && "$#" -ne 3 ]]; then
      usage
fi
if [[ "$#" -eq 3 ]]; then
    if [[ "$2" == "wordpress" ]]; then
        set -- "$1" "wordpress" "wordpress" "$3"
    else
        # Make $4 empty but defined because of -u.
        set -- "$1" "$2" "$3" ""
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
if [[ -n "${VERSION}" ]]; then
    SEPARATORS[plugin]="."
    SEPARATORS[theme]="."
else
    SEPARATORS[plugin]=""
    SEPARATORS[theme]=""
fi
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
declare -A BROWSER_URLS
BROWSER_URLS[wordpress]="https://wordpress.org/download"
BROWSER_URLS[plugin]="https://wordpress.org/plugins/${NAME}/"
BROWSER_URLS[theme]="https://wordpress.org/themes/${NAME}/"
readonly BROWSER_URLS
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
        warn "Failed to download: ${DOWNLOAD_URLS[${TYPE}]}"
        if [[ -n "${VERSION}" && "${TYPE}" != "wordpress" ]]; then
            warn "Trying again without explicit version"
            exec "$0" "${WORDPRESS_BASE}" "${TYPE}" "${NAME}" ""
        else
            die "Visit ${BROWSER_URLS[${TYPE}]}"
        fi
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
fi
git add -A .
(unset LESS; git diff --cached --shortstat)
git commit --quiet --message "Installed ${NAME} ${VERSION}"
