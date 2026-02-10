#!/bin/bash

set -e -f -u -o pipefail

install_venv() {
  local venv_dir="$1" venv_parent
  venv_parent="$(dirname "${venv_dir}")"
  if [[ ! -d "${venv_dir}" ]]; then
    mkdir -p "${venv_parent}"
    cd "${venv_parent}"
    /usr/bin/python3 -m venv "$(basename "${venv_dir}")"
  fi
}

main() {
  local venv_dir="${HOME}/tmp/bin/linkdirs_virtualenv"
  (install_venv "${venv_dir}")
  source "${venv_dir}/bin/activate"
  pip install pyfakefs
  cd "${HOME}/bin/python"
  python3 linkdirs_test.py
}

main "$@"
