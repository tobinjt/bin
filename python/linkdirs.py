#!/usr/bin/python

"""%prog [OPTIONS] SOURCE_DIRECTORY [SOURCE_DIRECTORY...] DESTINATION_DIRECTORY.

Link all files in SOURCE_DIRECTORY [SOURCE_DIRECTORY...] to
DESTINATION_DIRECTORY, creating the destination directory hierarchy where
necessary.
"""

import collections
import difflib
import fnmatch
import optparse
import os
import pipes
import shutil
import stat
import sys
import textwrap
import time

__author__ = "johntobin@johntobin.ie (John Tobin)"


class Error(Exception):
  """Base class for exceptions."""
  pass


class LinkResults(collections.namedtuple('LinkResults',
                                         'expected_files diffs errors')):
  """Container for the results of linking files and directories.

  Attributes:
    expected_files: list(str), files and directories that should exist in the
                    destination.
    diffs: list(str), diffs between source and destination files.
    errors: list(str), error messages.
  """

  def extend(self, other):
    """Extend self with the data from other.

    Args:
      other: LinkResults, data to append.
    """
    self.expected_files.extend(other.expected_files)
    self.diffs.extend(other.diffs)
    self.errors.extend(other.errors)


def safe_unlink(unlink_me, dryrun=True):
  """Remove a file or directory, or print shell commands that would do so.

  Args:
    unlink_me: the file or directory to be removed.
    dryrun:    if True, shell commands are printed; if False, unlink_me is
               removed.  Defaults to True.

  Raises:
    OSError: there was a problem removing unlink_me.
  """

  if os.path.islink(unlink_me) or not os.path.isdir(unlink_me):
    if dryrun:
      print "rm %s" % pipes.quote(unlink_me)
    else:
      os.unlink(unlink_me)
  else:
    if dryrun:
      print "rm -r %s" % pipes.quote(unlink_me)
    else:
      shutil.rmtree(unlink_me)


def safe_link(source_filename, dest_filename, dryrun=True):
  """Link one file to another, or print shell commands that would do so.

  Args:
    source_filename: str, existing filename.
    dest_filename:   str, new filename.
    dryrun:          bool, if True, shell commands are printed; if False, files
                     are linked.  Defaults to True.
  Raises:
    OSError: there was a problem linking files.
  """

  if dryrun:
    print "ln %s %s" % (pipes.quote(source_filename),
                        pipes.quote(dest_filename))
  else:
    os.link(source_filename, dest_filename)


def diff(old_filename, new_filename):
  """Return a diff between old and new files.

  Args:
    old_filename: the original file.
    new_filename: the new file.

  Returns:
    An array of strings, possibly empty.

  Raises:
    OSError: an error occurred reading one of the files.
  """

  old_timestamp = time.ctime(os.stat(old_filename).st_mtime)
  old_contents = open(old_filename, "r").readlines()
  new_timestamp = time.ctime(os.stat(new_filename).st_mtime)
  new_contents = open(new_filename, "r").readlines()
  diff_generator = difflib.unified_diff(new_contents, old_contents,
                                        new_filename, old_filename,
                                        new_timestamp, old_timestamp)
  diffs = [d for d in diff_generator]
  return diffs


def remove_skip_patterns(files, skip):
  """Remove any files matching shell patterns.

  Args:
    files: a list of filenames.
    skip: a list of shell patterns.

  Returns:
    An array of filenames.
  """

  unmatched = []
  for filename in files:
    for pattern in skip:
      if fnmatch.fnmatch(filename, pattern):
        break
    else:
      unmatched.append(filename)
  return unmatched


def link_dir(source, dest, options):
  """Recursively link files in source directory to dest directory.

  Args:
    source:  str, the source directory
    dest:    str, the destination directory
    options: argparse.Namespace, options requested by the user.

  Returns:
    LinkResults.

  Raises:
    OSError: a filesystem operation failed.
  """

  results = LinkResults([], [], [])
  for directory, subdirs, files in os.walk(source, topdown=True):
    # Remove skippable subdirs.  Assigning to the slice will prevent os.walk
    # from descending into the skipped subdirs.
    subdirs[:] = remove_skip_patterns(subdirs, options.skip)
    subdirs.sort()
    for subdir in subdirs:
      source_dir = os.path.join(directory, subdir)
      dest_dir = source_dir.replace(source, dest, 1)
      results.expected_files.append(dest_dir)
      source_stat = os.stat(source_dir)
      source_mode = stat.S_IMODE(source_stat.st_mode)

      if os.path.isdir(dest_dir):
        if not options.dryrun:
          os.chmod(dest_dir, source_mode)
        else:
          print "chmod %s %s" % (oct(source_mode), pipes.quote(dest_dir))
        continue

      if os.path.exists(dest_dir):
        # Destination isn't a directory.
        if options.force:
          safe_unlink(dest_dir, options.dryrun)
        else:
          results.errors.append("%s is not a directory" % dest_dir)
          continue

      if options.dryrun:
        print "mkdir %s" % pipes.quote(dest_dir)
      else:
        os.mkdir(dest_dir, source_mode)
        os.chmod(dest_dir, source_mode)

    results.extend(link_files(source, dest, directory, files, options))

  return results


def link_files(source, dest, directory, files, options):
  """Link files from source to dest.

  Args:
    source:    str, the toplevel source directory.
    dest:      str, the toplevel dest directory.
    directory: str, the directory the files are in, relative to source and dest.
    files:     list(str), the files in source/directory.
    options:   argparse.Namespace, options requested by the user.

  Returns:
    LinkResults.  expected_files will not include files that are skipped.
  """

  results = LinkResults([], [], [])
  files = remove_skip_patterns(files, options.skip)
  files = [os.path.join(directory, filename) for filename in files]
  skip = ["*%s%s" % (os.sep, pattern) for pattern in options.skip]
  files = remove_skip_patterns(files, skip)
  files.sort()
  for source_filename in files:
    dest_filename = source_filename.replace(source, dest, 1)
    results.expected_files.append(dest_filename)

    if os.path.islink(source_filename):
      # Skip source symlinks.
      results.errors.append("Skipping symbolic link %s" % source_filename)
      continue

    if not os.path.exists(dest_filename) and not os.path.islink(dest_filename):
      # Destination doesn't already exist, and it's not a dangling symlink, so
      # just link it.
      safe_link(source_filename, dest_filename, options.dryrun)
      continue

    if os.path.islink(dest_filename) or not os.path.isfile(dest_filename):
      # Destination exists and is not a file.
      if options.force:
        safe_unlink(dest_filename, options.dryrun)
        safe_link(source_filename, dest_filename, options.dryrun)
      else:
        results.errors.append("%s: is not a file" % dest_filename)
      continue

    if os.path.samefile(source_filename, dest_filename):
      # The file is correctly linked.
      continue

    if options.force:
      # Don't bother checking anything if --force was used.
      safe_unlink(dest_filename, options.dryrun)
      safe_link(source_filename, dest_filename, options.dryrun)
      continue

    # If the destination is already linked don't change it without --force.
    num_links = os.stat(dest_filename)[stat.ST_NLINK]
    if num_links != 1:
      results.errors.append("%s: link count is %d" % (dest_filename, num_links))
      continue

    # Check for diffs.
    file_diffs = diff(source_filename, dest_filename)
    if file_diffs:
      results.diffs.extend(file_diffs)
      continue

    print ("%s and %s are different files but have the same contents; "
           "deleting and linking" % (source_filename, dest_filename))
    safe_unlink(dest_filename, options.dryrun)
    safe_link(source_filename, dest_filename, options.dryrun)

  return results


def report_unexpected_files(dest_dir, expected_files_list, options):
  """Check for files in destdir that aren't in source_dir.

  Args:
    dest_dir: str, the destination directory.
    expected_files_list: list(str), files expected to exist in the destination.
    options: argparse.Namespace, options requested by the user.

  Returns:
    list(str), the messages to print.
  """

  expected_files = {dest_dir: 1}
  for entry in expected_files_list:
    expected_files[entry] = 1

  unexpected_msgs = []
  unexpected_paths = {
      "directory": [],
      "file": []
  }
  for directory, subdirs, files in os.walk(dest_dir, topdown=True):
    subdirs[:] = remove_skip_patterns(subdirs, options.skip)
    subdirs.sort()
    files = remove_skip_patterns(files, options.skip)
    files.sort()

    if directory == dest_dir and options.ignore_unexpected_children:
      unexpected = [subdir for subdir in subdirs
                    if os.path.join(directory, subdir) not in expected_files]
      for subdir in unexpected:
        subdirs.remove(subdir)

    full_subdirs = [os.path.join(directory, entry) for entry in subdirs]
    full_files = [os.path.join(directory, entry) for entry in files]
    skip_more = ["*%s%s" % (os.sep, pattern) for pattern in options.skip]
    full_files = remove_skip_patterns(full_files, skip_more)
    for (my_list, my_type) in ((full_subdirs, "directory"),
                               (full_files, "file")):
      for entry in my_list:
        if entry not in expected_files:
          unexpected_msgs.append("Unexpected %s: %s" % (my_type, entry))
          unexpected_paths[my_type].append(entry)

  unexpected_msgs.sort()
  unexpected_paths["file"].sort()
  unexpected_paths["directory"].sort()
  if unexpected_paths["file"]:
    unexpected_msgs.append("rm %s" % " ".join(unexpected_paths["file"]))
  if unexpected_paths["directory"]:
    # Descending sort by length, so that child directories are removed before
    # parent directories.
    unexpected_paths["directory"].sort(key=len, reverse=True)
    unexpected_msgs.append("rmdir %s" % " ".join(unexpected_paths["directory"]))
  return unexpected_msgs


def read_skip_patterns_from_file(filename):
  """Read skip patterns from filename, ignoring comments and empty lines."""
  patterns = []
  with open(filename) as pfh:
    for line in pfh.readlines():
      line = line.strip()
      if line and not line.startswith("#"):
        patterns.append(line)
  return patterns


def real_main(argv):
  """The real main function, it just doesn't print anything or exit."""
  # __doc__ is written to pass pylint checks, so it must be changed before being
  # used as a usage message.
  usage = __doc__.rstrip().replace(".", "", 1)
  argv_parser = optparse.OptionParser(usage=usage, version="%prog 1.0")
  argv_parser.add_option(
      "--dryrun", action="store_true", dest="dryrun", default=False,
      help=textwrap.fill("""Perform a trial run with no changes made
                         (default: %default)"""))
  argv_parser.add_option(
      "--force", action="store_true", dest="force", default=False,
      help=textwrap.fill("""Remove existing files if necessary (default:
                         %default)"""))
  argv_parser.add_option(
      "--ignore_file", action="append", dest="ignore_file", metavar="FILENAME",
      default=[],
      help=textwrap.fill("""File containing shell patterns to ignore.  To
                         specify multiple filenames, use this option multiple
                         times."""))
  argv_parser.add_option(
      "--ignore_pattern", action="append", dest="ignore_pattern",
      metavar="FILENAME",
      default=[
          "CVS", ".git", ".gitignore", ".gitmodules", ".hg", ".svn", "*.swp"],
      help=textwrap.fill("""Extra shell patterns to ignore (appended to this
                         list: %default).  To specify multiple filenames, use
                         this option multiple times."""))
  argv_parser.add_option(
      "--ignore_unexpected_children", action="store_true",
      dest="ignore_unexpected_children", default=False,
      help=textwrap.fill("""When checking for unexpected files or directories,
                         ignore unexpected child directories in
                         DESTINATION_DIRECTORY; unexpected grandchild
                         directories of DESTINATION_DIRECTORY will not be
                         ignored (default: %default)"""))
  argv_parser.add_option(
      "--report_unexpected_files", action="store_true",
      dest="report_unexpected_files", default=False,
      help=textwrap.fill("""Report unexpected files in DESTINATION_DIRECTORY
                         (default: %default)"""))

  (options, args) = argv_parser.parse_args(argv[1:])
  if len(args) < 2:
    return ["Usage: %s [OPTIONS] SOURCE_DIR [SOURCE_DIR...] DEST_DIR"
            % argv[0]]

  ignore_patterns = options.ignore_pattern[:]
  for filename in options.ignore_file:
    ignore_patterns.extend(read_skip_patterns_from_file(filename))

  all_results = LinkResults([], [], [])
  unexpected_msgs = []
  dest = args.pop().rstrip(os.sep)
  if not os.path.isdir(dest):
    os.makedirs(dest)

  options.skip = ignore_patterns
  for source in args:
    source = source.rstrip(os.sep)
    all_results.extend(link_dir(source, dest, options))
  if options.report_unexpected_files:
    unexpected_msgs.extend(report_unexpected_files(
        dest, all_results.expected_files, options))

  return all_results.diffs + all_results.errors + unexpected_msgs


def main(argv):
  messages = real_main(argv)
  for line in messages:
    print line
  if messages:
    sys.exit(1)
  sys.exit(0)


if __name__ == "__main__":
  main(sys.argv)
