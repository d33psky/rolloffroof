#!/usr/bin/perl
use POSIX qw(strftime);
use strict;
 
#apcaccess | egrep '^(STATUS|LINEV|LOADPCT|BCHARGE|TIMELEFT|BATTV|LINEFREQ|ITEMP)'
#STATUS   : ONLINE 
#LINEV    : 230.4 Volts
#LOADPCT  :   0.0 Percent Load Capacity
#BCHARGE  : 100.0 Percent
#TIMELEFT : 270.0 Minutes
#ITEMP    : 30.6 C Internal
#BATTV    : 27.4 Volts
#LINEFREQ : 50.0 Hz

sub readUPS {
	my ($rrdname) = @_;

	my $status = '';
	my $linev = '';
	my $loadpct = '';
	my $bcharge = '';
	my $timeleft = '';
	my $itemp = '';
	my $battv = '';
	my $linefreq = '';

	local *FH;
	open(FH, "apcaccess|") or die "Cannot open apcaccess: $!";
	while (<FH>) {
#		print $_;
		chomp;
		my $line = $_;
		if (m/^STATUS\s+:\s+(.*)$/) {
			my $statusstring = $1;
			if (m/ONLINE/) {
				$status = 1;
			} else {
				$status = 0;
			}
			next;
		}
		if (m/^LINEV\s+:\s+([\d\.]+)\s+Volts$/) {
			$linev = $1;
			next;
		}
		if (m/^LOADPCT\s+:\s+([\d\.]+)\s+Percent Load Capacity$/) {
			$loadpct = $1;
			next;
		}
		if (m/^BCHARGE\s+:\s+([\d\.]+)\s+Percent$/) {
			$bcharge = $1;
			next;
		}
		if (m/^TIMELEFT\s+:\s+([\d\.]+)\s+Minutes$/) {
			$timeleft = $1;
			next;
		}
		if (m/^ITEMP\s+:\s+([\d\.]+)\s+C Internal$/) {
			$itemp = $1;
			next;
		}
		if (m/^BATTV\s+:\s+([\d\.]+)\s+Volts$/) {
			$battv = $1;
			next;
		}
		if (m/^LINEFREQ\s+:\s+([\d\.]+)\s+Hz$/) {
			$linefreq = $1;
			next;
		}
	}
	close(FH) or die "ERROR: cannot close apcaccess: $!\n";

#	print "STATUS $status LINEV $linev LOADPCT $loadpct BCHARGE $bcharge TIMELEFT $timeleft ITEMP $itemp BATTV $battv LINEFREQ $linefreq\n";

	my $message = "update $rrdname.rrd -t status:linev:loadpct:bcharge:timeleft:itemp:battv:linefreq N:$status:$linev:$loadpct:$bcharge:$timeleft:$itemp:$battv:$linefreq";

	my $file = "/dev/shm/_rrdupdate_$rrdname";
	open my $fh, '>', $file or die "can't open $file: $!";
	print $fh "$message\n";
	close $fh or die "can't close $file: $!";
}

readUPS("ups");

