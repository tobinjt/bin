function setup() {
  bats_require_minimum_version 1.5.0
  # This is required by bats-assert and bats-file.
  load "${HOME}/src/bats-support/load"
  load "${HOME}/src/bats-assert/load"
  load "${HOME}/src/bats-file/load"

  # wget(1) will be replaced by a mock in $BATS_TEST_TMPDIR.
  PATH="${BATS_TEST_TMPDIR}:${PATH}"
  SKIP_STARTUP_SLEEP="Skip sleep on startup"
  export SKIP_STARTUP_SLEEP
}

function test_success() { # @test
  cat > "${BATS_TEST_TMPDIR}/wget" <<'FAKE_WGET'
#!/bin/bash

cat > wget.log <<WGET
--2019-12-12 22:45:34--  https://www.johntobin.ie/
HTTP request sent, awaiting response... 200 OK
WGET
FAKE_WGET
  chmod 755 "${BATS_TEST_TMPDIR}/wget"

  run check-links "https://www.johntobin.ie/" < /dev/null
  assert_success
  assert_output ""
}

function test_failure() { # @test
  cat > "${BATS_TEST_TMPDIR}/wget" <<'FAKE_WGET'
#!/bin/bash

cat > wget.log <<WGET
--2019-12-12 22:45:34--  https://www.johntobin.ie/unsuccessful
HTTP request sent, awaiting response... 404 Not found
WGET
FAKE_WGET
  chmod 755 "${BATS_TEST_TMPDIR}/wget"

  stderr="prevent shellcheck warning about unassigned variable"
  run --separate-stderr check-links "https://www.johntobin.ie/" < /dev/null
  assert_failure
  local expected
  expected="--2019-12-12 22:45:34--  https://www.johntobin.ie/unsuccessful"
  expected+=" HTTP request sent, awaiting response... 404 Not found"
  assert_output --partial "${expected}"
  assert_equal "${stderr}" ""
}

function test_retries() { # @test
  cat > "${BATS_TEST_TMPDIR}/wget" <<'FAKE_WGET'
#!/bin/bash

cat > wget.log <<WGET
# Unsuccessful request, succeeds on retry
--2019-12-12 22:45:34--  https://www.johntobin.ie/succeed-on-retry
HTTP request sent, awaiting response... 401 Something went wrong
--2019-12-12 22:45:34--  https://www.johntobin.ie/succeed-on-retry
HTTP request sent, awaiting response... 200 OK
WGET
FAKE_WGET
  chmod 755 "${BATS_TEST_TMPDIR}/wget"

  run --separate-stderr check-links "https://www.johntobin.ie/" < /dev/null
  assert_success
  assert_output ""
}

function test_help() { # @test
  cat > "${BATS_TEST_TMPDIR}/wget" <<'FAKE_WGET'
#!/bin/bash

printf "WGET SHOULD NOT BE RUN\n" >&2
exit 1
WGET
FAKE_WGET
  chmod 755 "${BATS_TEST_TMPDIR}/wget"

  run check-links "--help" < /dev/null
  assert_failure
  assert_output --partial "Links outside SOME-WEBSITE will not be checked"
  refute_output --partial "WGET SHOULD NOT BE RUN"
}

function test_sleep() { # @test
  cat > "${BATS_TEST_TMPDIR}/wget" <<'FAKE_WGET'
#!/bin/bash

cat > wget.log <<WGET
--2019-12-12 22:45:34--  https://www.johntobin.ie/
HTTP request sent, awaiting response... 200 OK
WGET
FAKE_WGET
  chmod 755 "${BATS_TEST_TMPDIR}/wget"

  cat > "${BATS_TEST_TMPDIR}/sleep" <<'FAKE_SLEEP'
#!/bin/bash

touch "${BATS_TEST_TMPDIR}/sleep-was-run"
FAKE_SLEEP
  chmod 755 "${BATS_TEST_TMPDIR}/sleep"

  unset SKIP_STARTUP_SLEEP
  run check-links "https://www.johntobin.ie/" < /dev/null
  assert_success
  assert_output ""
  assert_exists "${BATS_TEST_TMPDIR}/sleep-was-run"
}
