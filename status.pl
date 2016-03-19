#!/usr/bin/perl
use IO::Socket;
use POSIX qw(strftime);
use strict;

sub readSHM {
	my ($file) = @_;
	$file = "/dev/shm/$file";
	open my $fh, '<', $file or return 0; #die "can't open $file: $!";
	my @lines = <$fh>;
	close $fh or die "can't close $file: $!";
	my $message = $lines[0];
	chomp $message;
#	printf(strftime("%Y%m%d_%H%M%S", localtime) . " $file: [$message]\n");
	return $message;
}

my $luminosity = readSHM("value_luminosity_luminosity");

my $sqm = readSHM("value_sqm_sqm");

my $BAA_sensor = readSHM("value_skytemperature-BAA_sensor");
my $BAA_object = readSHM("value_skytemperature-BAA_object");

my $BCC_sensor = readSHM("value_skytemperature-BCC_sensor");
my $BCC_object = readSHM("value_skytemperature-BCC_object");

my $raining = readSHM("state_raining");

my $ups_online = readSHM("state_ups_online");

my $raindrop_sum = readSHM("value_raindrop_sum");

my $imaging_computer_power = readSHM("state_relay3");
my $imaging_equipment_power = readSHM("state_relay4");
my $mount_power = readSHM("state_relay6");
my $roof_motor_power = readSHM("state_relay7");

my $state_roof_closed_sensor = readSHM("state_roof_closed_sensor");
my $state_roof_opened_sensor = readSHM("state_roof_opened_sensor");

#printf(strftime("%Y%m%d_%H%M%S", localtime) . " luminosity $luminosity\n");

if (    $roof_motor_power =~ 'low'
	 && $mount_power =~ 'low'
	 && $imaging_equipment_power =~ 'low'
	 && $imaging_computer_power =~ 'low' ) {
	print ". Roof Controller, Mount, Imaging Equipment and Computer are all off.\n";
} else {
	if ( $roof_motor_power =~ 'low' ) {
		print ". Roof motor controller is off\n";
	} else {
		print "I Roof motor controller is on.\n";
	}
	if ( $mount_power =~ 'low' ) {
		print ". Mount is off\n";
	} else {
		print "I Mount is on.\n";
	}
	if ( $imaging_equipment_power =~ 'low' ) {
		print ". Imaging equipment is off\n";
	} else {
		print "I Imaging equipment is on.\n";
	}
	if ( $imaging_computer_power =~ 'low' ) {
		print ". Imaging computer is off\n";
	} else {
		print "I Imaging computer is powered.\n";
	}
}

if ( $state_roof_closed_sensor =~ 'high' ) {
	print ". Roof is closed.\n";
} else {
	if ( $state_roof_opened_sensor =~ 'high' ) {
		print "I Roof is OPEN.\n";
	} else {
		print "X Roof state is UNKNOWN.\n";
	}
}

my $mustClose = 0;

if ( $luminosity <= 2.0 ) {
	print "- Luminosity $luminosity [lx] is dark enough.\n";
} else {
	print "X Luminosity $luminosity [lx] is too bright.\n";
	$mustClose++;
}

if ( $sqm >= 17.0 ) {
	print "- SQM $sqm [mag/arcsec^2] is dark enough.\n";
} else {
	print "X SQM $sqm [mag/arcsec^2] is too bright.\n";
	$mustClose++;
}

my $deltaBAA = sprintf("%0.2f", $BAA_sensor - $BAA_object);
if ( $deltaBAA >= 20.0 ) {
	print "- deltaBAA $deltaBAA [C] is clear enough.\n";
} else {
	print "X deltaBAA $deltaBAA [C] is too cloudy.\n";
	$mustClose++;
}

my $deltaBCC = sprintf("%0.2f", $BCC_sensor - $BCC_object);
if ( $deltaBCC >= 20.0 ) {
	print "- deltaBCC $deltaBCC [C] is clear enough.\n";
} else {
	print "X deltaBCC $deltaBCC [C] is too cloudy.\n";
	$mustClose++;
}

if ( $raindrop_sum == 0 ) {
	print "- It is dry for at least 1 hour.\n";
} else {
   	$mustClose++;
    if ( $raining == 0 ) {
    	print "X It is dry now, but it rained $raindrop_sum drops last hour.\n";
    } else {
    	print "X It is raining, $raindrop_sum drops last hour.\n";
    }
}

if ( $ups_online == 1 ) {
	print "- UPS is on mains.\n";
} else {
	print "X UPS is not on mains.\n";
	$mustClose++;
}

if ( $state_roof_closed_sensor =~ 'high' ) {
	if ( $mustClose == 0 ) {
		print "It is safe to open the roof !\n";
	} else {
		my $isare = "";
		if ( $mustClose == 1 ) {
			$isare = "is $mustClose reason";
		} else {
			$isare = "are $mustClose reasons";
		}
		print "There $isare to keep the roof closed !\n";
	}
} else {
	if ( $state_roof_opened_sensor =~ 'high' ) {
		if ( $mustClose == 0 ) {
			print "It is safe to keep the roof open !\n";
		} else {
			my $isare = "";
			if ( $mustClose == 1 ) {
				$isare = "is $mustClose reason";
			} else {
				$isare = "are $mustClose reasons";
			}
			print "There $isare to CLOSE THE ROOF !\n";
		}
	} else {
		print "Roof state UNKNOWN, we're better opening or closing the roof !\n";
	}
}

