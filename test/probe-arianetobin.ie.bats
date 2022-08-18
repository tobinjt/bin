#!/bin/bash

set -e -f -u -o pipefail

setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  source 'probe-arianetobin.ie'
  # Make the tests fast by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS
  output="prevent shellcheck warning about unassigned variable"
  stderr="${output}"
}

function test_success { # @test
  curl() {
    printf "%s\\n" "foo bar baz ${SENTINEL} foo bar baz"
  }
  run --separate-stderr main
  assert_success
  assert_equal "${output}" ""
  assert_equal "${stderr}" ""
}

function test_failure { # @test
  curl() {
    printf "No sentinel here\\n"
  }
  run --separate-stderr main
  assert_failure
  assert_equal "${output}" ""
  assert_equal "${stderr}" \
    "Did not find sentinel '${SENTINEL}' in https://www.arianetobin.ie/"
}

# TODO: write a test where the first attempt fails and the second succeeds,
# like in check-dns-for-hosting_test.  I've tried to do this without success,
# because curl() is not redefined like host is, and I don't understand why :(
