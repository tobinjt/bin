# Project Overview

<!-- markdownlint-disable MD025 -->

This directory (`/Users/johntobin/bin/python`) contains a collection of
standalone Python utility scripts and tools used for various system
administration and personal tasks. These scripts are designed to be run directly
from the command line.

## Key Scripts

- **`linkdirs.py`**: A robust tool for recursively linking files from one or
  more source directories to a destination directory, with options for conflict
  resolution, pattern exclusion, and diff reporting.
- **`cron_to_plist.py`**: A utility to convert standard crontab entries into
  macOS `launchd.plist` files, capturing the current environment's `PATH`.
- **`check_dns_for_hosting.py`**: A script to verify DNS records for various
  hosts, likely used for monitoring hosting configurations.
- **`birthday.py`**: A command-line calculator for the "Birthday Paradox"
  probability.
- **`check_redirects_for_hosting.py`**: (Inferred) A companion tool to the DNS
  checker for validating HTTP redirects.
- **`run_everywhere.py`**: (Inferred) Likely a tool for executing commands
  across multiple contexts or hosts.
- **`retry_tool.py`**: (Inferred) A generic retry logic implementation or
  wrapper.
- **`nines.py`**: (Inferred) Likely a tool for calculating availability
  percentages (nines).

# Building and Running

Since these are Python scripts, there is no build step.

## Running Scripts

Scripts contain a shebang `#!/usr/bin/env python3` and can be executed directly
if marked executable:

```bash
./linkdirs.py --help
./birthday.py
```

Or via the python interpreter:

```bash
python3 cron_to_plist.py [arguments]
```

## Testing

The project uses `pytest` for testing. Each script typically has a corresponding
`_test.py` file (e.g., `linkdirs.py` -> `linkdirs_test.py`).

To run all tests with coverage:

```bash
pytest
```

Configuration is handled in `pytest.ini`, which sets default options (e.g.,
`--cov --cov-report=html`).

# Development Conventions

- **Language:** Python 3 (specifically compatible with 3.14 based on
  `.mypy_cache`).
- **Typing:** Strong typing is used throughout. `mypy` is likely used for static
  analysis (inferred from `.mypy_cache`). Use of `typing` module and built-in
  collection types (PEP 585) is observed.
- **Data Structures:** `dataclasses` are preferred over dictionaries for
  structured data.
- **Documentation:** All modules and functions include docstrings. Module-level
  docstrings provide a high-level summary and usage examples.
- **Formatting:** Code is consistent and clean, likely formatted with `black`.
- **Dependencies:** Standard library is heavily utilized, but some scripts
  import external modules (e.g., `dns` in `check_dns_for_hosting.py`, `pyfakefs`
  in tests).
- **Testing:**
  - Tests are comprehensive and cover edge cases.
  - `unittest.mock` and `pyfakefs` are used for mocking system interactions.
  - Tests are co-located in the same directory with a `_test.py` suffix.
