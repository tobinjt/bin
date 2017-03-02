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


# expected_files is a list of files and directories that should exist in the
# destination.  diffs is a list of diffs between source and destination files.
# errors is a list of error messages.
LinkResults = collections.namedtuple('LinkResults',
                                     'expected_files diffs errors')


def safe_unlink(unlink_me, dryrun=True):
  """Remove a file or directory, or return shell commands that would do so.

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


def link_dir(source, dest, skip, dryrun, force):
  """Recursively link files in source directory to dest directory.

  Args:
    source:       the source directory
    dest:         the destination directory
    skip:         files and directories under source that will be skipped.
    dryrun:       if true, the filesystem will not be changed; shell commands
                  will be printed instead.
    force:        existing files will be removed if necessary.  dryrun overrides
                  force.

  Returns:
    LinkResults.

  Raises:
    OSError:             a filesystem operation failed.
  """

  expected_files = []
  diffs = []
  errors = []
  for directory, subdirs, files in os.walk(source, topdown=True):
    # Remove skippable subdirs.  Assigning to the slice will prevent os.walk
    # from descending into the skipped subdirs.
    subdirs[:] = remove_skip_patterns(subdirs, skip)
    subdirs.sort()
    for subdir in subdirs:
      source_dir = os.path.join(directory, subdir)
      dest_dir = source_dir.replace(source, dest, 1)
      expected_files.append(dest_dir)
      source_stat = os.stat(source_dir)
      source_mode = stat.S_IMODE(source_stat.st_mode)

      if os.path.isdir(dest_dir):
        if not dryrun:
          os.chmod(dest_dir, source_mode)
        continue

      if os.path.exists(dest_dir):
        if force:
          safe_unlink(dest_dir, dryrun=dryrun)
        else:
          errors.append("%s is not a directory" % dest_dir)
          continue

      if dryrun:
        print "mkdir %s" % pipes.quote(dest_dir)
      else:
        os.mkdir(dest_dir, source_mode)
        os.chmod(dest_dir, source_mode)

    results = link_files(source, dest, directory, files,
                         dryrun=dryrun, force=force, skip=skip)
    expected_files.extend(results.expected_files)
    diffs.extend(results.diffs)
    errors.extend(results.errors)

  return LinkResults(expected_files, diffs, errors)


def link_files(source, dest, directory, files, dryrun, force, skip):
  """Link files from source to dest.

  Args:
    source:    the toplevel source directory.
    dest:      the toplevel dest directory.
    directory: the directory the files are in, relative to source and dest.
    files:     the files in source/directory.
    dryrun:    if true, the filesystem will not be changed.
    force:     existing files will be removed if necessary.  dryrun overrides
               force.
    skip:      a list of filenames to skip.

  Returns:
    LinkResults.  expected_files will not include files that are skipped.
  """

  expected_files = []
  diffs = []
  errors = []
  files = remove_skip_patterns(files, skip)
  files = [os.path.join(directory, filename) for filename in files]
  skip_more = ["*%s%s" % (os.sep, pattern) for pattern in skip]
  files = remove_skip_patterns(files, skip_more)
  for source_filename in files:
    dest_filename = source_filename.replace(source, dest, 1)
    expected_files.append(dest_filename)

    # To correctly fake things during a dryrun, we need to remember when we
    # delete a destination file.
    file_was_removed = False

    if (os.path.islink(dest_filename)
        or (os.path.exists(dest_filename)
            and not os.path.isfile(dest_filename))):
      if force:
        safe_unlink(dest_filename, dryrun=dryrun)
        file_was_removed = True
      else:
        errors.append("%s: is not a file" % dest_filename)
        continue

    if os.path.exists(dest_filename) and not file_was_removed:
      if os.path.samefile(source_filename, dest_filename):
        # The file is correctly linked.
        continue

      if not force:
        file_diffs = diff(source_filename, dest_filename)
        if not file_diffs:
          num_links = os.stat(dest_filename)[stat.ST_NLINK]
          if num_links != 1 and not force:
            errors.append("%s: link count is %d" % (dest_filename, num_links))
            continue
          print ("%s and %s are different files but have the same contents; "
                 "deleting and linking"
                 % (source_filename, dest_filename))
          safe_unlink(dest_filename, dryrun=dryrun)
          file_was_removed = True
        else:
          diffs.extend(file_diffs)

      if force and not file_was_removed:
        safe_unlink(dest_filename, dryrun=dryrun)
        file_was_removed = True

    if os.path.islink(source_filename):
      errors.append("Skipping symbolic link %s" % source_filename)
      continue
    if file_was_removed or not os.path.exists(dest_filename):
      if dryrun:
        print "ln %s %s" % (pipes.quote(source_filename),
                            pipes.quote(dest_filename))
      else:
        os.link(source_filename, dest_filename)

  return LinkResults(expected_files, diffs, errors)


def report_unexpected_files(dest_dir, expected_files_list, skip,
                            ignore_unexpected_children=False):
  """Check for files in destdir that aren't in source_dir.

  Args:
    dest_dir: the destination directory.
    expected_files_list: a list of files expected to exist in the destination.
    skip: files and directories under source that will be skipped.
    ignore_unexpected_children: Ignore unexpected top level directories.
                                Defaults to false.

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
    subdirs[:] = remove_skip_patterns(subdirs, skip)
    subdirs.sort()
    files = remove_skip_patterns(files, skip)
    files.sort()

    if directory == dest_dir and ignore_unexpected_children:
      unexpected = [subdir for subdir in subdirs
                    if os.path.join(directory, subdir) not in expected_files]
      for subdir in unexpected:
        subdirs.remove(subdir)

    full_subdirs = [os.path.join(directory, entry) for entry in subdirs]
    full_files = [os.path.join(directory, entry) for entry in files]
    skip_more = ["*%s%s" % (os.sep, pattern) for pattern in skip]
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
  for source in args:
    source = source.rstrip(os.sep)
    results = link_dir(source, dest, skip=ignore_patterns,
                       dryrun=options.dryrun, force=options.force)
    all_results.expected_files.extend(results.expected_files)
    all_results.diffs.extend(results.diffs)
    all_results.errors.extend(results.errors)
  if options.report_unexpected_files:
    unexpected_msgs.extend(report_unexpected_files(
        dest, expected_files_list=all_results.expected_files,
        skip=ignore_patterns,
        ignore_unexpected_children=options.ignore_unexpected_children))

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
