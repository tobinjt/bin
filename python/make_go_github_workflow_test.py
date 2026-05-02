import os
import sys
import unittest
from typing import override
from unittest import mock

from pyfakefs import fake_filesystem_unittest

import make_go_github_workflow


class TestMain(fake_filesystem_unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.setUpPyfakefs()
        # Ensure the template files exist in the fake filesystem
        template_dir = os.path.dirname(
            os.path.realpath(make_go_github_workflow.__file__)
        )
        for template in [
            # keep-sorted start
            "dependabot.yml",
            "golang_pre-commit.yml",
            # keep-sorted end
        ]:
            template_path = os.path.join(template_dir, template)
            self.fs.add_real_file(  # pyright: ignore [reportUnknownMemberType]
                template_path
            )

    @mock.patch.object(sys, "argv", ["make_go_github_workflow.py", "mygoapp"])
    def test_main(self) -> None:
        """Tests that the main function correctly writes all files."""
        make_go_github_workflow.main()
        dependabot_file = ".github/dependabot.yml"
        pre_commit_file = ".github/workflows/golang_pre-commit.yml"
        self.assertTrue(os.path.exists(dependabot_file))
        self.assertTrue(os.path.exists(pre_commit_file))

        with open(dependabot_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("mygoapp", content)
            self.assertIn('package-ecosystem: "github-actions"', content)

        with open(pre_commit_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("mygoapp", content)
            self.assertIn("name: Go pre-commit checks.", content)

    @mock.patch.object(
        sys,
        "argv",
        ["make_go_github_workflow.py", "mygoapp", "extra_ignored_arg"],
    )
    def test_main_with_ignored_arg(self) -> None:
        """Tests that an extra argument is ignored and doesn't cause an error."""
        make_go_github_workflow.main()
        dependabot_file = ".github/dependabot.yml"
        self.assertTrue(os.path.exists(dependabot_file))


if __name__ == "__main__":
    unittest.main()
