function setup() {
  bats_require_minimum_version 1.5.0
  load 'test_helper/bats-support/load' # This is required by bats-assert.
  load 'test_helper/bats-assert/load'
  source 'test/gather_coverage.sh'
  lines=("keep shellcheck happy")
}

function test_argument_handling() { # @test
  run path-parents /etc/passwd
  assert_success
  assert_line "/etc"
  assert_line "/etc/passwd"
  assert_equal "${#lines[@]}" 2

  # Non-existent filename works.
  run path-parents /qwerty/asdf/bar/foo/baz
  assert_success
  assert_line "/qwerty"
  assert_line "/qwerty/asdf"
  assert_line "/qwerty/asdf/bar"
  assert_line "/qwerty/asdf/bar/foo"
  assert_line "/qwerty/asdf/bar/foo/baz"
  assert_equal "${#lines[@]}" 5

  # Help works.
  run path-parents -h
  assert_success
  assert_line --partial "If no filenames are provided reads from stdin."
  assert_line --partial "-h: Show usage message."
  assert_line --partial "-s N: Skip output of paths with N or fewer components"

  # Valid -s.
  run path-parents -s 1 /etc/passwd
  assert_success
  assert_line "/etc/passwd"
  assert_equal "${#lines[@]}" 1

  # Invalid -s.
  run path-parents -s asdf /etc/passwd
  assert_failure
  assert_line "Bad argument 'asdf'; argument to -s must be an integer."
  assert_equal "${#lines[@]}" 1

  # Invalid flag.
  run path-parents -q /etc/passwd
  assert_failure
  assert_line --partial "illegal option -- q"

  # Reading stdin works.
  run path-parents < <(echo /a/b/c)
  assert_success
  assert_line "/a"
  assert_line "/a/b"
  assert_line "/a/b/c"
  assert_equal "${#lines[@]}" 3

  # Reading stdin and skipping.
  run path-parents -s 2 < <(echo /a/b/c)
  assert_success
  assert_line "/a/b/c"
  assert_equal "${#lines[@]}" 1

  run path-parents -s 5 /etc/passwd
  assert_success
  assert_output ""
}

function test_path_variants() { # @test
  # Leading slashes.
  run path-parents /etc/passwd
  assert_success
  assert_line "/etc"
  assert_line "/etc/passwd"
  assert_equal "${#lines[@]}" 2

  run path-parents -s 1 /etc/passwd
  assert_success
  assert_line "/etc/passwd"
  assert_equal "${#lines[@]}" 1

  # No leading slashes.
  run path-parents etc/passwd
  assert_success
  assert_line "etc"
  assert_line "etc/passwd"
  assert_equal "${#lines[@]}" 2

  run path-parents -s 1 etc/passwd
  assert_success
  assert_line "etc/passwd"
  assert_equal "${#lines[@]}" 1

  # Doubled slashes.
  run path-parents etc//passwd
  assert_success
  assert_line "etc"
  assert_line "etc/passwd"
  assert_equal "${#lines[@]}" 2

  run path-parents //etc//passwd
  assert_success
  assert_line "/etc"
  assert_line "/etc/passwd"
  assert_equal "${#lines[@]}" 2
}
