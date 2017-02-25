"""Tests for linkdirs."""

import os

from pyfakefs import fake_filesystem_unittest

import linkdirs


class TestMain(fake_filesystem_unittest.TestCase):
  """Tests for RealMain and main."""

  def setUp(self):
    self.setUpPyfakefs()

  def test_main(self):
    """Test main."""
    src_file = '/a/b/c/file'
    src_content = 'qwerty'
    dest_dir = '/z/y/x'
    self.fs.CreateFile(src_file, contents=src_content)
    os.makedirs(dest_dir)

    linkdirs.RealMain(['linkdirs', os.path.dirname(src_file), dest_dir])
    with open(os.path.join(dest_dir, os.path.basename(src_file)), 'r') as tfh:
      self.assertEqual(src_content, tfh.read())
