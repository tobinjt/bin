"""Tests for check_backup_sentinels."""

#  from io import StringIO
import os
import typing
import unittest

#  import mock
from pyfakefs import fake_filesystem_unittest

import check_backup_sentinels


class TestParseSentinels(fake_filesystem_unittest.TestCase):
  """Tests for parsing sentinels."""

  def setUp(self):
    self.setUpPyfakefs()

  def create_files_for_test(self, data: typing.Dict[str, str]) -> None:
    """Create files for tests."""
    for (filename, contents) in data.items():
      # pylint: disable=no-member
      # Disable "Instance of 'FakeFilesystem' has no 'CreateFile' member"
      self.fs.CreateFile(filename, contents=contents)

  def test_simple(self):
    """Test basic processing."""
    testdir = '/test/test_simple'
    hostname = 'a-hostname'
    base = os.path.join(testdir, hostname)
    ps = check_backup_sentinels.ParsedSentinels
    files = {
        base: '1234\n',
        '%s.%s' % (base, ps.SLEEPING_UNTIL): '5432\n',
        '%s.%s' % (base, ps.MAX_ALLOWED_DELAY): '98\n',
    }
    self.create_files_for_test(files)
    parsed = check_backup_sentinels.parse_sentinels(testdir, 7)
    self.assertEqual({hostname: 1234}, parsed.timestamps)
    self.assertEqual({hostname: 5432}, parsed.sleeping_until)
    self.assertEqual({hostname: 98}, parsed.max_allowed_delay)

  def test_default_delay(self):
    """Test default delay is used."""
    testdir = '/test/test_simple'
    hostname = 'a-hostname'
    files = {
        os.path.join(testdir, hostname): '31313\n',
    }
    self.create_files_for_test(files)
    parsed = check_backup_sentinels.parse_sentinels(testdir, 7)
    self.assertEqual({hostname: 31313}, parsed.timestamps)
    self.assertEqual({hostname: 7}, parsed.max_allowed_delay)
    self.assertNotIn(hostname, parsed.sleeping_until)

  def test_bad_filename(self):
    """Test handling of bad filenames."""
    testdir = '/test/test_simple'
    hostname = 'a-hostname'
    files = {
        '%s.%s' % (os.path.join(testdir, hostname), 'qwerty'): '5432\n',
    }
    self.create_files_for_test(files)
    self.assertRaises(check_backup_sentinels.Error,
                      check_backup_sentinels.parse_sentinels, testdir, 7)


class TestMain(unittest.TestCase):
  """Tests for main."""

  def test_bad_args(self):
    """Check that bad args are rejected."""
    with self.assertRaisesRegex(check_backup_sentinels.Error, '^Usage:.*'):
      check_backup_sentinels.main(['argv0'])
    with self.assertRaisesRegex(check_backup_sentinels.Error, '^Usage:.*'):
      check_backup_sentinels.main(['argv0', 'expected', 'not expected'])

  def test_good_args(self):
    """Check that good args are accepted."""
    check_backup_sentinels.main(['argv0', 'expected'])

if __name__ == '__main__':
  unittest.main()
