#!/usr/bin/perl -w

sub read_code;

if (!$ARGV [0]) {
	die "Usage: $0 filename\n";
}

$total_code = $total_comment = $total_blank = 0;

while ( defined $ARGV [0] ) {
	if (!open FILE, "< $ARGV[0]") {
		die "Couldn't open $ARGV[0], $!\n";
	}
	print $ARGV [0], ":\n";
	$array = read_code ();
	$total_code = $total_code + $array->[0];
	$total_comment = $total_comment + $array->[1];
	$total_blank = $total_blank + $array->[2];
	shift @ARGV;
}

print STDOUT	"Total code:\n",
		$total_code, "\tlines of code\n",
		$total_comment, "\tlines of comments\n",
		$total_blank, "\tlines are blank\n",
		($total_code + $total_comment + $total_blank), 
			"\tlines in total\n";
exit ( 0 );

sub read_code {
	my ( $code, $blank, $comment );
	$code = $blank = $comment = 0;

	READ: while (<FILE>) {
		m,^\s*$, and ++$blank and next READ;
		m,^\s*//, and ++$comment and next READ;
		m,^\s*/\*.*\*/, and ++$comment and next READ;
		if (m,^\s*/\*,) {
			$comment++;
			while (<FILE>) {
				$comment++;
				m,\*/\s*$, and next READ;
			}
		next READ;
		}
		$code++;
	}

	print STDOUT	"\t$code lines of code, ",
			"$comment lines of comments,\n",
			"\t$blank lines are blank, ",
			" giving ", ($code + $comment + $blank), 
			" lines in total\n";

	return ( [ $code, $comment, $blank ] );
}
