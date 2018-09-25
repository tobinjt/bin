"""Tests for check_backup_sentinels."""

#  from io import StringIO
import os
import unittest

#  import mock
from pyfakefs import fake_filesystem_unittest

import check_backup_sentinels


class TestParseSentinels(fake_filesystem_unittest.TestCase):
  """Tests for parsing sentinels."""

  def setUp(self):
    self.setUpPyfakefs()

  def test_simple(self):
    """Test basic processing."""
    # pylint: disable=no-member
    # Disable "Instance of 'FakeFilesystem' has no 'CreateFile' member"
    testdir = '/test/test_simple'
    hostname = 'a-hostname'
    base = os.path.join(testdir, hostname)
    self.fs.CreateFile(base, contents='1234\n')
    sleeping = check_backup_sentinels.ParsedSentinels.SLEEPING_UNTIL
    self.fs.CreateFile('%s.%s' % (base, sleeping), contents='5432\n')
    max_allowed = check_backup_sentinels.ParsedSentinels.MAX_ALLOWED_DELAY
    self.fs.CreateFile('%s.%s' % (base, max_allowed), contents='98\n')
    parsed = check_backup_sentinels.parse_sentinels(testdir)
    self.assertEqual({hostname: 1234}, parsed.timestamps)
    self.assertEqual({hostname: 5432}, parsed.sleeping_until)
    self.assertEqual({hostname: 98}, parsed.max_allowed_delay)

  def test_bad_filename(self):
    """Test handling of bad filenames."""
    # pylint: disable=no-member
    # Disable "Instance of 'FakeFilesystem' has no 'CreateFile' member"
    testdir = '/test/test_simple'
    hostname = 'a-hostname'
    base = os.path.join(testdir, hostname)
    self.fs.CreateFile('%s.%s' % (base, 'qwerty'), contents='5432\n')
    self.assertRaises(check_backup_sentinels.Error,
                      check_backup_sentinels.parse_sentinels, testdir)


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
