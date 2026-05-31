#!/bin/bash

set -e -f -u -o pipefail

main() {
  cd "${HOME}/bin/python"
  /usr/bin/python3 retry_tool_test.py
}

main "$@"
