#!/bin/bash

set -e -f -u -o pipefail

main() {
  cd "${HOME}/bin/python"
  /usr/bin/python3 run_everywhere_test.py
}

main "$@"
