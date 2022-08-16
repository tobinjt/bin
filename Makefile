# If make fails with "make: *** No rule to make target ..." then one of the
# input files is missing.

TEST_PROGRAMS = $(wildcard test/*.bats)
TIMESTAMP_FILES = $(patsubst test/%.bats, test/.%.timestamp, $(TEST_PROGRAMS))

.PHONY: all clean coverage tests
all: tests

tests: $(TIMESTAMP_FILES)

clean:
	rm -f $(TIMESTAMP_FILES)

test/.%.timestamp: test/%.bats %
	rm -f $@
	./test/bats/bin/bats ./$<
	touch $@

# TODO: figure out code coverage.
