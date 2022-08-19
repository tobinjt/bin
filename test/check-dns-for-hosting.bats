setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  source 'check-dns-for-hosting'

  # Speed up tests by not sleeping.
  SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS=0
  export SECONDS_TO_SLEEP_BETWEEN_ATTEMPTS
}

test_success() { # @test
  # Set up fake host records.
  local host_records
  host_records="$(mktemp "${TMPDIR:-/tmp}/host_records.XXXXXXXXXXXXXXXXX")"
  # I want ${host_records} to be expanded now, because when we exit successfully
  # it will be out of scope and cannot be expanded.
  # shellcheck disable=SC2064
  trap "rm -f \"${host_records}\"" EXIT
  host() {
    local domain="$3"
    grep "^${domain} " "${host_records}"
  }
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
    run main "${check_me}"
    assert_success
    assert_output ""
  done
}

test_failure() { # @test
  host() {
    true
  }
  run main "domain3.ie"
  assert_failure
  local expected_lines line
  expected_lines=(
    "Bad A address: pattern '^domain3.ie has address 168.119.99.114$' not found"
    "Bad AAAA address: pattern '^domain3.ie has IPv6 address 2a01:4f8:c010:21a::1$' not found"
    "Bad A address: pattern '^www.domain3.ie has address 168.119.99.114$' not found"
    "Bad AAAA address: pattern '^www.domain3.ie has IPv6 address 2a01:4f8:c010:21a::1$' not found"
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

test_retries() { # @test
  # Set up fake host records.
  local temp_dir
  temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/host_records.XXXXXXXXXXXXXXXXX")"
  # I want ${temp_dir} to be expanded now, because when we exit successfully it
  # will be out of scope and cannot be expanded.
  # shellcheck disable=SC2064
  trap "rm -r -f \"${temp_dir}\"" EXIT

  # Each run of host() will output and delete the first input file it finds.  We
  # retry the A record check 3 times and the AAAA record check twice.
  printf "no A records found 1\\n" > "${temp_dir}/1"
  printf "no A records found 2\\n" > "${temp_dir}/2"
  printf "sub.domain4.ie has address 168.119.99.114\\n" > "${temp_dir}/3"
  printf "no AAAA records found 1\\n" > "${temp_dir}/4"
  printf "sub.domain4.ie has IPv6 address 2a01:4f8:c010:21a::1\\n" \
    > "${temp_dir}/5"

  host() {
    local i
    for i in $(seq 1 5); do
      local filename="${temp_dir}/${i}"
      if [[ -f "${filename}" ]]; then
        cat "${filename}"
        rm "${filename}"
        return
      fi
    done
    printf "# ERROR: host ran out of files to check\\n" >&3
    return 1
  }

  run main "sub.domain4.ie"
  assert_success
  assert_output ""
}
