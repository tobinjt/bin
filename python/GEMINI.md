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

**`pytest`** is the preferred way to run tests; *do not* run tests using
`python3 FILENAME`.

To run all tests with coverage:

```bash
pytest
```

To run a single test with coverage:

```bash
pytest FILENAME
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

# Python Coding Instructions

## Import Modules, Not Classes or Functions

When writing Python code, you **must** import entire modules or submodules
rather than specific classes or functions from within those modules.

______________________________________________________________________

### Example

Here is a clear illustration of the correct and incorrect approach.

#### ✅ Correct Usage: `import my_app.database`

This is the preferred method. Import the module, then access its contents via
the module's namespace.

```python
# In main.py
import my_app.database
import my_app.utils

def initialize_app():
    db_conn = my_app.database.DatabaseConnection()
    data = my_app.utils.load_initial_data()
    # ... more code
```

______________________________________________________________________

#### ❌ Incorrect Usage: from my_app.database import DatabaseConnection

Avoid this method, as it can pollute the namespace and obscure the origin of
classes and functions.

```python
# In main.py
from my_app.database import DatabaseConnection
from my_app.utils import load_initial_data

def initialize_app():
    # It's less clear where DatabaseConnection comes from without looking at the
    # imports.
    db_conn = DatabaseConnection()
    data = load_initial_data()
    # ... more code
```

______________________________________________________________________

#### ✅ Correct Usage: importing a sub-module: from unitest import mock

This is preferred because 1) it's importing a sub-module rather than a class or
function, 2) the shorter import paths are easier to read, and 3) if we ever
import the module from somewhere else only the import line needs to change, not
every reference.

```python
import sys
import unittest
from unittest import mock

class TestMain(unittest.TestCase):
    @mock.patch.object(sys, "exit")
    def test_success(self, mock_sys_exit: mock.Mock) -> None:
        ...
```

## Docstrings are required

When you write or modify Python code, you must ensure that every function,
method, or generator that is not part of a test suite has a docstring. This
docstring must, at a minimum, document the function's arguments, return values,
and any exceptions that may be raised by the function.

This rule applies to all non-test functions, regardless of their visibility
(public or private).

______________________________________________________________________

### Example: Correct

This function has a docstring that clearly explains what the function does and
what its arguments are.

```python
def connect_to_database(hostname: str, port: int) -> Connection:
    """Establishes a connection to the database.

    Args:
        hostname: The hostname or IP address of the database server.
        port: The port number to connect to.

    Returns:
        A database connection object.
    """
    # ... implementation ...
```

______________________________________________________________________

### Example: Incorrect (Missing Docstring)

This function is missing a docstring entirely.

```python
def connect_to_database(hostname: str, port: int) -> Connection:
    # ... implementation ...
```

______________________________________________________________________

### Example: Incorrect (Incomplete Docstring)

This docstring is incomplete because it does not document the function's
arguments.

```python
def connect_to_database(hostname: str, port: int) -> Connection:
    """Establishes a connection to the database."""
    # ... implementation ...
```

## Use dataclasses rather than dicts

When you are writing Python code, you **must** use `dataclasses` to represent
structured data. You **must not** use dictionaries (`dict`) for this purpose.

Using `dataclasses` provides type safety and makes code easier to read and
maintain.

______________________________________________________________________

### Example: Correct

This example correctly uses a `dataclass` to represent a user, making the code's
intent clear and type-safe.

```python
from dataclasses import dataclass

@dataclass
class User:
    id: int
    username: str
    is_active: bool

def fetch_user(user_id: int) -> User | None:
    # In a real scenario, this would fetch from a database.
    if user_id == 1:
        return User(id=1, username="testuser", is_active=True)
    return None
```

______________________________________________________________________

### Example: Incorrect

This example is incorrect because it uses a dictionary to represent the user.
This approach is less clear and lacks the type safety provided by `dataclasses`.

```python
# Incorrect: Do not use dictionaries for structured data in code.

def fetch_user_dict(user_id: int) -> dict | None:
    if user_id == 1:
        return {"id": 1, "username": "testuser", "is_active": True}
    return None
```

______________________________________________________________________

## Python Typing Conventions

You are instructed to follow modern Python type hinting standards (PEP 585 and
PEP 604) for all code generation and refactoring tasks.

### 1. Built-in Collections (PEP 585)

When writing type signatures, you must use built-in collection types instead of
their counterparts from the `typing` module.

Deprecated / Old Style | Required Modern Style :----------------------- |
:-------------------- `typing.List` / `List` | `list` `typing.Dict` / `Dict` |
`dict` `typing.Tuple` / `Tuple` | `tuple` `typing.Set` / `Set` | `set`

### 2. Union and Optional Types (PEP 604)

Use the bitwise OR operator (`|`) for unions and optional types. Do not import
`Union` or `Optional` from the `typing` module.

Old Style | Required Modern Style :---------------- | :--------------------
`Union[int, str]` | `int | str` `Optional[str]` | `str | None`

### Code Examples

**Incorrect:**

```python
from typing import List, Dict, Union, Optional

def get_user(id: Union[int, str]) -> Optional[Dict[str, str]]: ...
    ...
```

**Correct:**

```python
def get_user(id: int | str) -> dict[str, str] | None:
    ...
```

### Context

Standardize on Python 3.10+ syntax. *Do not ever* use `typing` module imports
for these features.

## Use `foo | None` for optional types

When you write or modify Python code, you must use the `| None` syntax for
optional types, as specified in PEP 604. You must not use `typing.Optional`.

This rule applies to all Python code you generate, including function
signatures, variable annotations, and class attributes.

______________________________________________________________________

### Example

**Correct (Do this):**

```python
def find_user(username: str) -> dict | None:
    # ... implementation ...
    return None
```

______________________________________________________________________

**Incorrect (Don't do this):**

```python
from typing import Optional

def find_user(username: str) -> Optional[dict]:
    # ... implementation ...
    return None
```

## Use a subclass of `argparse.Namespace` when processing command line arguments

By default, the fields in the object returned by `argparse` aren't typed,
causing problems for type checking. The solution is to use a subclass of
`argparse.Namespace` when parsing command line arguments. This enables type
checkers to correctly check types, and enables IDEs to perform completion.

**Implementation**:

- Define a subclass of `argparse.Namespace` named `Args`.

- The `__init__` method:

  - Must have a typed parameter for each command line argument.

  - The default value for each non-mutable parameter (`int`, `bool`, `str`, ...)
    must be the default value for the command line argument.

  - Mutable types (e.g. `list`, `dict`) must be typed as `list | None = None`,
    because `list = []` is dangerous - the default is shared across instances.

  - Each field must be assigned the corresponding parameter.

    - Where a parameter is `None` the default value of the command line option
      must be substituted, using:

      ```python
      self.foo = list(foo) if foo is not None else []
      ```

      `list(foo)` is used rather than simply `foo` so that the list isn't shared
      between the new instance and the creator of the new instance.

- When parsing command line arguments use a new instance of the `Args` class:

  ```python
  parser = argparse.ArgumentParser(...)
  _ = parser.add_argument(...)
  ...
  args = parser.parse_args(namespace=Args())
  ```

## Tests must use the `unittest` framework

When you are asked to write Python test code, you **must** use the built-in
`unittest` framework. Your tests should be written as methods within a class
that inherits from `unittest.TestCase`.

You **must** use the assertion methods provided by `unittest.TestCase` (e.g.,
`self.assertEqual()`, `self.assertTrue()`, `self.assertRaises()`) to check for
expected outcomes. Do not use the standard `assert` statement for test
assertions.

______________________________________________________________________

### Example: Correct

This example correctly uses the `unittest` module and the `self.assertEqual()`
assertion method.

```python
import unittest

def add(a, b):
    return a + b

class TestMathFunctions(unittest.TestCase):

    def test_add_integers(self):
        """
        Tests that the add function correctly sums two integers.
        """
        self.assertEqual(add(1, 2), 3)

    def test_add_strings(self):
        """
        Tests that the add function correctly concatenates two strings.
        """
        self.assertEqual(add('a', 'b'), 'ab')

if __name__ == '__main__':
    unittest.main()
```

______________________________________________________________________

### Example: Incorrect

This example is incorrect because it uses a plain `assert` statement instead of
a `unittest` assertion method. While this might work with other test runners
like `pytest`, your instructions are to use the `unittest` style exclusively.

```python
# Incorrect: Do not use plain assert statements.
import unittest

def add(a, b):
    return a + b

class TestMathFunctions(unittest.TestCase):

    def test_add_integers(self):
        assert add(1, 2) == 3
```

## Use `mock.patch.object` for Mocking

When writing Python code, especially for unit tests that use the `unittest.mock`
library, you **must** use `mock.patch.object` instead of `mock.patch`.

______________________________________________________________________

### Example

Here is a clear illustration of the correct and incorrect approach.

#### ✅ Correct Usage: `mock.patch.object`

This is the preferred method. You import the module and then patch the function
directly on that module object.

```python
from unittest import mock
import my_project.services

def test_some_feature():
    # Patches 'external_api_call' directly on the imported 'services' object.
    with mock.patch.object(my_project.services, 'external_api_call') as mock_api_call:
        my_project.services.run_feature()
        mock_api_call.assert_called_once()
```

______________________________________________________________________

#### ❌ Incorrect Usage: mock.patch

Avoid this method. It relies on a string path that can easily be incorrect or
become outdated.

```python
from unittest import mock
import my_project.services

def test_some_feature():
    # This string path is fragile and less clear.
    with mock.patch('my_project.services.external_api_call') as mock_api_call:
        my_project.services.run_feature()
        mock_api_call.assert_called_once()
```

## Use `mock.create_autospec` for Mocks

When writing Python unit tests, you **must** use `mock.create_autospec` to
create mock objects. Do **not** use `mock.MagicMock` or `mock.Mock` directly.

______________________________________________________________________

### Example

Consider a simple class we want to test against.

```python
# in my_project/services.py
class ApiClient:
    def get_user_data(self, user_id: int) -> dict:
        # ... logic to call an external API
        return {"id": user_id, "name": "Jane Doe"}
```

______________________________________________________________________

#### ✅ Correct Usage: mock.create_autospec

This test will fail if you try to call get_user_data with the wrong number of
arguments, protecting you from API changes.

```python
from unittest import mock
from my_project.services import ApiClient

def test_user_retrieval():
    # Create a spec'd mock from the ApiClient class
    mock_client = mock.create_autospec(ApiClient, instance=True)

    # This call matches the real method signature
    mock_client.get_user_data(user_id=123)

    # If you tried mock_client.get_user_data(), it would raise a TypeError,
    # which is correct!
    # If you tried mock_client.get_nonexistent_method(), it would raise an
    # AttributeError.

    mock_client.get_user_data.assert_called_once_with(user_id=123)
```

______________________________________________________________________

#### ❌ Incorrect Usage: mock.MagicMock

This test is brittle. It would still pass even if the signature of get_user_data
changed or if you misspelled a method name.

```python
from unittest import mock

def test_user_retrieval_brittle():
    # A generic mock has no knowledge of the real ApiClient's interface
    mock_client = mock.MagicMock()

    # This call will *not* be validated against the real method signature.
    # The mock will happily accept any arguments.
    mock_client.get_user_data("wrong", "arguments")

    # This would also work, creating a new magic mock on the fly, hiding a
    # potential typo. mock_client.get_usr_data()

    mock_client.get_user_data.assert_called_once_with("wrong", "arguments")
```

## Lint all Python code with `ruff` and `basedpyright`

When you are asked to write, modify, or generate Python code, you must always
lint your final code output using the `ruff` and `basedpyright` command-line
tools.

- **Trigger**: Any request that results in Python code as the primary output.
- **Action**: Run `ruff` and `basedpyright` on the generated Python code, and
  fix any errors reported.
  - Your goal is to ensure the codebase is clean, type-hinted, and free of
    logical inconsistencies by resolving issues raised by the linters.
  - Ensure fixes follow Python best practices (PEP 8) and maintain the original
    logic of the code.
- **Command**: Assume `ruff` and `basedpyright` are installed in the user's
  `PATH`. Use `ruff check FILENAME(s)` and `basedpyright FILENAME(s)` where
  `FILENAME(s)` are the names of the Python files you have written.
- **Error Resolution Strategy**:
  - *Type Mismatches*: Add or correct type annotations, including return type
    annotations. Use typing.Any only as a last resort.
  - *Unused Imports/Variables*: Remove them unless they are required for side
    effects; if they are required for side effects the import must be annotated
    with a reason.
  - *None-Safety*: Minimise use of `None`. Add explicit `if x is not None:`
    checks to eliminate `None` values quickly.
- **Verification Loop**: After applying a set of fixes:
  1. Re-run both tools.
  1. If new errors appear (or old ones persist), iterate on the fix.
  1. Stop only when both tools report 0 errors and 0 warnings, or when further
     changes would break the code's functionality.
  1. Run `black` as described elsewhere to format the code and re-run both
     tools.
- **Constraints**:
  - *Do not* suppress errors or warnings if there is a viable way to fix them.
  - *Do not* change the runtime behavior of the code unless the error identifies
    a clear bug.
  - *Maintain Style*: Match the existing indentation and naming conventions of
    the file.

## Format all Python code with `black`

When you are asked to write, modify, or generate Python code, you must always
reformat your final code output using the `black` command-line tool.

- **Trigger**: Any request that results in Python code as the primary output.
- **Action**: Pipe the generated Python code to the `black` formatter.
- **Command**: Assume `black` is installed in the user's `PATH`. Use `black -`
  to read the code from standard input.
- **Output**: Your final response should only contain the `black`-formatted
  code. Do not show the code before formatting.
- **Verification Loop**: After applying a set of fixes:
