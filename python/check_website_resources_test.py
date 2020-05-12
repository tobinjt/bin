"""Tests for check_website_resources."""

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
      self.assertEqual(['asdf\n', '1234\n'], actual)


class TestReadConfig(unittest.TestCase):
  """Tests for read_config."""

  def test_simple(self):
    """A very simple test."""
    with pyfakefs.fake_filesystem_unittest.Patcher() as patcher:
      contents = """
          {
              "URL": [
                  "resource 1",
                  "resource 2"
              ]
          }
          """
      expected = {
          'URL': [
              'resource 1',
              'resource 2',
              ]
          }
      filename = 'test.json'
      patcher.fs.create_file(filename, contents=contents)
      actual = check_website_resources.read_config(filename)
      self.assertEqual(expected, actual)


@mock.patch('subprocess.run')
@mock.patch('check_website_resources.read_wget_log')
class TestRunWget(unittest.TestCase):
  """Tests for run_wget."""

  def test_called_correctly(self, mock_read, mock_subprocess):
    """Test that subprocess.run is called correctly."""
    mock_read.return_value = ['foo bar baz\n']
    actual = check_website_resources.run_wget('asdf')
    self.assertEqual(mock_read.return_value, actual)
    mock_subprocess.assert_called_once_with(
        check_website_resources.WGET_ARGS + ['asdf'],
        check=True, capture_output=True)

  def test_process_fails(self, unused_mock_read, mock_subprocess):
    """Test that process failure is handled correctly."""
    mock_subprocess.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=['blah'], stderr='wget: command not found')
    with self.assertLogs(level=logging.ERROR):
      actual = check_website_resources.run_wget('asdf')
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
    """TODO: WRITE ACTUAL TEST. Test for resources being correct."""
    mock_run_wget.return_value = ['TODO: WRITE ACTUAL TEST.']
    actual = check_website_resources.check_single_url(
        'asdf', [])
    self.assertEqual([], actual)

  def test_wget_fails(self, mock_run_wget):
    """Test for correctly handling wget failure."""
    mock_run_wget.return_value = []
    actual = check_website_resources.check_single_url(
        'asdf', [])
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
    actual = check_website_resources.check_single_url(
        'asdf', ['resource_1', 'resource_2', 'return_baz'])
    self.assertEqual([], actual)

  def test_demangling(self, mock_run_wget):
    """Test that resources are demangled."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- /images/new-logo-optimised.jpg.pagespeed.ce.yvq_6R_CGM.jpg
        -- resource_2
        """)
    actual = check_website_resources.check_single_url(
        'asdf', ['/images/new-logo-optimised.jpg', 'resource_2'])
    self.assertEqual([], actual)

  def test_extra_resource(self, mock_run_wget):
    """Test for there being an unexpected resource."""
    mock_run_wget.return_value = split_inline_string(
        """
        -- resource_1
        -- resource_2
        """)
    actual = check_website_resources.check_single_url(
        'asdf', ['resource_1'])
    expected = split_inline_string(
        """
        Unexpected resource diffs for asdf:
        --- expected
        +++ actual
        @@ -1 +1,2 @@
         resource_1
        +resource_2
        """)
    self.assertEqual(expected, actual)


class TestParseArguments(unittest.TestCase):
  """Tests for parse_arguments."""
  def test_simple(self):
    """A simple test."""
    options = check_website_resources.parse_arguments(['foo.json'])
    self.assertEqual('foo.json', options.config)


if __name__ == '__main__':
  unittest.main()
