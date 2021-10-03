#!/usr/bin/env python3
"""%(prog)s [OPTIONS] SOURCE_DIRECTORY [...] DESTINATION_DIRECTORY

Link all files in SOURCE_DIRECTORY [SOURCE_DIRECTORY...] to
DESTINATION_DIRECTORY, creating the destination directory hierarchy where
necessary.
"""

import argparse
import dataclasses
import difflib
import filecmp
import fnmatch
import os
import pipes
import shutil
import stat
import sys
import textwrap
import time
from typing import List, Tuple

__author__ = 'johntobin@johntobin.ie (John Tobin)'

# Type definitions.
# A single path.
Path = str  # pragma: no mutate
# A list of directories, filenames, or paths.
Paths = List[str]  # pragma: no mutate
# Diffs between files.
Diffs = List[str]  # pragma: no mutate
# Messages to print.
Messages = List[str]  # pragma: no mutate
# Shell patterns to skip.
SkipPatterns = List[str]  # pragma: no mutate
# Command line args.
CommandLineArgs = List[str]  # pragma: no mutate


class Error(Exception):
  """Base class for exceptions."""


@dataclasses.dataclass
class UnexpectedPaths:
  """Container for unexpected paths.

  Attributes:
    files: unexpected files.
    directories: unexpected directories.
  """
  files: Paths
  directories: Paths


@dataclasses.dataclass
class LinkResults:
  """Container for the results of linking files and directories.

  Attributes:
    expected_files: files and directories that should exist in the destination.
    diffs: diffs between source and destination files.
    errors: error messages.
  """
  expected_files: Paths
  diffs: Diffs
  errors: Messages

  def extend(self, other) -> None:
    """Extend self with the data from other.

    Args:
      other: LinkResults, data to append.
    """
    self.expected_files.extend(other.expected_files)
    self.diffs.extend(other.diffs)
    self.errors.extend(other.errors)


def safe_unlink(unlink_me: Path, dryrun: bool) -> None:
  """Remove a file or directory, or print shell commands that would do so.

  Args:
    unlink_me: the file or directory to be removed.
    dryrun:    if True, shell commands are printed; if False, unlink_me is
               removed.

  Raises:
    OSError: there was a problem removing unlink_me.
  """

  if os.path.islink(unlink_me) or not os.path.isdir(unlink_me):
    if dryrun:
      print(f'rm {pipes.quote(unlink_me)}')
    else:
      os.unlink(unlink_me)
  else:
    if dryrun:
      print(f'rm -r {pipes.quote(unlink_me)}')
    else:
      shutil.rmtree(unlink_me)


def safe_link(source_filename: Path, dest_filename: Path, dryrun: bool) -> None:
  """Link one file to another, or print shell commands that would do so.

  Args:
    source_filename: existing filename.
    dest_filename:   new filename.
    dryrun:          if True, shell commands are printed; if False, files are
                     linked.
  Raises:
    OSError: there was a problem linking files.
  """

  if dryrun:
    print(f'ln {pipes.quote(source_filename)} {pipes.quote(dest_filename)}')
  else:
    os.link(source_filename, dest_filename)


def diff(old_filename: Path, new_filename: Path) -> Diffs:
  """Return a diff between old and new files.

  Args:
    old_filename: the original file.
    new_filename: the new file.

  Returns:
    An array of strings, possibly empty.

  Raises:
    OSError: an error occurred reading one of the files.
  """

  # pyfakefs doesn't seem to validate the mode, so stop mutating it.
  old_timestamp = time.ctime(os.stat(old_filename).st_mtime)
  new_timestamp = time.ctime(os.stat(new_filename).st_mtime)
  with open(old_filename, encoding='utf8') as old_fh:
    with open(new_filename, encoding='utf8') as new_fh:
      old_contents = old_fh.readlines()
      new_contents = new_fh.readlines()
      diff_generator = difflib.unified_diff(new_contents, old_contents,
                                            new_filename, old_filename,
                                            new_timestamp, old_timestamp)
      # Strip the newline here because one will be added later when printing the
      # messages.
      return [
          d.rstrip('\n')  # pragma: no mutate
          for d in diff_generator
      ]


def remove_skip_patterns(files: Paths, skip: SkipPatterns) -> Paths:
  """Remove any files matching shell patterns.

  Args:
    files: a list of filenames.
    skip: a list of shell patterns.

  Returns:
    An array of filenames.
  """

  unmatched = []
  skip_more = skip[:]
  skip_more.extend([os.sep.join(['*', pattern]) for pattern in skip])
  skip_more.extend([os.sep.join(['*', pattern, '*']) for pattern in skip])
  for filename in files:
    for pattern in skip_more:
      if fnmatch.fnmatch(filename, pattern):
        break
    else:
      unmatched.append(filename)
  return unmatched


def link_dir(source: Path, dest: Path,
             options: argparse.Namespace) -> LinkResults:
  """Recursively link files in source directory to dest directory.

  Args:
    source:  the source directory
    dest:    the destination directory
    options: options requested by the user.

  Returns:
    LinkResults.

  Raises:
    OSError: a filesystem operation failed.
  """

  results = LinkResults([], [], [])
  for directory, subdirs, files in os.walk(source):
    # Remove skippable subdirs.  Assigning to the slice will prevent os.walk
    # from descending into the skipped subdirs.
    subdirs[:] = remove_skip_patterns(subdirs, options.skip)
    subdirs.sort()
    for subdir in subdirs:
      source_dir = os.path.join(directory, subdir)
      dest_dir = source_dir.replace(source, dest, 1)
      results.expected_files.append(dest_dir)
      source_mode = stat.S_IMODE(os.stat(source_dir).st_mode)

      if os.path.isdir(dest_dir):
        dest_mode = stat.S_IMODE(os.stat(dest_dir).st_mode)
        if dest_mode == source_mode:
          continue
        if not options.dryrun:
          os.chmod(dest_dir, source_mode)
        else:
          mode = oct(source_mode).replace('o', '')
          print(f'chmod {mode} {pipes.quote(dest_dir)}')
        continue

      if os.path.exists(dest_dir):
        # Destination isn't a directory.
        if options.force:
          safe_unlink(dest_dir, options.dryrun)
        else:
          results.errors.append(f'{dest_dir} is not a directory')
          continue

      if options.dryrun:
        print(f'mkdir {pipes.quote(dest_dir)}')
      else:
        os.mkdir(dest_dir, source_mode)
        os.chmod(dest_dir, source_mode)

    results.extend(link_files(source, dest, directory, files, options))

  return results


def link_files(source: Path, dest: Path, directory: Path, files: Paths,
               options: argparse.Namespace) -> LinkResults:
  """Link files from source to dest.

  Args:
    source:    the toplevel source directory.
    dest:      the toplevel dest directory.
    directory: the directory the files are in, relative to source and dest.
    files:     the files in source/directory.
    options:   options requested by the user.

  Returns:
    LinkResults.  expected_files will not include files that are skipped.
  """

  results = LinkResults([], [], [])
  files = remove_skip_patterns(files, options.skip)
  files = [os.path.join(directory, filename) for filename in files]
  skip = [f'*{os.sep}{pattern}' for pattern in options.skip]
  files = remove_skip_patterns(files, skip)
  files.sort()
  for source_filename in files:
    dest_filename = source_filename.replace(source, dest, 1)
    results.expected_files.append(dest_filename)

    if os.path.islink(source_filename):
      # Skip source symlinks.
      if options.ignore_symlinks:
        # Work around coverage weirdness; this would be more natural:
        #   if not options.ignore_symlinks:
        #     append warning
        #   continue
        # But when I do that coverage reports that the if statement is never
        # false, but it is because the test that requires the log line passes.
        # Weird :(
        continue
      results.errors.append(f'Skipping symbolic link {source_filename}')
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
        results.errors.append(f'{dest_filename}: is not a file')
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
    # mypy doesn't understand this line.
    num_links = os.stat(dest_filename)[stat.ST_NLINK]  # type: ignore
    if num_links != 1:
      results.errors.append(f'{dest_filename}: link count is {num_links}')
      continue

    # Check for diffs.
    if filecmp.cmp(source_filename, dest_filename, shallow=False):
      print(f'{source_filename} and {dest_filename} are different files but'
            ' have the same contents; deleting and linking')
      safe_unlink(dest_filename, options.dryrun)
      safe_link(source_filename, dest_filename, options.dryrun)
      continue

    results.diffs.extend(diff(source_filename, dest_filename))

  return results


def report_unexpected_files(dest_dir: Path, expected_files_list: Paths,
                            options: argparse.Namespace) -> Messages:
  """Check for and maybe delete files in destdir that aren't in source_dir.

  Args:
    dest_dir: the destination directory.
    expected_files_list: files expected to exist in the destination.
    options: options requested by the user.

  Returns:
    Messages to print.
  """

  expected_files = set(expected_files_list)
  expected_files.add(dest_dir)

  unexpected_paths = UnexpectedPaths([], [])
  for directory, subdirs, files in os.walk(dest_dir):
    subdirs[:] = remove_skip_patterns(subdirs, options.skip)
    subdirs.sort()
    files = remove_skip_patterns(files, options.skip)
    files.sort()

    if directory == dest_dir and options.ignore_unexpected_children:
      unexpected = [
          subdir for subdir in subdirs
          if os.path.join(directory, subdir) not in expected_files
      ]
      for subdir in unexpected:
        subdirs.remove(subdir)

    full_subdirs = [os.path.join(directory, entry) for entry in subdirs]
    full_files = [os.path.join(directory, entry) for entry in files]
    full_subdirs = remove_skip_patterns(full_subdirs, options.skip)
    full_files = remove_skip_patterns(full_files, options.skip)
    unexpected_paths.directories.extend(
        [path for path in full_subdirs if path not in expected_files])
    unexpected_paths.files.extend(
        [path for path in full_files if path not in expected_files])

  msgs = []
  if options.delete_unexpected_files:
    msgs.extend(delete_unexpected_files(unexpected_paths, options))
  msgs.extend(format_unexpected_files(unexpected_paths))
  return msgs


def delete_unexpected_files(unexpected_paths: UnexpectedPaths,
                            options: argparse.Namespace) -> Messages:
  """Delete unexpected files, but not directories.

  Args:
    unexpected_paths: paths to process.
    options: options requested by the user.

  Returns:
    the messages to print.
  """

  for entry in unexpected_paths.files:
    safe_unlink(entry, options.dryrun)
  # Don't report files that have been deleted.
  unexpected_paths.files[:] = []
  if not unexpected_paths.directories:
    return []
  if not options.force:
    return [
        'Refusing to delete directories without --force/-f: ' +
        ' '.join(unexpected_paths.directories)
    ]
  # Descending sort by length, so that child directories are removed before
  # parent directories.
  unexpected_paths.directories.sort(key=len, reverse=True)
  for entry in unexpected_paths.directories:
    safe_unlink(entry, options.dryrun)
  # Don't report directories that have been deleted.
  unexpected_paths.directories[:] = []
  return []


def format_unexpected_files(unexpected_paths: UnexpectedPaths) -> Messages:
  """Format unexpected files and directories for output.

  Args:
    unexpected_paths: paths to process.

  Returns:
    Messages to print.
  """

  unexpected_paths.directories.sort()
  unexpected_paths.files.sort()
  unexpected_msgs = []
  unexpected_msgs.extend([
      f'Unexpected directory: {path}' for path in unexpected_paths.directories
  ])
  unexpected_msgs.extend(
      [f'Unexpected file: {path}' for path in unexpected_paths.files])
  if unexpected_paths.files:
    unexpected_msgs.append(f"rm {' '.join(unexpected_paths.files)}")
  if unexpected_paths.directories:
    # Descending sort by length, so that child directories are removed before
    # parent directories.
    unexpected_paths.directories.sort(key=len, reverse=True)
    unexpected_msgs.append(f"rmdir {' '.join(unexpected_paths.directories)}")
  return unexpected_msgs


def read_skip_patterns_from_file(filename: Path) -> SkipPatterns:
  """Read skip patterns from filename, ignoring comments and empty lines."""
  patterns = []
  with open(filename, encoding='utf8') as pfh:
    for line in pfh.readlines():
      line = line.strip()
      if line and not line.startswith('#'):
        patterns.append(line)
  return patterns


def parse_arguments(
    argv: CommandLineArgs) -> Tuple[argparse.Namespace, Messages]:
  """Parse the arguments provided by the user.

  Args:
    argv: the arguments to parse.
  Returns:
    argparse.Namespace, with attributes set based on the arguments.
  """
  # __doc__ is written to pass pylint checks, so it must be changed before being
  # used as a usage message.
  (usage, description) = __doc__.split('\n', maxsplit=1)
  argv_parser = argparse.ArgumentParser(
      description=description,
      usage=usage,
      formatter_class=argparse.RawDescriptionHelpFormatter)
  argv_parser.add_argument(
      '--dryrun',
      action='store_true',
      dest='dryrun',
      default=False,
      help=textwrap.fill("""Perform a trial run with no changes made
                         (default: %(default)s)"""))
  argv_parser.add_argument(
      '--force',
      action='store_true',
      dest='force',
      default=False,
      help=textwrap.fill("""Remove existing files if necessary (default:
                         %(default)s)"""))
  argv_parser.add_argument(
      '--ignore_file',
      action='append',
      dest='ignore_file',
      metavar='FILENAME',
      default=[],
      help=textwrap.fill("""File containing shell patterns to ignore.  To
                         specify multiple filenames, use this option multiple
                         times."""))
  argv_parser.add_argument(
      '--ignore_pattern',
      action='append',
      dest='ignore_pattern',
      metavar='FILENAME',
      # There is no signal from mutating these constants; I could add tests for
      # every one, but it doesn't help.
      default=[
          'CVS',
          '.git',
          '.gitignore',
          '.gitmodules',  # pragma: no mutate
          '.hg',
          '.svn',
          '*.swp'
      ],  # pragma: no mutate
      help=textwrap.fill("""Extra shell patterns to ignore (appended to this
                         list: %(default)s).  To specify multiple filenames, use
                         this option multiple times."""))
  argv_parser.add_argument(
      '--ignore_unexpected_children',
      action='store_true',
      dest='ignore_unexpected_children',
      default=False,
      help=textwrap.fill("""When checking for unexpected files or directories,
                         ignore unexpected child directories in
                         DESTINATION_DIRECTORY; unexpected grandchild
                         directories of DESTINATION_DIRECTORY will not be
                         ignored (default: %(default)s)"""))
  argv_parser.add_argument(
      '--report_unexpected_files',
      action='store_true',
      dest='report_unexpected_files',
      default=False,
      help=textwrap.fill("""Report unexpected files in DESTINATION_DIRECTORY
                         (default: %(default)s)"""))
  argv_parser.add_argument(
      '--delete_unexpected_files',
      action='store_true',
      dest='delete_unexpected_files',
      default=False,
      help=textwrap.fill("""Delete unexpected files in DESTINATION_DIRECTORY
                         (default: %(default)s)"""))
  argv_parser.add_argument(
      '--ignore_symlinks',
      action='store_true',
      dest='ignore_symlinks',
      default=False,
      help=textwrap.fill("""Ignore symlinks rather than reporting an error and
                         failing (default: %(default)s)"""))
  argv_parser.add_argument('args',
                           nargs='+',
                           metavar='DIRECTORIES',
                           default=[],
                           help='See usage for details')

  options = argv_parser.parse_args(argv[1:])
  messages = []
  if len(options.args) < 2:
    messages.append(usage % {'prog': argv[0]})
  if options.delete_unexpected_files and not options.ignore_unexpected_children:
    messages.append('Cannot enable --delete_unexpected_files without '
                    '--ignore_unexpected_children')
  return (options, messages)


def real_main(argv: CommandLineArgs) -> Messages:
  """The real main function, it just doesn't print anything or exit."""

  (options, messages) = parse_arguments(argv)
  if messages:
    return messages
  ignore_patterns = options.ignore_pattern[:]
  for filename in options.ignore_file:
    ignore_patterns.extend(read_skip_patterns_from_file(filename))

  all_results = LinkResults([], [], [])
  unexpected_msgs = []
  # When mutmut mutates these lines the tests take long enough for mutmut to
  # report them as suspicious, so disable mutations.
  dest = options.args.pop().rstrip(os.sep)  # pragma: no mutate
  if not os.path.isdir(dest):  # pragma: no mutate
    os.makedirs(dest)

  options.skip = ignore_patterns
  for source in options.args:
    source = source.rstrip(os.sep)
    all_results.extend(link_dir(source, dest, options))
  if options.report_unexpected_files or options.delete_unexpected_files:
    unexpected_msgs.extend(
        report_unexpected_files(dest, all_results.expected_files, options))

  return all_results.diffs + all_results.errors + unexpected_msgs


def main(argv: CommandLineArgs):
  messages = real_main(argv)
  for line in messages:
    print(line)
  if messages:
    sys.exit(1)
  sys.exit(0)


if __name__ == '__main__':  # pragma: no mutate
  main(sys.argv)
