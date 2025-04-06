# If make fails with "make: *** No rule to make target ..." then one of the
# input files is missing.
#
# To install bats:
# - cd ~/src
# - git clone https://github.com/bats-core/bats-core.git
# - git clone https://github.com/bats-core/bats-assert.git
# - git clone https://github.com/bats-core/bats-file
# - git clone https://github.com/bats-core/bats-support.git

TEST_PROGRAMS = $(wildcard test/*.bats)
TIMESTAMP_FILES = $(patsubst test/%.bats, test/.%.timestamp, $(TEST_PROGRAMS))
KCOVERAGE_DIR = $(HOME)/tmp/generated/kcoverage
BATS = $(HOME)/src/bats-core/bin/bats

.PHONY: all clean coverage tests
all: bats_tests

bats_tests: $(TIMESTAMP_FILES)

clean:
	rm -f $(TIMESTAMP_FILES)
	rm -rf $(KCOVERAGE_DIR)

test/.%.timestamp: test/%.bats %
	rm -f $@
	run-if-exists $(BATS) ./$<
	touch $@

bats_coverage: clean
	KCOVERAGE_DIR=$(KCOVERAGE_DIR) make bats_tests

bats_coverage_2:
	kcov --bash-method=DEBUG --clean --bash-parse-files-in-dir=. $(KCOVERAGE_DIR)2 $(BATS) test
