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
import pprint
import shlex
import shutil
import stat
import sys
import textwrap
import time
from pathlib import Path

__author__ = "johntobin@johntobin.ie (John Tobin)"

# Type definitions.
# A list of directories, filenames, or paths.
Paths = list[Path]
# Diffs between files.
Diffs = list[str]
# Messages to print.
Messages = list[str]
# Shell patterns to skip.
SkipPatterns = list[str]


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

    def extend(self, other: "LinkResults") -> None:
        """Extend self with the data from other.

        Args:
            other: LinkResults, data to append.
        """
        self.expected_files.extend(other.expected_files)
        self.diffs.extend(other.diffs)
        self.errors.extend(other.errors)


@dataclasses.dataclass
class Options:
    """Commandline options."""

    args: list[str]
    debug: bool
    delete_unexpected_files: bool
    dryrun: bool
    force: bool
    ignore_symlinks: bool
    ignore_unexpected_children: bool
    report_unexpected_files: bool
    ignore_file: Paths
    skip: SkipPatterns


def options_from_args(args: argparse.Namespace) -> Options:
    """Parse command line arguments into an Options object.

    Args:
        args: command line arguments, not including argv[0].

    Returns:
        Options.
    """
    return Options(
        args=args.args,  # pyright: ignore [reportAny]
        debug=args.debug,  # pyright: ignore [reportAny]
        delete_unexpected_files=args.delete_unexpected_files,  # pyright: ignore [reportAny]
        dryrun=args.dryrun,  # pyright: ignore [reportAny]
        force=args.force,  # pyright: ignore [reportAny]
        ignore_symlinks=args.ignore_symlinks,  # pyright: ignore [reportAny]
        ignore_unexpected_children=args.ignore_unexpected_children,  # pyright: ignore [reportAny]
        report_unexpected_files=args.report_unexpected_files,  # pyright: ignore [reportAny]
        ignore_file=[Path(x) for x in args.ignore_file],  # pyright: ignore [reportAny]
        skip=args.ignore_pattern,  # pyright: ignore [reportAny]
    )


def safe_unlink(*, unlink_me: Path, dryrun: bool) -> None:
    """Remove a file or directory, or print shell commands that would do so.

    Args:
        unlink_me: the file or directory to be removed.
        dryrun:    if True, shell commands are printed; if False, unlink_me is
                              removed.

    Raises:
        OSError: there was a problem removing unlink_me.
    """

    if unlink_me.is_symlink() or not unlink_me.is_dir():
        if dryrun:
            print(f"rm {shlex.quote(str(unlink_me))}")
        else:
            try:
                unlink_me.unlink()
            except FileNotFoundError:
                #  Something else deleted the file, don't die.
                pass
    else:
        if dryrun:
            print(f"rm -r {shlex.quote(str(unlink_me))}")
        else:
            shutil.rmtree(unlink_me)


def safe_link(*, source_filename: Path, dest_filename: Path, dryrun: bool) -> None:
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
        print(
            f"ln {shlex.quote(str(source_filename))} {shlex.quote(str(dest_filename))}"
        )
    else:
        dest_filename.hardlink_to(source_filename)


def diff(*, old_filename: Path, new_filename: Path) -> Diffs:
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
    old_timestamp = time.ctime(old_filename.stat().st_mtime)
    new_timestamp = time.ctime(new_filename.stat().st_mtime)
    with old_filename.open(encoding="utf8") as old_fh:
        with new_filename.open(encoding="utf8") as new_fh:
            old_contents = old_fh.readlines()
            new_contents = new_fh.readlines()
            diff_generator = difflib.unified_diff(
                new_contents,
                old_contents,
                str(new_filename),
                str(old_filename),
                new_timestamp,
                old_timestamp,
            )
            # Strip the newline here because one will be added later when printing the
            # messages.
            return [d.rstrip("\n") for d in diff_generator]  # pragma: no mutate


def remove_skip_patterns(*, files: Paths, skip: SkipPatterns) -> Paths:
    """Remove any files matching shell patterns.

    Args:
        files: a list of filenames.
        skip: a list of shell patterns.

    Returns:
        An array of filenames.
    """

    unmatched: list[Path] = []
    skip_more = skip[:]
    skip_more.extend([os.sep.join(["*", pattern]) for pattern in skip])
    skip_more.extend([os.sep.join(["*", pattern, "*"]) for pattern in skip])
    for filename in files:
        for pattern in skip_more:
            if fnmatch.fnmatch(str(filename), pattern):
                break
        else:
            unmatched.append(filename)
    return unmatched


def link_dir(*, source: Path, dest: Path, options: Options) -> LinkResults:
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

    results = LinkResults(expected_files=[], diffs=[], errors=[])
    for directory_str, subdirs, files in os.walk(source):
        directory = Path(directory_str)
        # Remove skippable subdirs.  Assigning to the slice will prevent os.walk
        # from descending into the skipped subdirs.
        # remove_skip_patterns returns list[Path], but we need list[str] for os.walk.
        filtered_subdirs = remove_skip_patterns(
            files=[Path(s) for s in subdirs], skip=options.skip
        )
        subdirs[:] = [str(s) for s in filtered_subdirs]
        subdirs.sort()
        for subdir in subdirs:
            source_dir = directory / subdir
            dest_dir = dest / source_dir.relative_to(source)
            results.expected_files.append(dest_dir)
            source_mode = stat.S_IMODE(source_dir.stat().st_mode)

            if dest_dir.is_dir():
                dest_mode = stat.S_IMODE(dest_dir.stat().st_mode)
                if dest_mode == source_mode:
                    continue
                if not options.dryrun:
                    dest_dir.chmod(source_mode)
                else:
                    mode = oct(source_mode).replace("o", "")
                    print(f"chmod {mode} {shlex.quote(str(dest_dir))}")
                continue

            if dest_dir.exists():
                # Destination isn't a directory.
                if options.force:
                    safe_unlink(unlink_me=dest_dir, dryrun=options.dryrun)
                else:
                    results.errors.append(f"{dest_dir} is not a directory")
                    continue

            if options.dryrun:
                print(f"mkdir {shlex.quote(str(dest_dir))}")
            else:
                dest_dir.mkdir(mode=source_mode)
                dest_dir.chmod(source_mode)

        results.extend(
            link_files(
                source=source,
                dest=dest,
                directory=directory,
                files=[Path(f) for f in files],
                options=options,
            )
        )

    return results


def link_files(
    *,
    source: Path,
    dest: Path,
    directory: Path,
    files: Paths,
    options: Options,
) -> LinkResults:
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

    results = LinkResults(expected_files=[], diffs=[], errors=[])
    files = remove_skip_patterns(files=files, skip=options.skip)
    # warnings :(
    files = [
        directory / filename
        for filename in remove_skip_patterns(files=files, skip=options.skip)
    ]
    skip = [f"*{os.sep}{pattern}" for pattern in options.skip]
    files = remove_skip_patterns(files=files, skip=skip)
    files.sort()
    for source_filename in files:
        dest_filename = dest / source_filename.relative_to(source)
        results.expected_files.append(dest_filename)

        if source_filename.is_symlink():
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
            results.errors.append(f"Skipping symbolic link {source_filename}")
            continue

        if not dest_filename.exists() and not dest_filename.is_symlink():
            # Destination doesn't already exist, and it's not a dangling symlink, so
            # just link it.
            safe_link(
                source_filename=source_filename,
                dest_filename=dest_filename,
                dryrun=options.dryrun,
            )
            continue

        if dest_filename.is_symlink() or not dest_filename.is_file():
            # Destination exists and is not a file.
            if options.force:
                safe_unlink(unlink_me=dest_filename, dryrun=options.dryrun)
                safe_link(
                    source_filename=source_filename,
                    dest_filename=dest_filename,
                    dryrun=options.dryrun,
                )
            else:
                results.errors.append(f"{dest_filename}: is not a file")
            continue

        if source_filename.samefile(dest_filename):
            # The file is correctly linked.
            continue

        if options.force:
            # Don't bother checking anything if --force was used.
            safe_unlink(unlink_me=dest_filename, dryrun=options.dryrun)
            safe_link(
                source_filename=source_filename,
                dest_filename=dest_filename,
                dryrun=options.dryrun,
            )
            continue

        # If the destination is already linked don't change it without --force.
        num_links = dest_filename.stat().st_nlink
        if num_links != 1:
            results.errors.append(
                f"{dest_filename}: link count is {num_links}; is this file present "
                + "in multiple source directories?"
            )
            continue

        # Check for diffs.
        if filecmp.cmp(source_filename, dest_filename, shallow=False):
            print(
                f"{source_filename} and {dest_filename} are different files but"
                + " have the same contents; deleting and linking"
            )
            safe_unlink(unlink_me=dest_filename, dryrun=options.dryrun)
            safe_link(
                source_filename=source_filename,
                dest_filename=dest_filename,
                dryrun=options.dryrun,
            )
            continue

        results.diffs.extend(
            diff(old_filename=source_filename, new_filename=dest_filename)
        )

    return results


def report_unexpected_files(
    *, dest_dir: Path, expected_files_list: Paths, options: Options
) -> Messages:
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

    unexpected_paths = UnexpectedPaths(files=[], directories=[])
    for directory_str, subdirs, files in os.walk(dest_dir):
        directory = Path(directory_str)
        subdirs[:] = [
            str(s.name)
            for s in remove_skip_patterns(
                files=[Path(s) for s in subdirs], skip=options.skip
            )
        ]
        subdirs.sort()
        filtered_files = list(
            remove_skip_patterns(files=[Path(f) for f in files], skip=options.skip)
        )
        filtered_files.sort()

        if directory == dest_dir and options.ignore_unexpected_children:
            # Remove unexpected top-level directories.
            unexpected = [
                subdir
                for subdir in subdirs
                if (directory / subdir) not in expected_files
            ]
            for subdir in unexpected:
                subdirs.remove(subdir)

        full_subdirs = [directory / entry for entry in subdirs]
        full_files = [directory / entry for entry in filtered_files]
        full_subdirs = remove_skip_patterns(files=full_subdirs, skip=options.skip)
        full_files = remove_skip_patterns(files=full_files, skip=options.skip)

        if directory == dest_dir and options.ignore_unexpected_children:
            # Remove unexpected top-level symlinks.
            symlinks = [file for file in full_files if file.is_symlink()]
            full_files = list(set(full_files) - set(symlinks))

        unexpected_paths.directories.extend(
            sorted(set(full_subdirs) - set(expected_files))
        )
        unexpected_paths.files.extend(sorted(set(full_files) - set(expected_files)))

    msgs: Messages = []
    if options.delete_unexpected_files:
        msgs.extend(
            delete_unexpected_files(unexpected_paths=unexpected_paths, options=options)
        )
    msgs.extend(format_unexpected_files(unexpected_paths=unexpected_paths))
    return msgs


def delete_unexpected_files(
    *, unexpected_paths: UnexpectedPaths, options: Options
) -> Messages:
    """Delete unexpected files, but not directories.

    Args:
        unexpected_paths: paths to process.
        options: options requested by the user.

    Returns:
        the messages to print.
    """

    for entry in unexpected_paths.files:
        safe_unlink(unlink_me=entry, dryrun=options.dryrun)
    # Don't report files that have been deleted.
    unexpected_paths.files[:] = []
    if not unexpected_paths.directories:
        return []
    if not options.force:
        return [
            "Refusing to delete directories without --force/-f: "
            + " ".join([str(d) for d in unexpected_paths.directories])
        ]
    # Descending sort by length, so that child directories are removed before
    # parent directories.
    unexpected_paths.directories.sort(key=lambda p: len(str(p)), reverse=True)
    for entry in unexpected_paths.directories:
        safe_unlink(unlink_me=entry, dryrun=options.dryrun)
    # Don't report directories that have been deleted.
    unexpected_paths.directories[:] = []
    return []


def format_unexpected_files(*, unexpected_paths: UnexpectedPaths) -> Messages:
    """Format unexpected files and directories for output.

    Args:
        unexpected_paths: paths to process.

    Returns:
        Messages to print.
    """

    unexpected_paths.directories.sort()
    unexpected_paths.files.sort()
    unexpected_msgs: Messages = []
    unexpected_msgs.extend(
        [f"Unexpected directory: {path}" for path in unexpected_paths.directories]
    )
    unexpected_msgs.extend(
        [f"Unexpected file: {path}" for path in unexpected_paths.files]
    )
    if unexpected_paths.files:
        unexpected_msgs.append(
            "rm " + " ".join([shlex.quote(str(f)) for f in unexpected_paths.files])
        )
    if unexpected_paths.directories:
        # Descending sort by length, so that child directories are removed before
        # parent directories.
        unexpected_paths.directories.sort(key=lambda p: len(str(p)), reverse=True)
        unexpected_msgs.append(
            "rmdir "
            + " ".join([shlex.quote(str(d)) for d in unexpected_paths.directories])
        )
    return unexpected_msgs


def read_skip_patterns_from_file(*, filename: Path) -> SkipPatterns:
    """Read skip patterns from filename, ignoring comments and empty lines."""
    patterns: list[str] = []
    with filename.open(encoding="utf8") as pfh:
        for line in pfh.readlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def parse_arguments(*, argv: list[str]) -> tuple[Options, Messages]:
    """Parse the arguments provided by the user.

    Args:
        argv: the arguments to parse.
    Returns:
        argparse.Namespace, with attributes set based on the arguments.
    """
    # __doc__ is written to pass pylint checks, so it must be changed before being
    # used as a usage message.
    usage, description = str(__doc__).split("\n", maxsplit=1)
    argv_parser = argparse.ArgumentParser(
        description=description,
        usage=usage,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    argv_parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        dest="debug",
        default=False,
        help=textwrap.fill("Enable debug output (default: %(default)s)"),
    )
    argv_parser.add_argument(
        "--dryrun",
        action=argparse.BooleanOptionalAction,
        dest="dryrun",
        default=False,
        help=textwrap.fill(
            "Perform a trial run with no changes made (default: %(default)s)"
        ),
    )
    argv_parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        dest="force",
        default=False,
        help=textwrap.fill("Remove existing files if necessary (default: %(default)s)"),
    )
    argv_parser.add_argument(
        "--ignore_file",
        action="append",
        dest="ignore_file",
        metavar="FILENAME",
        default=[],
        help=textwrap.fill(
            """File containing shell patterns to ignore.  To specify multiple filenames,
            use this option multiple times."""
        ),
    )
    argv_parser.add_argument(
        "--ignore_pattern",
        action="append",
        dest="ignore_pattern",
        metavar="FILENAME",
        # There is no signal from mutating these constants; I could add tests for
        # every one, but it doesn't help.
        default=[
            "CVS",
            ".git",
            ".gitignore",
            ".gitmodules",  # pragma: no mutate
            ".hg",
            ".svn",
            "*.swp",
        ],  # pragma: no mutate
        help=textwrap.fill(
            """Extra shell patterns to ignore (appended to this list: %(default)s).
            To specify multiple filenames, use this option multiple times."""
        ),
    )
    argv_parser.add_argument(
        "--ignore_unexpected_children",
        action=argparse.BooleanOptionalAction,
        dest="ignore_unexpected_children",
        default=False,
        help=textwrap.fill("""When checking for unexpected files or directories,
               ignore unexpected child directories and symlinks in
               DESTINATION_DIRECTORY; unexpected grandchild
               directories of DESTINATION_DIRECTORY will not be
               ignored (default: %(default)s)"""),
    )
    argv_parser.add_argument(
        "--report_unexpected_files",
        action=argparse.BooleanOptionalAction,
        dest="report_unexpected_files",
        default=False,
        help=textwrap.fill(
            "Report unexpected files in DESTINATION_DIRECTORY (default: %(default)s)"
        ),
    )
    argv_parser.add_argument(
        "--delete_unexpected_files",
        action=argparse.BooleanOptionalAction,
        dest="delete_unexpected_files",
        default=False,
        help=textwrap.fill(
            "Delete unexpected files in DESTINATION_DIRECTORY (default: %(default)s)"
        ),
    )
    argv_parser.add_argument(
        "--ignore_symlinks",
        action=argparse.BooleanOptionalAction,
        dest="ignore_symlinks",
        default=False,
        help=textwrap.fill("""Ignore symlinks rather than reporting an error and failing
            (default: %(default)s)"""),
    )
    argv_parser.add_argument(
        "args",
        nargs="+",
        metavar="DIRECTORIES",
        default=[],
        help="See usage for details",
    )

    options = options_from_args(argv_parser.parse_args(argv[1:]))
    messages: Messages = []
    if len(options.args) < 2:
        messages.append(usage % {"prog": argv[0]})
    if options.delete_unexpected_files and not options.ignore_unexpected_children:
        messages.append(
            "Cannot enable --delete_unexpected_files without "
            + "--ignore_unexpected_children"
        )
    return (options, messages)


def real_main(*, argv: list[str]) -> Messages:
    """The real main function, it just doesn't print anything or exit."""

    options, messages = parse_arguments(argv=argv)
    if messages:
        return messages
    skip = options.skip[:]
    for filename in options.ignore_file:
        skip.extend(read_skip_patterns_from_file(filename=filename))
    options.skip = skip

    if options.debug:
        print("DEBUG: options:")
        pprint.pprint(dataclasses.asdict(options), indent=2, width=100)

    all_results = LinkResults(expected_files=[], diffs=[], errors=[])
    unexpected_msgs: Messages = []
    # When mutmut mutates these lines the tests take long enough for mutmut to
    # report them as suspicious, so disable mutations.
    dest = Path(options.args.pop().rstrip(os.sep))  # pragma: no mutate
    if not dest.is_dir():  # pragma: no mutate
        dest.mkdir(parents=True, exist_ok=True)

    for source in options.args:
        source_path = Path(source.rstrip(os.sep))
        all_results.extend(link_dir(source=source_path, dest=dest, options=options))
    if options.report_unexpected_files or options.delete_unexpected_files:
        unexpected_msgs.extend(
            report_unexpected_files(
                dest_dir=dest,
                expected_files_list=all_results.expected_files,
                options=options,
            )
        )

    return all_results.diffs + all_results.errors + unexpected_msgs


def main(*, argv: list[str]):
    messages = real_main(argv=argv)
    for line in messages:
        print(line)
    if messages:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":  # pragma: no mutate
    main(argv=list[str](sys.argv))
