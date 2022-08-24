function setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  # curl(1) will be replaced by a mock in $BATS_TEST_TMPDIR.
  PATH="${BATS_TEST_TMPDIR}:${PATH}"
  # Make the tests fast by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS
  SENTINEL='<title>Ariane Tobin Jewellery - Ariane Tobin Jewellery</title>'
}

function test_success() { # @test
  cat > "${BATS_TEST_TMPDIR}/curl" <<FAKE_CURL
#!/bin/bash

printf "%s\\n" "foo bar baz ${SENTINEL} foo bar baz"
FAKE_CURL
  chmod 755 "${BATS_TEST_TMPDIR}/curl"

  run probe-arianetobin.ie
  assert_success
  assert_output ""
}

function test_failure() { # @test
  cat > "${BATS_TEST_TMPDIR}/curl" <<FAKE_CURL
#!/bin/bash

printf "No sentinel here\\n"
FAKE_CURL
  chmod 755 "${BATS_TEST_TMPDIR}/curl"

  # Deliberately not local so we get the variable bats sets.
  stderr="prevent shellcheck warning about unassigned variable"
  run --separate-stderr probe-arianetobin.ie
  assert_failure
  assert_output ""
  assert_equal "${stderr}" \
    "Did not find sentinel '${SENTINEL}' in https://www.arianetobin.ie/"
}

function test_retries() { # @test
  # Use a temp file to save state between invocations.  Because curl is invoked
  # in a subshell any changes we make to variables don't affect the parent
  # shell.
  local tmpfile
  tmpfile="${BATS_TEST_TMPDIR}/fake-curl-output"
  cat > "${tmpfile}" <<INPUT
No sentinel here
No sentinel here
foo bar baz ${SENTINEL} foo bar baz
INPUT

  cat > "${BATS_TEST_TMPDIR}/curl" <<FAKE_CURL
#!/bin/bash

# Print the first line.
sed -n -e '1p' "${tmpfile}"
# Delete the first line.
sed -i '' -e '1d' "${tmpfile}"
FAKE_CURL
  chmod 755 "${BATS_TEST_TMPDIR}/curl"

  run probe-arianetobin.ie
  assert_success
  assert_output ""
}
