"""Tests for check_website_resources."""

import io
import logging
import subprocess
import textwrap
from typing import List, Text
import unittest

import mock
import pyfakefs

import check_website_resources


def split_inline_string(string: Text) -> List[Text]:
  """Split a multi-line inline string, stripping empty start and end lines."""
  return textwrap.dedent(string).strip().split('\n')


class TestReadWgetLog(unittest.TestCase):
  """Tests for read_wget_log."""

  def test_simple(self):
    """A very simple test."""
    with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
      patcher.fs.create_file(check_website_resources.WGET_LOG,
                             contents='asdf\n1234\n')
      actual = check_website_resources.read_wget_log()
      self.assertEqual(['asdf', '1234'], actual)


class TestWriteCookiesFile(unittest.TestCase):
  """Tests for write_cookies_file."""

  def test_simple(self):
    """A very simple test."""
    with pyfakefs.fake_filesystem_unittest.Patcher():
      lines = ['asdf', '1234']
      check_website_resources.write_cookies_file(lines)
      with open(check_website_resources.COOKIES_FILE) as filehandle:
        self.assertEqual('asdf\n1234\n', filehandle.read())


class TestReadConfig(unittest.TestCase):
  """Tests for read_config."""

  def test_url_is_included(self):
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
              url='https://www.example.com/',
              resources=['https://www.example.com/', 'resource 1'],
              cookies={},
              )
          ]
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=contents)
      actual = check_website_resources.read_config(filename)
      self.assertEqual(expected, actual)

  def test_url_is_not_included(self):
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
              url='https://www.example.com/',
              resources=['https://www.example.com/', 'resource 1'],
              cookies={},
              )
          ]
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=contents)
      actual = check_website_resources.read_config(filename)
      self.assertEqual(expected, actual)


class TestValidateUserConfig(unittest.TestCase):
  """Tests for validate_user_config."""
  def test_validation(self):
    """Tests for all the validations."""
    # "assertion message": data structure.
    tests = {
        'Top-level data structure': 1,
        'All entries in the list must be dicts': [1],
        'Unsupported key': [{'asdf': 1}],
        'required config "url" not provided': [{'resources': 1}],
        'required config "resources" not provided': [{'url': 1}],
        'url must be a string': [{'url': 1, 'resources': []}],
        'resources must be a list of strings': [{'url': 'x', 'resources': 1}],
        'all resources must be strings': [{'url': 'x', 'resources': [1]}],
        'cookies must be a dict': [
            {'url': 'x', 'resources': ['x'], 'cookies': 1}],
        'everything in cookies must be strings': [
            {'url': 'x', 'resources': ['x'], 'cookies': {1: 'x'}}],
        'everything in cookies must be strings.': [
            {'url': 'x', 'resources': ['x'], 'cookies': {'x': 1}}],
        }
    for message, data in tests.items():
      with self.subTest(message):
        with self.assertRaisesRegex(ValueError, 'config.json:.*' + message):
          check_website_resources.validate_user_config('config.json', data)

  def test_valid_config(self):  # pylint: disable=no-self-use
    """Test that a valid config does not trigger any exceptions."""
    data = [
        {
            'url': 'http://www.example.com/',
            'resources': ['http://www.example.com/style.css'],
            'cookies': {'key': 'value'},
            },
        {
            'url': 'http://example.com/',
            'resources': ['http://example.com/style.css'],
            },
        ]
    check_website_resources.validate_user_config('config.json', data)


@mock.patch('subprocess.run')
@mock.patch('check_website_resources.read_wget_log')
class TestRunWget(unittest.TestCase):
  """Tests for run_wget."""

  def test_called_correctly(self, mock_read, mock_subprocess):
    """Test that subprocess.run is called correctly."""
    mock_read.return_value = ['foo bar baz\n']
    actual = check_website_resources.run_wget('https://www.example.com/', False)
    self.assertEqual(mock_read.return_value, actual)
    mock_subprocess.assert_called_once_with(
        check_website_resources.WGET_ARGS + ['https://www.example.com/'],
        check=True, capture_output=True)

  def test_cookies(self, mock_read, mock_subprocess):
    """Test that cookies are used."""
    mock_read.return_value = ['foo bar baz\n']
    actual = check_website_resources.run_wget('https://www.example.com/', True)
    self.assertEqual(mock_read.return_value, actual)
    mock_subprocess.assert_called_once_with(
        (check_website_resources.WGET_ARGS
         + ['--load-cookies=cookies.txt', 'https://www.example.com/']),
        check=True, capture_output=True)

  def test_process_fails(self, unused_mock_read, mock_subprocess):
    """Test that process failure is handled correctly."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=['blah'], stderr='wget: command not found')
    with self.assertLogs(level=logging.ERROR):
      actual = check_website_resources.run_wget('https://www.example.com/',
                                                False)
      self.assertEqual([], actual)


class TestReversePageSpeedMangling(unittest.TestCase):
  """Tests for reverse_pagespeed_mangling."""
  def test_simple(self):
    """A simple test."""
    inputs = split_inline_string(
        """
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
        """)
    actual = check_website_resources.reverse_pagespeed_mangling(inputs)
    expected = split_inline_string(
        """
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
        """)
    self.assertEqual(expected, actual)


@mock.patch('check_website_resources.run_wget')
class TestCheckSingleUrl(unittest.TestCase):
  """Tests for check_single_url."""

  def test_success(self, mock_run_wget):
    """Very basic success test."""
    mock_run_wget.return_value = ['-- resource_1']
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/', resources=['resource_1'], cookies={})
    actual = check_website_resources.check_single_url(config)
    self.assertEqual([], actual)

  def test_wget_fails(self, mock_run_wget):
    """Test for correctly handling wget failure."""
    mock_run_wget.return_value = []
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/', resources=[], cookies={})
    actual = check_website_resources.check_single_url(config)
    self.assertEqual(['Running wget failed'], actual)

  def test_parsing(self, mock_run_wget):
    """Test parsing."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -x- ignore_this
        -- resource_2
        ignore this too
        -- foo bar return_baz
        """)
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/',
        resources=['resource_1', 'resource_2', 'return_baz'],
        cookies={})
    actual = check_website_resources.check_single_url(config)
    self.assertEqual([], actual)

  def test_demangling(self, mock_run_wget):
    """Test that resources are demangled."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- /images/new-logo-optimised.jpg.pagespeed.ce.yvq_6R_CGM.jpg
        -- resource_2
        """)
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/',
        resources=['/images/new-logo-optimised.jpg', 'resource_2'],
        cookies={})
    actual = check_website_resources.check_single_url(config)
    self.assertEqual([], actual)

  def test_extra_resource(self, mock_run_wget):
    """Test for there being an unexpected resource."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -- resource_2
        """)
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/', resources=['resource_1'], cookies={})
    actual = check_website_resources.check_single_url(config)
    expected = split_inline_string(
        """
        Unexpected resource diffs for https://www.example.com/:
        --- expected
        +++ actual
        @@ -1 +1,2 @@
         resource_1
        +resource_2
        """)
    self.assertEqual(expected, actual)

  def test_cookies(self, mock_run_wget):
    """Test that cookies are handled properly."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -- resource_2
        """)
    config = check_website_resources.SingleURLConfig(
        url='https://www.example.com/', resources=['resource_1', 'resource_2'],
        cookies={'foo': 'bar'})
    with pyfakefs.fake_filesystem_unittest.Patcher():
      actual = check_website_resources.check_single_url(config)
      with open(check_website_resources.COOKIES_FILE) as filehandle:
        lines = filehandle.readlines()
        self.assertEqual('# Netscape HTTP Cookie File\n', lines[0])
      self.assertEqual([], actual)


class TestGenerateCookiesFileContents(unittest.TestCase):
  """Tests for generate_cookies_file_contents."""
  def test_simple(self):
    """A simple test."""
    expected = split_inline_string(
        """
        # Netscape HTTP Cookie File
        www.example.com\tFALSE\t/\tFALSE\t0\tcookie_1\tyes
        www.example.com\tFALSE\t/\tFALSE\t0\tcookie_2\tno
        """)
    actual = check_website_resources.generate_cookies_file_contents(
        'https://www.example.com/', {'cookie_1': 'yes', 'cookie_2': 'no'})
    self.assertEqual(expected, actual)

  def test_bad_url(self):
    """Crash when a hostname cannot be extracted."""
    with self.assertRaises(ValueError):
      check_website_resources.generate_cookies_file_contents(
          'not_a_url', {'cookie_1': 'yes', 'cookie_2': 'no'})


class TestParseArguments(unittest.TestCase):
  """Tests for parse_arguments."""
  def test_simple(self):
    """A simple test."""
    options = check_website_resources.parse_arguments(['foo.json'])
    self.assertEqual(['foo.json'], options.config_files)


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
      filename = 'test.json'
      patcher.fs.create_file(filename, contents='[]')
      status = check_website_resources.main(['unused', filename])
      self.assertEqual(0, status)

  def test_wget_fails(self):
    """Force wget to fail."""
    with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
      with mock.patch('check_website_resources.run_wget') as mock_wget:
        mock_wget.return_value = []
        with mock.patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
          status = check_website_resources.main(['unused', filename])
          self.assertEqual(1, status)
          warnings = mock_stderr.getvalue()
          self.assertEqual('Running wget failed\n', warnings)

  def test_expected_resources(self):
    """Test that expected resources causes zero messages."""
    with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
      with mock.patch('check_website_resources.run_wget') as mock_wget:
        mock_wget.return_value = [
            '-- www.example.com', '-- resource_1', '-- resource_2']
        with mock.patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
          status = check_website_resources.main(['unused', filename])
          self.assertEqual(0, status)
          warnings = mock_stderr.getvalue()
          self.assertEqual('', warnings)

  def test_unexpected_resources(self):
    """Test that unexpected resources are handled properly."""
    with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=self.TEST_JSON_CONFIG)
      with mock.patch('check_website_resources.run_wget') as mock_wget:
        mock_wget.return_value = [
            '-- www.example.com', '-- resource_1', '-- resource_3']
        with mock.patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
          status = check_website_resources.main(['unused', filename])
          self.assertEqual(1, status)
          warnings = mock_stderr.getvalue().rstrip('\n').split('\n')
          expected = split_inline_string(
              """
              Unexpected resource diffs for www.example.com:
              --- expected
              +++ actual
              @@ -1,3 +1,3 @@
               resource_1
              -resource_2
              +resource_3
               www.example.com
              """)
          self.assertEqual(expected, warnings)


if __name__ == '__main__':
  unittest.main()
