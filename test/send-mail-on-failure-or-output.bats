function setup() {
  bats_require_minimum_version 1.5.0
  load "${HOME}/src/bats-support/load" # This is required by bats-assert.
  load "${HOME}/src/bats-assert/load"

  # Ensure consistent subject line.
  SUBJECT_PREFIX="test@testing"
  export SUBJECT_PREFIX

  # mail(1) will be replaced by a mock in $BATS_TEST_TMPDIR.
  PATH="${BATS_TEST_TMPDIR}:${PATH}"
  cat > "${BATS_TEST_TMPDIR}/mail" <<'FAKE_MAIL'
#!/bin/bash

i=0
for arg in "$@"; do
  echo "arg ${i}: \"${arg}\""
  ((++i))
done
echo "stdin:"
cat
FAKE_MAIL
  chmod 755 "${BATS_TEST_TMPDIR}/mail"
}

function test_mail_should_not_be_sent() { # @test
  # If mail is run the arguments will be output and cause test failure.
  run send-mail-on-failure-or-output success@no-output true
  assert_success
  assert_output ""

  run send-mail-on-failure-or-output --ignore_exit_status \
    failure@no-output false
  assert_failure
  assert_output ""

  run send-mail-on-failure-or-output --only_on_failure \
    success@output echo this-output-is-ignored
  assert_success
  assert_output ""
}

function test_mail_should_be_sent() { # @test
  # Ensure mail is run by checking the output.
  run send-mail-on-failure-or-output failure@no-output false
  assert_failure
  assert_line --partial "test@testing: false"
  assert_line --partial "failure@no-output"

  run send-mail-on-failure-or-output success@output echo foo
  assert_success
  assert_line --partial "test@testing: echo foo"
  assert_line --partial "success@output"
  assert_line --partial "foo"

  run send-mail-on-failure-or-output --ignore_exit_status \
    ignored@output echo bar
  assert_success
  assert_line --partial "bar"

  run send-mail-on-failure-or-output failure@stderr-output ls /non-existent
  assert_failure
  assert_line --partial "No such file or directory"

  run send-mail-on-failure-or-output --only_on_failure \
    failure@stderr-output ls /non-existent
  assert_failure
  assert_line --partial "No such file or directory"

  cat > "${BATS_TEST_TMPDIR}/output-to-stderr" <<'OUTPUT_TO_STDERR'
#!/bin/bash

echo "this goes to stderr" >&2
OUTPUT_TO_STDERR
  chmod 755 "${BATS_TEST_TMPDIR}/output-to-stderr"
  run send-mail-on-failure-or-output success@stderr-output output-to-stderr
  assert_success
  assert_line --partial "this goes to stderr"
}

function test_argument_handling() { # @test
  run send-mail-on-failure-or-output --ignore_exit_status --only_on_failure \
    incompatible-arguments@mail echo this-should-not-be-output
  assert_failure
  assert_line "Cannot use both --ignore_exit_status and --only_on_failure"
  refute_line this-should-not-be-output

  run send-mail-on-failure-or-output --help
  assert_success
  assert_line --partial "[OPTIONS] EMAIL_ADDRESS command args"
  assert_line "OPTIONS: --ignore_exit_status, --only_on_failure"
  assert_line "Cannot use --ignore_exit_status and --only_on_failure together"

  run send-mail-on-failure-or-output --bad-flag
  assert_failure
  assert_line "Unrecognised option: --bad-flag"

  run send-mail-on-failure-or-output
  assert_failure
  assert_line "No email address given!"

  run send-mail-on-failure-or-output no-comand-given@mail
  assert_failure
  assert_line "No command to run!"
}
