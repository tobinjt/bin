function setup() {
  bats_require_minimum_version 1.5.0
  load "${HOME}/src/bats-support/load" # This is required by bats-assert.
  load "${HOME}/src/bats-assert/load"

  # Speed up tests by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS

  # host(1) will be replaced by a mock in $BATS_TEST_TMPDIR.
  PATH="${BATS_TEST_TMPDIR}:${PATH}"
}

function test_success() { # @test
  # Set up fake host records.
  local host_records
  host_records="${BATS_TEST_TMPDIR}/host_records"
  cat > "${BATS_TEST_TMPDIR}/host" <<HOST
#!/bin/bash

grep "^\$3 " "${host_records}"
HOST
  chmod 755 "${BATS_TEST_TMPDIR}/host"
  cat > "${host_records}" <<HOST_RECORDS
# domain1.ie will succeed.
domain1.ie has address 168.119.99.114
domain1.ie has IPv6 address 2a01:4f8:c010:21a::1
www.domain1.ie has address 168.119.99.114
www.domain1.ie has IPv6 address 2a01:4f8:c010:21a::1
domain1.ie mail is handled by 1 aspmx.l.google.com.
domain1.ie mail is handled by 10 aspmx2.googlemail.com.
domain1.ie mail is handled by 10 aspmx3.googlemail.com.
domain1.ie mail is handled by 5 alt1.aspmx.l.google.com.
domain1.ie mail is handled by 5 alt2.aspmx.l.google.com.

# dev.domain2.ie will succeed, without subdomains being checked.
dev.domain2.ie has address 168.119.99.114
dev.domain2.ie has IPv6 address 2a01:4f8:c010:21a::1
HOST_RECORDS

  local check_me
  for check_me in "domain1.ie" "dev.domain2.ie"; do
    run check-dns-for-hosting "${check_me}"
    assert_success
    assert_output ""
  done
}

function test_failure() { # @test
  # Why does this work but a symlink from host to /bin/true fails?
  cat > "${BATS_TEST_TMPDIR}/host" <<HOST
#!/bin/bash

true
HOST
  chmod 755 "${BATS_TEST_TMPDIR}/host"
  run check-dns-for-hosting "domain3.ie"
  assert_failure
  local expected_lines line
  expected_lines=(
    "Bad A address: pattern 'has address 168.119.99.114$' not found"
    "Bad AAAA address: pattern 'has IPv6 address 2a01:4f8:c010:21a::1$' not found"
    "Bad A address: pattern 'has address 168.119.99.114$' not found"
    "Bad AAAA address: pattern 'has IPv6 address 2a01:4f8:c010:21a::1$' not found"
    "Bad MX address: pattern '^domain3.ie mail is handled by 1 aspmx.l.google.com.$' not found"
    "Bad MX address: pattern '^domain3.ie mail is handled by 10 aspmx2.googlemail.com.$' not found"
    "Bad MX address: pattern '^domain3.ie mail is handled by 10 aspmx3.googlemail.com.$' not found"
    "Bad MX address: pattern '^domain3.ie mail is handled by 5 alt1.aspmx.l.google.com.$' not found"
    "Bad MX address: pattern '^domain3.ie mail is handled by 5 alt2.aspmx.l.google.com.$' not found"
  )
  for line in "${expected_lines[@]}"; do
    assert_output --partial "${line}"
  done
}

function test_retries() { # @test
  # Set up fake host records.
  # Each run of host() will output and delete the first input file it finds.  We
  # retry the A record check 3 times and the AAAA record check twice.
  printf "no A records found 1\\n" > "${BATS_TEST_TMPDIR}/1"
  printf "no A records found 2\\n" > "${BATS_TEST_TMPDIR}/2"
  printf "sub.domain4.ie has address 168.119.99.114\\n" > "${BATS_TEST_TMPDIR}/3"
  printf "no AAAA records found 1\\n" > "${BATS_TEST_TMPDIR}/4"
  printf "sub.domain4.ie has IPv6 address 2a01:4f8:c010:21a::1\\n" \
    > "${BATS_TEST_TMPDIR}/5"

  cat > "${BATS_TEST_TMPDIR}/host" <<'HOST'
#!/bin/bash

for i in $(seq 1 5); do
  filename="${BATS_TEST_TMPDIR}/${i}"
  if [[ -f "${filename}" ]]; then
    cat "${filename}"
    rm "${filename}"
    exit 0
  fi
done
printf "# ERROR: host ran out of files to check\\n" >&3
exit 1
HOST
  chmod 755 "${BATS_TEST_TMPDIR}/host"

  run check-dns-for-hosting "sub.domain4.ie"
  assert_success
  assert_output ""
}
