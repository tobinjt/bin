#!/usr/bin/env perl -w

# this program just counts how many lines of code, lines of comments, and 
# blank lines there are in your program.
# comments are on a line by themselves, e.g.
		# this is a comment
# but: $blah = pop @blah; # this is code
# coz i reckon the former is easier to read

# $Id$

use strict;
use warnings;

use IO::File;

sub read_pod ($$);

$ARGV [0] or die "Usage: $0 filename\n";
my $file = new IO::File "< $ARGV[0]" or die "Couldn't open $ARGV[0], $!\n";
my ( $code, $blank, $comment, $pod ) = ( 0, 0, 0, 0 );

while (<$file>) {
	m/^\s*$/ and ++$blank and next;
	m/^\s*\#/ and ++$comment and next;
	m/^=(pod|head[1-4]|over|item|back|for|begin|end)/o 
			and read_pod ($file, \$pod)
			and next;
	$code++;
}

print STDOUT	$ARGV [0], ":\n", 
		$code, "\tlines of code\n",
		$comment, "\tlines of comments\n",
		$pod, "\tlines of pod\n",
		$blank, "\tlines are blank\n",
		($code + $comment + $pod + $blank), "\tlines in total\n";

sub read_pod ($$) {
	my ( $file, $pod ) = @_;

	$$pod++;
	while ( <$file> ) {
		$$pod++;
		m/^=cut/ and last;
	}
	return 1;
}
