TEST_PROGRAMS = $(wildcard *_test)
TIMESTAMP_FILES = $(patsubst %_test, .%_timestamp, $(TEST_PROGRAMS))
KCOVERAGE_DIR = $(HOME)/tmp/kcoverage

.PHONY: all clean coverage tests
all: tests

tests: $(TIMESTAMP_FILES)

clean:
	rm -f $(TIMESTAMP_FILES)

coverage: tests
	rm -rf $(KCOVERAGE_DIR)
	for test_program in $(TEST_PROGRAMS); do \
		kcov --bash-method=DEBUG --limits=80,90 \
			--exclude-pattern="$${HOME}/bin/tests" \
			$(KCOVERAGE_DIR) "./$${test_program}"; \
	done

# We always depend on %_test and ../%, but only depend on %_test.std{out,err} if
# they exist.  We use secondary expansion so that % gets expanded in one pass,
# then wildcard gets expanded to a single filename if the file exists or no
# filename if it doesn't exist.  This means to changes to any file needed for
# testing will cause tests to be rerun.
.SECONDEXPANSION:
.%_timestamp: %_test ../% $$(wildcard %_test.stdout) $$(wildcard %_test.stderr)
	rm -f $@
	./$<
	test -f $@
