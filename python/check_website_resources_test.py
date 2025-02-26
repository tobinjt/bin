"""Tests for check_website_resources."""

import io
import logging
import pydantic
import subprocess
import textwrap
import unittest
from unittest import mock

import pyfakefs

import check_website_resources


def split_inline_string(*, string: str) -> list[str]:
    """Split a multi-line inline string, stripping empty start and end lines."""
    return textwrap.dedent(string).strip().split("\n")


class TestReadWgetLog(unittest.TestCase):
    """Tests for read_wget_log."""

    def test_simple(self):
        """A very simple test."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            patcher.fs.create_file(
                check_website_resources.WGET_LOG, contents="asdf\n1234\n"
            )
            actual = check_website_resources.read_wget_log()
            self.assertEqual(["asdf", "1234"], actual)


class TestWriteCookiesFile(unittest.TestCase):
    """Tests for write_cookies_file."""

    def test_simple(self):
        """A very simple test."""
        with pyfakefs.fake_filesystem_unittest.Patcher():
            lines = ["asdf", "1234"]
            check_website_resources.write_cookies_file(lines=lines)
            with open(
                check_website_resources.COOKIES_FILE, encoding="utf8"
            ) as filehandle:
                self.assertEqual("asdf\n1234\n", filehandle.read())


class TestReadConfig(unittest.TestCase):
    """Tests for read_config."""

    def test_configs_are_immutable(self):
        """Configs should be immutable so I don't accidentally alter them.

        Note that this only affects top-level fields, the contents of dicts and
        lists can still be changed.
        """
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["https://www.example.com/", "resource 1"],
            cookies={},
            comment="https://www.example.com/",
        )
        with self.assertRaisesRegex(pydantic.ValidationError, "Instance is frozen"):
            config.url = "overwritten"

    def test_url_is_included_in_resources(self):
        """Test explicit inclusion of URL works."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            contents = """
                    [
                        {
                            "url": "https://www.example.com/",
                            "resources": [
                                "https://www.example.com/",
                                "resource 1"
                            ]
                        }
                    ]
                    """
            expected = [
                check_website_resources.SingleURLConfig(
                    url="https://www.example.com/",
                    resources=["https://www.example.com/", "resource 1"],
                    cookies={},
                    comment="no comment",
                )
            ]
            filename = "test.json"
            patcher.fs.create_file(filename, contents=contents)
            actual = check_website_resources.read_config(path=filename)
            self.assertEqual(expected, actual)

    def test_url_is_not_included_in_resources(self):
        """Test URL not being included works."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            contents = """
                    [
                        {
                            "url": "https://www.example.com/",
                            "resources": [
                                "resource 1"
                            ]
                        }
                    ]
                    """
            expected = [
                check_website_resources.SingleURLConfig(
                    url="https://www.example.com/",
                    resources=["https://www.example.com/", "resource 1"],
                    cookies={},
                    comment="no comment",
                )
            ]
            filename = "test.json"
            patcher.fs.create_file(filename, contents=contents)
            actual = check_website_resources.read_config(path=filename)
            self.assertEqual(expected, actual)

    def test_url_is_missing_from_config(self):
        """Test URL not being included fails validation."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            contents = """
                    [
                        {
                            "resources": [
                                "resource 1"
                            ]
                        }
                    ]
                    """
            filename = "test.json"
            patcher.fs.create_file(filename, contents=contents)
            with self.assertRaisesRegex(
                ValueError, 'required config "url" not provided'
            ):
                check_website_resources.read_config(path=filename)

    def test_resources_are_missing_from_config(self):
        """Test resources not being included fails validation."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            contents = """
                    [
                        {
                            "url": "https://www.example.com/"
                        }
                    ]
                    """
            filename = "test.json"
            patcher.fs.create_file(filename, contents=contents)
            with self.assertRaisesRegex(
                ValueError, 'required config "resources" not provided'
            ):
                check_website_resources.read_config(path=filename)


@mock.patch("subprocess.run")
@mock.patch("check_website_resources.read_wget_log")
class TestRunWget(unittest.TestCase):
    """Tests for run_wget."""

    def test_called_correctly(self, mock_read, mock_subprocess):
        """Test that subprocess.run is called correctly."""
        mock_read.return_value = ["foo bar baz\n"]
        actual = check_website_resources.run_wget(
            url="https://www.example.com/", load_cookies=False
        )
        self.assertEqual(mock_read.return_value, actual)
        mock_subprocess.assert_called_once_with(
            check_website_resources.WGET_ARGS + ["https://www.example.com/"],
            check=True,
            capture_output=True,
        )

    def test_cookies(self, mock_read, mock_subprocess):
        """Test that cookies are used."""
        mock_read.return_value = ["foo bar baz\n"]
        actual = check_website_resources.run_wget(
            url="https://www.example.com/", load_cookies=True
        )
        self.assertEqual(mock_read.return_value, actual)
        mock_subprocess.assert_called_once_with(
            (
                check_website_resources.WGET_ARGS
                + ["--load-cookies=cookies.txt", "https://www.example.com/"]
            ),
            check=True,
            capture_output=True,
        )

    def test_process_fails(self, unused_mock_read, mock_subprocess):
        """Test that process failure is handled correctly."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["blah"], stderr="wget: command not found"
        )
        with self.assertLogs(level=logging.ERROR):
            with self.assertRaisesRegex(
                check_website_resources.WgetFailedException,
                r"^wget for https://www.example.com/ failed",
            ):
                check_website_resources.run_wget(
                    url="https://www.example.com/", load_cookies=False
                )


class TestReversePageSpeedMangling(unittest.TestCase):
    """Tests for reverse_pagespeed_mangling."""

    def test_simple(self):
        """A simple test."""
        inputs = split_inline_string(
            string="""
                /ariane-theme/images/new-logo-optimised.jpg.pagespeed.ce.yvq_6R_CGM.jpg
                /cart66/A.cart66_enhanced.css.pagespeed.cf.BLPYiFTVpx.css
                /css/dist/block-library/A.style.min.css.pagespeed.cf._93gOJAMuK.css
                /images/xcart66_admin_button.png.pagespeed.ic.nU-s0MGYCa.png
                /js/cart66-library.js+jquery.selectBox.js.pagespeed.jc.UhX2CG36B8.js
                /js/jquery/jquery.js.pagespeed.jm.gp20iU5FlU.js
                /public/css/A.cookie-law-info-gdpr.css.pagespeed.cf.rBqo-ZhFB1.css
                /public/css/A.cookie-law-info-public.css.pagespeed.cf.9bzBAumhiD.css
                /public/js/cookie-law-info-public.js.pagespeed.jm.fOf_UkWyBH.js
                /themes/ariane-theme/A.style.css.pagespeed.cf.lD0ZgzpJDA.css
                /themes/ariane-theme/images/favicons/favicon.ico
                /themes/ariane-theme/slider.js.pagespeed.jm.g0mntm2Nxd.js
                """
        )
        actual = check_website_resources.reverse_pagespeed_mangling(paths=inputs)
        expected = split_inline_string(
            string="""
                /ariane-theme/images/new-logo-optimised.jpg
                /cart66/cart66_enhanced.css
                /css/dist/block-library/style.min.css
                /images/cart66_admin_button.png
                /js/cart66-library.js+jquery.selectBox.js
                /js/jquery/jquery.js
                /public/css/cookie-law-info-gdpr.css
                /public/css/cookie-law-info-public.css
                /public/js/cookie-law-info-public.js
                /themes/ariane-theme/style.css
                /themes/ariane-theme/images/favicons/favicon.ico
                /themes/ariane-theme/slider.js
                """
        )
        self.assertEqual(expected, actual)


@mock.patch("check_website_resources.run_wget")
class TestCheckSingleUrl(unittest.TestCase):
    """Tests for check_single_url."""

    def test_success(self, mock_run_wget):
        """Very basic success test."""
        mock_run_wget.return_value = ["-- resource_1"]
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1"],
            cookies={},
            comment="comment",
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual([], actual)

    def test_wget_fails(self, mock_run_wget):
        """Test for correctly handling wget failure."""
        mock_run_wget.side_effect = check_website_resources.WgetFailedException(
            "forced failure"
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/", resources=[], cookies={}, comment="comment"
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual(
            [
                "https://www.example.com/ (comment): running wget "
                + "failed; forced failure"
            ],
            actual,
        )

    def test_parsing(self, mock_run_wget):
        """Test parsing."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- resource_1
                -x- ignore_this
                -- resource_2
                -x- resource_2 is repeated but should not be included twice.
                -- resource_2
                ignore this too
                -- foo bar return_baz
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1", "resource_2", "return_baz"],
            cookies={},
            comment="comment",
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual([], actual)

    def test_demangling(self, mock_run_wget):
        """Test that resources are demangled."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- /images/new-logo-optimised.jpg.pagespeed.ce.yvq_6R_CGM.jpg
                -- resource_2
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["/images/new-logo-optimised.jpg", "resource_2"],
            cookies={},
            comment="comment",
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual([], actual)

    def test_extra_resource(self, mock_run_wget):
        """Test for there being an unexpected resource."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- resource_1
                -- resource_2
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1"],
            cookies={},
            comment="comment",
        )
        actual = check_website_resources.check_single_url(config=config)
        expected = split_inline_string(
            string="""
                Unmatched resources for https://www.example.com/ (comment):
                resource_2
                """
        )
        self.assertEqual(expected, actual)

    def test_optional_resource(self, mock_run_wget):
        """Test for optional resource being accepted."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- resource_1
                -- resource_2
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1"],
            cookies={},
            comment="comment",
            optional_resources=["resource_2"],
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual([], actual)

    def test_optional_resource_regexes(self, mock_run_wget):
        """Test for optional resource regexes being accepted."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- resource_1
                -- dark-mode.min.7039e2fd92710e0626d451d6725af137.js
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1"],
            cookies={},
            comment="comment",
            optional_resource_regexes=["dark-mode.min.[a-z0-9]{32}.js"],
        )
        actual = check_website_resources.check_single_url(config=config)
        self.assertEqual([], actual)

    def test_cookies(self, mock_run_wget):
        """Test that cookies are handled properly."""
        mock_run_wget.return_value = split_inline_string(
            string="""
                -- resource_1
                -- resource_2
                """
        )
        config = check_website_resources.SingleURLConfig(
            url="https://www.example.com/",
            resources=["resource_1", "resource_2"],
            cookies={"foo": "bar"},
            comment="comment",
        )
        with pyfakefs.fake_filesystem_unittest.Patcher():
            actual = check_website_resources.check_single_url(config=config)
            with open(
                check_website_resources.COOKIES_FILE, encoding="utf8"
            ) as filehandle:
                lines = filehandle.readlines()
                self.assertEqual("# Netscape HTTP Cookie File\n", lines[0])
            self.assertEqual([], actual)


class TestGenerateCookiesFileContents(unittest.TestCase):
    """Tests for generate_cookies_file_contents."""

    def test_simple(self):
        """A simple test."""
        expected = split_inline_string(
            string="""
                # Netscape HTTP Cookie File
                www.example.com\tFALSE\t/\tFALSE\t0\tcookie_1\tyes
                www.example.com\tFALSE\t/\tFALSE\t0\tcookie_2\tno
                """
        )
        actual = check_website_resources.generate_cookies_file_contents(
            url="https://www.example.com/",
            cookies={"cookie_1": "yes", "cookie_2": "no"},
        )
        self.assertEqual(expected, actual)

    def test_bad_url(self):
        """Crash when a hostname cannot be extracted."""
        with self.assertRaisesRegex(ValueError, "^Unable to extract hostname"):
            check_website_resources.generate_cookies_file_contents(
                url="not_a_url", cookies={"cookie_1": "yes", "cookie_2": "no"}
            )


class TestParseArguments(unittest.TestCase):
    """Tests for parse_arguments."""

    def test_simple(self):
        """A simple test."""
        options = check_website_resources.parse_arguments(argv=["foo.json"])
        self.assertEqual(["foo.json"], options.config_files)


class TestMain(unittest.TestCase):
    """Tests for main()."""

    TEST_JSON_CONFIG = """
            [
                {
                    "url": "www.example.com",
                    "resources": [
                        "resource_1",
                        "resource_2"
                    ]
                }
            ]
            """

    def test_empty_config(self):
        """Test with an empty config."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            filename = "test.json"
            patcher.fs.create_file(filename, contents="[]")
            status = check_website_resources.main(argv=["unused", filename])
            self.assertEqual(0, status)

    def test_wget_fails(self):
        """Force wget to fail."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            filename = "test.json"
            patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
            with mock.patch("check_website_resources.run_wget") as mock_wget:
                mock_wget.side_effect = check_website_resources.WgetFailedException(
                    "forced failure"
                )
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    status = check_website_resources.main(argv=["unused", filename])
                    self.assertEqual(1, status)
                    warnings = mock_stderr.getvalue()
                    self.assertEqual(
                        "www.example.com (no comment): running wget "
                        + "failed; forced failure\n",
                        warnings,
                    )

    def test_expected_resources(self):
        """Test that expected resources causes zero messages."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            filename = "test.json"
            patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
            with mock.patch("check_website_resources.run_wget") as mock_wget:
                mock_wget.return_value = [
                    "-- www.example.com",
                    "-- resource_1",
                    "-- resource_2",
                ]
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    status = check_website_resources.main(argv=["unused", filename])
                    self.assertEqual(0, status)
                    warnings = mock_stderr.getvalue()
                    self.assertEqual("", warnings)

    def test_unexpected_resources(self):
        """Test that unexpected resources are handled properly."""
        with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
            filename = "test.json"
            patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
            with mock.patch("check_website_resources.run_wget") as mock_wget:
                mock_wget.return_value = [
                    "-- www.example.com",
                    "-- resource_1",
                    "-- resource_3",
                ]
                with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                    status = check_website_resources.main(argv=["unused", filename])
                    self.assertEqual(1, status)
                    warnings = mock_stderr.getvalue().rstrip("\n").split("\n")
                    expected = split_inline_string(
                        string="""
                            Missing resources for www.example.com (no comment):
                            resource_2
                            Unmatched resources for www.example.com (no comment):
                            resource_3
                            """
                    )
                    self.assertEqual(expected, warnings)

    @mock.patch("sys.exit")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    @mock.patch("sys.stderr", new_callable=io.StringIO)
    def test_no_args(self, mock_stderr, mock_stdout, _):
        """Test no args."""
        check_website_resources.main(argv=["argv0"])
        self.assertEqual("", mock_stdout.getvalue())
        # The name of the program is pytest when running tests.  Except when it's
        # pytest-3, so handle that too.
        expected = (
            "usage: pytest JSON_CONFIG_FILE [JSON_CONFIG_FILE2...]\n"
            "pytest: error: the following arguments are required: "
            "JSON_CONFIG_FILE\n"
        )
        actual = mock_stderr.getvalue().replace("pytest-3", "pytest")
        self.assertEqual(expected, actual)

    @mock.patch("sys.exit")
    @mock.patch("sys.stdout", new_callable=io.StringIO)
    def test_help(self, mock_stdout, _):
        """Test --help to ensure that the description is correctly set up."""
        check_website_resources.main(argv=["argv0", "--help"])
        # The name of the program is pytest when running tests.
        substrings = [
            "usage: pytest JSON_CONFIG_FILE [JSON_CONFIG_FILE2...]",
            "\n\nCheck that the correct resources are returned for",
            "\nJSON_CONFIG_FILE must contain a single list of dicts",
            "JSON_CONFIG_FILE  Config file specifying URLs and expected",
            "(multiple files are supported but are completely",
        ]
        stdout = mock_stdout.getvalue().replace("pytest-3", "pytest")
        for substring in substrings:
            with self.subTest(f"Testing -->>{substring}<<--"):
                self.assertIn(substring, stdout)


if __name__ == "__main__":  # pragma: no mutate
    unittest.main()
