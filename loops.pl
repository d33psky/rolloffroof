#!/usr/bin/perl
use IO::Socket;
use POSIX qw(strftime);
use strict;
 
# Remote RRD server and port
my $rrd_server = "192.168.100.81";
my $port = 7777;
 
sub sendToRRD ($) {
	my $message = shift;

	my $socket = IO::Socket::INET->new(PeerAddr=> $rrd_server,
									PeerPort=> $port,
									Proto=> 'tcp',
									Type=> SOCK_STREAM)
		or die "Can't talk to $rrd_server at $port";

	print $socket "$message";

	close $socket;
}

sub readTempAndHumidity {
	my($rrdname, $pin, $f1, $f2) = @_;

	my $humidity = '';
	my $temperature = '';
	my $dht=`./loldht $pin`;
	print $dht;
	$_ = $dht;
	# pin 8 Humidity = 53.50 % Temperature = 8.50 *C 
	m/.*Humidity = (.*) . Temperature = (.*) .C/ && do {
		$temperature = sprintf("%0.2f", $2 + $f1);
		$humidity = sprintf("%0.2f", $1 + $f2);
	};
	my $gamma = ( (17.27 * $temperature) / (237.7 + $temperature) ) + log (($humidity + 0.001)/ 100);
	my $dewpoint = sprintf("%0.2f", (237.7 * $gamma) / (17.27 - $gamma));
	my $message = "update $rrdname.rrd -t temperature:humidity:dewpoint N:$temperature:$humidity:$dewpoint";

	my $file = "/dev/shm/rrdupdate_$rrdname";
	open my $fh, '>', $file or die "can't open $file: $!";
	print $fh "$message\n";
	close $fh or die "can't close $file: $!";

	$file = "/dev/shm/value_" . $rrdname . "_temperature";
	open $fh, '>', $file or die "can't open $file: $!";
	print $fh "$temperature\n";
	close $fh or die "can't close $file: $!";

	$file = "/dev/shm/value_" . $rrdname . "_humidity";
	open $fh, '>', $file or die "can't open $file: $!";
	print $fh "$humidity\n";
	close $fh or die "can't close $file: $!";

	$file = "/dev/shm/value_" . $rrdname . "_dewpoint";
	open $fh, '>', $file or die "can't open $file: $!";
	print $fh "$dewpoint\n";
	close $fh or die "can't close $file: $!";
}

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
		if (m/^LOADPCT\s+:\s+([\d\.]+)\s+Percent.*$/) {
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
		if (m/^ITEMP\s+:\s+([\d\.]+)\s+C.*$/) {
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

	print "STATUS $status LINEV $linev LOADPCT $loadpct BCHARGE $bcharge TIMELEFT $timeleft ITEMP $itemp BATTV $battv LINEFREQ $linefreq\n";

	my $message = "update $rrdname.rrd -t status:linev:loadpct:bcharge:timeleft:itemp:battv:linefreq N:$status:$linev:$loadpct:$bcharge:$timeleft:$itemp:$battv:$linefreq";

	my $file = "/dev/shm/rrdupdate_$rrdname";
	open my $fh, '>', $file or die "can't open $file: $!";
	print $fh "$message\n";
	close $fh or die "can't close $file: $!";

	$file = "/dev/shm/state_ups_online";
	open $fh, '>', $file or die "can't open $file: $!";
	print $fh "$status\n";
	close $fh or die "can't close $file: $!";

}

# Drain /dev/shm/cloud_sensor_safety_event if readAllMyI2cDevices wrote one.
# Posts a critical Mattermost alert (@hans pushes to phone), then unlinks
# the flag so we don't spam — readAllMyI2cDevices only writes on transition.
sub checkSafetyAlert {
	my $flag = "/dev/shm/cloud_sensor_safety_event";
	return unless -e $flag;

	open my $fh, '<', $flag or do { unlink $flag; return; };
	my $body = do { local $/; <$fh> };
	close $fh;
	chomp $body;

	my $url_file = '/root/.mattermosturl-observatory';
	unless (-e $url_file) {
		warn "$url_file missing, dropping safety alert: $body\n";
		unlink $flag;
		return;
	}
	open my $uf, '<', $url_file or do { unlink $flag; return; };
	my $url = <$uf>;
	close $uf;
	chomp $url;

	# Match the format used by controller.py + observatorylib:
	# ":rotating_light: [ISO8601-UTC source] @hans message"
	my $ts = strftime("%Y-%m-%dT%H:%M:%S", gmtime) . ".000Z";
	# JSON-escape the body (it's controlled by us but be defensive)
	my $body_json = $body;
	$body_json =~ s/\\/\\\\/g;
	$body_json =~ s/"/\\"/g;
	my $text = ":rotating_light: [$ts cloud-sensor] \@hans Cap over-temp safety: $body_json";
	my $payload = qq({"text": "$text"});

	# List-form system() bypasses the shell -> no quoting pitfalls
	system("curl", "-s", "--max-time", "10",
	       "--data-urlencode", "payload=$payload", $url);
	unlink $flag;
}

while (1) {
	my $startdate = time;

	printf( strftime("%Y%m%d_%H%M%S", localtime) ." getting data:\n");

# Both indoor/outdoor DHT22 sensors are b0rken — pin 15 (outside, dead since 2020,
# resurrected via AHT21B at the pole base in readAllMyI2cDevices.c) and pin 16
# (observatory, reads garbage like Humidity=1.00% and stalls loldht). Read both
# is disabled here. See ~/infra/docs/astro/todo-options.md for the AHT21B
# replacement plan.
#	printf(strftime("%Y%m%d_%H%M%S", localtime) ." read tempandhum-outside pin 15:\n");
#	readTempAndHumidity("tempandhum-outside", "15", "0.0", "0.0");

#	printf(strftime("%Y%m%d_%H%M%S", localtime) ." read tempandhum-observatory pin 16:\n");
#	readTempAndHumidity("tempandhum-observatory", "16", "0.0", "14.0");
	printf(strftime("%Y%m%d_%H%M%S", localtime) ." read_TSL237_pigpio :\n");
	system("./read_TSL237_pigpio") == 0 or die "read_TSL237_pigpio failed!";
	printf(strftime("%Y%m%d_%H%M%S", localtime) ." readAllMyI2cDevices :\n");
	system("./readAllMyI2cDevices") == 0 or die "readAllMyI2cDevices failed!";
	checkSafetyAlert();
	printf(strftime("%Y%m%d_%H%M%S", localtime) ." read ups :\n");
	readUPS("ups");

	printf(strftime("%Y%m%d_%H%M%S", localtime) ." Done reading, send rrds:\n");
	while ( </dev/shm/rrdupdate*> ) {
		my $file = $_;
		open my $fh, '<', $file or die "can't open $file: $!";
		my @lines = <$fh>;
		close $fh or die "can't close $file: $!";
		my $message = $lines[0];
		chomp $message;
		printf(strftime("%Y%m%d_%H%M%S", localtime) . " $_: [$message]\n");
		sendToRRD($message);
	}

	my $enddate = time;

	my $seconds = 60 - ($enddate - $startdate);
	printf(strftime("%Y%m%d_%H%M%S", localtime) . " sleep $seconds s\n");
	sleep $seconds;
}

