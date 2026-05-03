import os
import sys
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import make_python_github_workflow


class TestMain(fake_filesystem_unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Ensure the template files exist in the fake filesystem
        template_dir = os.path.dirname(
            os.path.realpath(make_python_github_workflow.__file__)
        )
        for template in [
            # keep-sorted start
            "dependabot.yml",
            "dependabot_validation.yml",
            # keep-sorted end
        ]:
            template_path = os.path.join(template_dir, template)
            self.fs.add_real_file(  # pyright: ignore [reportUnknownMemberType]
                template_path
            )

    @mock.patch.object(sys, "argv", ["make_python_github_workflow.py", "mypyapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly writes all files."""
        make_python_github_workflow.main()
        dependabot_file = ".github/dependabot.yml"
        dependabot_validation_file = ".github/workflows/dependabot_validation.yml"
        self.assertTrue(os.path.exists(dependabot_file))
        self.assertTrue(os.path.exists(dependabot_validation_file))

        with open(dependabot_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("mypyapp", content)
            self.assertIn('package-ecosystem: "github-actions"', content)

        with open(dependabot_validation_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("mypyapp", content)
            self.assertIn("name: Validate Dependabot Config", content)

    @mock.patch.object(
        sys,
        "argv",
        ["make_python_github_workflow.py", "mypyapp", "extra_ignored_arg"],
    )
    def test_main_with_ignored_arg(self) -> None:
        """Tests that an extra argument is ignored and doesn't cause an error."""
        make_python_github_workflow.main()
        dependabot_file = ".github/dependabot.yml"
        self.assertTrue(os.path.exists(dependabot_file))


if __name__ == "__main__":
    unittest.main()
