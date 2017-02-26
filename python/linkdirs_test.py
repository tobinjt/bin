"""Tests for linkdirs."""

import os
import re
import StringIO
import unittest

import mock
from pyfakefs import fake_filesystem_unittest

import linkdirs


class TestIntegration(fake_filesystem_unittest.TestCase):
  """Integration tests: exercise as much code as possible.

  Use cases to test:
  - Missing file gets created.
  - File with same contents is replaced with link.
  - Excluded files/dirs are skipped.
  - Report unexpected files.
  - Report diffs.
  - Bad arguments are caught.
  """

  def assert_files_are_linked(self, file1, file2):
    """Assert that two files are linked."""
    self.assertTrue(os.path.samefile(file1, file2))

  def setUp(self):
    self.setUpPyfakefs()

  def test_missing_file_is_created(self):
    """Missing file gets created."""
    src_file = '/a/b/c/file'
    dest_file = '/z/y/x/file'
    self.fs.CreateFile(src_file, contents='qwerty')

    linkdirs.real_main(['linkdirs', os.path.dirname(src_file),
                        os.path.dirname(dest_file)])
    self.assert_files_are_linked(src_file, dest_file)

  def test_replace_same_contents(self):
    """File with same contents is replaced with link."""
    src_file = '/a/b/c/file'
    dest_file = '/z/y/x/file'
    self.fs.CreateFile(src_file, contents='qwerty')
    self.fs.CreateFile(dest_file, contents='qwerty')

    with mock.patch('sys.stdout',
                    new_callable=StringIO.StringIO) as mock_stdout:
      linkdirs.real_main(['linkdirs', os.path.dirname(src_file),
                          os.path.dirname(dest_file)])
      self.assert_files_are_linked(src_file, dest_file)
      expected = ('/a/b/c/file and /z/y/x/file are different files but have the'
                  ' same contents; deleting and linking\n')
      self.assertEqual(expected, mock_stdout.getvalue())

  def test_report_unexpected_files(self):
    """Report unexpected files."""
    src_dir = '/a/b/c'
    self.fs.CreateFile(os.path.join(src_dir, 'file'))
    # 'asdf' subdir exists here, so it will be checked in destdir.
    self.fs.CreateFile(os.path.join(src_dir, 'asdf', 'file'))
    dest_dir = '/z/y/x'
    self.fs.CreateFile(os.path.join(dest_dir, 'pinky'))
    self.fs.CreateFile(os.path.join(dest_dir, 'the_brain'))
    # Ensure there is a subdir that should not be reported.
    os.makedirs(os.path.join(dest_dir, 'subdir'))
    # And also a subdir that will be reported.
    os.makedirs(os.path.join(dest_dir, 'asdf', 'report_me'))

    actual = linkdirs.real_main(['linkdirs', '--report_unexpected_files',
                                 '--ignore_unexpected_children',
                                 src_dir, dest_dir])
    expected = [
        'Unexpected directory: /z/y/x/asdf/report_me',
        'Unexpected file: /z/y/x/pinky',
        'Unexpected file: /z/y/x/the_brain',
        'rm /z/y/x/pinky /z/y/x/the_brain',
        'rmdir /z/y/x/asdf/report_me',
    ]
    self.assertEqual(expected, actual)

  def test_exclusions_are_skipped(self):
    """Excluded files/dirs are skipped."""
    non_skip_files = ['link_me', 'me_too']
    non_skip_dirs = ['harry', 'murphy']
    skip_files = ['pinky', 'the_brain']
    skip_dirs = ['loki', 'molly']
    skip_contents = '\n'.join(skip_files + ['# a comment', ''] + skip_dirs)
    skip_filename = 'skip-me'
    self.fs.CreateFile(skip_filename, contents=skip_contents)

    src_dir = '/a/b/c'
    for dirname in skip_dirs + non_skip_dirs:
      for filename in skip_files + non_skip_files:
        self.fs.CreateFile(os.path.join(src_dir, dirname, filename))

    dest_dir = '/z/y/x'
    linkdirs.real_main(['linkdirs', '--ignore_file=%s' % skip_filename,
                        # Report unexpected files because it exercises more code
                        # paths.
                        '--report_unexpected_files',
                        '--ignore_unexpected_children',
                        src_dir, dest_dir])

    files = []
    for dirpath, _, filenames in os.walk(dest_dir):
      for filename in filenames:
        files.append(os.path.join(dirpath, filename))
    files.sort()
    expected = ['harry/link_me', 'harry/me_too', 'murphy/link_me',
                'murphy/me_too']
    expected = [os.path.join(dest_dir, x) for x in expected]
    self.assertEqual(expected, files)

  def test_report_diffs(self):
    """Report diffs."""
    src_file = '/a/b/c/file'
    dest_file = '/z/y/x/file'
    self.fs.CreateFile(src_file, contents='qwerty\n')
    self.fs.CreateFile(dest_file, contents='asdf\n')

    # Test without --force to generate diffs.
    actual = linkdirs.real_main(['linkdirs', os.path.dirname(src_file),
                                 os.path.dirname(dest_file)])
    # Strip off timestamps.
    actual = [re.sub(r'\t.*\n', '\t\n', x) for x in actual]
    expected = [
        '--- /z/y/x/file\t\n',
        '+++ /a/b/c/file\t\n',
        '@@ -1 +1 @@\n',
        '-asdf\n',
        '+qwerty\n',
    ]
    self.assertEqual(expected, actual)

    # Test with --force to overwrite.
    actual = linkdirs.real_main(['linkdirs', '--force',
                                 os.path.dirname(src_file),
                                 os.path.dirname(dest_file)])
    self.assertEqual([], actual)
    self.assert_files_are_linked(src_file, dest_file)

  def test_argument_handling(self):
    """Bad arguments are caught."""
    self.assertEqual(
        ['Usage: linkdirs [OPTIONS] SOURCE_DIR [SOURCE_DIR...] DEST_DIR'],
        linkdirs.real_main(['linkdirs', '--force', '/asdf']))


if __name__ == '__main__':
  unittest.main()
