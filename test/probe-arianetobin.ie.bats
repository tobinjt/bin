#!/bin/bash

set -e -f -u -o pipefail

setup() {
  load 'test_helper/bats-support/load' # this is required by bats-assert!
  load 'test_helper/bats-assert/load'
  source 'probe-arianetobin.ie'
  # Make the tests fast by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS
}

function test_success { # @test
  curl() {
    printf "%s\\n" "${SENTINEL}"
  }
  main
}

function test_failure { # @test
  curl() {
    printf "No sentinel here\\n"
    printf "curl was invoked for test 2\\n" >&2
  }
  run main
  assert_failure
}

# TODO: write a test where the first attempt fails and the second succeeds,
# like in check-dns-for-hosting_test.  I've tried to do this without success,
# because curl() is not redefined like host is, and I don't understand why :(
