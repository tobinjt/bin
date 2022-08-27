#!/bin/bash

function gather_coverage() {
  if [[ -n "${KCOVERAGE_DIR:-}" ]]; then
    kcov --bash-dont-parse-binary-dir "${KCOVERAGE_DIR}" "$@"
  else
    "$@"
  fi
}
