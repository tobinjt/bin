setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  source 'probe-arianetobin.ie'
  # Make the tests fast by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS
}

function test_success { # @test
  curl() {
    printf "%s\\n" "foo bar baz ${SENTINEL} foo bar baz"
  }
  run main
  assert_success
  assert_output ""
}

function test_failure { # @test
  curl() {
    printf "No sentinel here\\n"
  }
  # Deliberately not local so we get the variable bats sets.
  stderr="prevent shellcheck warning about unassigned variable"
  run --separate-stderr main
  assert_failure
  assert_output ""
  assert_equal "${stderr}" \
    "Did not find sentinel '${SENTINEL}' in https://www.arianetobin.ie/"
}

function test_retries { # @test
  # Use a temp file to save state between invocations.  Because curl is invoked
  # in a subshell any changes we make to variables don't affect the parent
  # shell.
  local tmpfile
  tmpfile="$(mktemp "${TMPDIR:-/tmp}/test_retries-XXXXXXXXXXXX")"
  # I want ${tmpfile} to be expanded now, because when we exit successfully it
  # will be out of scope and cannot be expanded.
  # shellcheck disable=SC2064
  trap "rm -f \"${tmpfile}\"" EXIT
  cat > "${tmpfile}" <<INPUT
No sentinel here
No sentinel here
foo bar baz ${SENTINEL} foo bar baz
INPUT
  curl() {
    # Print the first line.
    sed -n -e '1p' "${tmpfile}"
    # Delete the first line.
    sed -i '' -e '1d' "${tmpfile}"
  }
  run main
  assert_success
  assert_output ""
}
