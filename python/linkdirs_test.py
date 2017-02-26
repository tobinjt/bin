"""Tests for linkdirs."""

import os
import StringIO

import mock
from pyfakefs import fake_filesystem_unittest

import linkdirs


class TestSafeUnlink(fake_filesystem_unittest.TestCase):
  """Tests for safe_unlink."""

  def setUp(self):
    self.setUpPyfakefs()

  @mock.patch('sys.stdout', new_callable=StringIO.StringIO)
  def test_delete_file(self, mock_stdout):
    """Delete a file for real."""
    filename = '/a/b/c/file'
    self.fs.CreateFile(filename)
    self.assertTrue(os.path.exists(filename))
    linkdirs.safe_unlink(filename, False)
    self.assertFalse(os.path.exists(filename))
    self.assertEqual('', mock_stdout.getvalue())


class TestIntegration(fake_filesystem_unittest.TestCase):
  """Integration tests: exercise as much code as possible.

  Use cases to test:
  - Missing file gets created.
  - File with same contents is replaced with link.
  - Excluded files/dirs are skipped.
  - Report unexpected files.
  """

  def assert_files_are_linked(self, file1, file2):
    """Assert that two files are linked."""
    self.assertTrue(os.path.samefile(file1, file2))

  def setUp(self):
    self.setUpPyfakefs()

  def test_missing_file_is_created(self):
    """Simple test for main."""
    src_dir = '/a/b/c/file'
    filename = 'file'
    src_file = os.path.join(src_dir, filename)
    src_content = 'qwerty'
    dest_dir = '/z/y/x'
    dest_file = os.path.join(dest_dir, filename)
    self.fs.CreateFile(src_file, contents=src_content)
    os.makedirs(dest_dir)

    linkdirs.real_main(['linkdirs', src_dir, dest_dir])
    self.assert_files_are_linked(src_file, dest_file)

  def test_no_conflict(self):
    """Test with no conflicts."""
    pass
