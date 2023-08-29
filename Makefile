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
KCOVERAGE_DIR = $(HOME)/tmp/kcoverage

.PHONY: all clean coverage tests
all: bats_tests

bats_tests: $(TIMESTAMP_FILES)

clean:
	rm -f $(TIMESTAMP_FILES)

test/.%.timestamp: test/%.bats %
	rm -f $@
	run-if-exists $(HOME)/src/bats-core/bin/bats ./$<
	touch $@

bats_coverage: clean
	rm -rf $(KCOVERAGE_DIR)
	KCOVERAGE_DIR=$(KCOVERAGE_DIR) make bats_tests
