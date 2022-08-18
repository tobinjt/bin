setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  source 'check-links'
}

test_success() { # @test
  wget() {
    cat > wget.log <<WGET
--2019-12-12 22:45:34--  https://www.johntobin.ie/
HTTP request sent, awaiting response... 200 OK
WGET
  }
  run main "https://www.johntobin.ie/" < /dev/null
  assert_success
  assert_output ""
}

test_failure() { # @test
  wget() {
    cat > wget.log <<WGET
--2019-12-12 22:45:34--  https://www.johntobin.ie/unsuccessful
HTTP request sent, awaiting response... 404 Not found
WGET
  }
  stderr="prevent shellcheck warning about unassigned variable"
  run --separate-stderr main "https://www.johntobin.ie/" < /dev/null
  assert_failure
  local expected
  expected="--2019-12-12 22:45:34--  https://www.johntobin.ie/unsuccessful"
  expected+=" HTTP request sent, awaiting response... 404 Not found"
  assert_output --partial "${expected}"
  assert_equal "${stderr}" ""
}

test_retries() { # @test
  wget() {
    cat > wget.log <<WGET
# Unsuccessful request, succeeds on retry
--2019-12-12 22:45:34--  https://www.johntobin.ie/succeed-on-retry
HTTP request sent, awaiting response... 401 Something went wrong
--2019-12-12 22:45:34--  https://www.johntobin.ie/succeed-on-retry
HTTP request sent, awaiting response... 200 OK
WGET
  }
  run --separate-stderr main "https://www.johntobin.ie/" < /dev/null
  assert_success
  assert_output ""
}
