TIMESTAMP_FILES = $(patsubst %_test, .%_timestamp, $(wildcard *_test))

.PHONY: all clean
all: $(TIMESTAMP_FILES)

clean:
	rm -f $(TIMESTAMP_FILES)

# We always depend on %_test and ../%, but only depend on %_test.std{out,err} if
# they exist.  We use secondary expansion so that % gets expanded in one pass,
# then wildcard gets expanded to a single filename if the file exists or no
# filename if it doesn't exist.  This means to changes to any file needed for
# testing will cause tests to be rerun.
.SECONDEXPANSION:
.%_timestamp: %_test ../% $$(wildcard %_test.stdout) $$(wildcard %_test.stderr) \
		$$(wildcard ../%.c)
	./$<
	touch $@

# Disable the built-in rule for compiling C source so that we don't overwrite
# ../full-disk-access
.SUFFIXES:
