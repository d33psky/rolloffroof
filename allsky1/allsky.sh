#!/bin/bash

# 20161013_200927 root@rpi3:~/ cd /mnt/nas/tmp/ && while :;do T=$(date '+%Y%m%d_%H%M%S'); echo $T;raspistill -v -n -ex verylong -mm spot -t 1000 -ss 6000000 -q 100 -ISO 800 -o ${T}-rpi3.jpg;echo "count stars";S=$(cat ${T}-rpi3.jpg|jpegtopnm 2>/dev/null|ppmtopgm|convert -crop 1750x1944 - - |convert - crop.fits && image2xy -O -g 9 crop-0.fits|awk '{ print $3 }');echo "stars=[$S]";echo "update allskycamstars.rrd -t stars N:$S" > /dev/shm/rrdupdate_allskycamstars;echo "sleep 10";sleep 10;done

#what controls the shutter time ?
# it's based currently on the average adu in the images
# so exposure time increments work like this
# 0.001 second bumps when exposure is less than 0.02
# then 0.01 bumps when it's less than 0.2
# then 0.1 bumps when less than 2
# and above 2 seconds, it uses one second bumps
# if average > 20000 bump down
# if average is < 1000 bump up
# clamp on the ends at 0.001 and 15 seconds

set -e
#set -x

cd /mnt/nas/tmp/

TARGETPERIOD=60

AVERAGEVALUE=0
SHUTTERSPEED=6000000
SHUTTERSPEED=1
SHUTTERSPEED=400000
SHUTTERSPEED=100

while :; do 
	NOW=$(date '+%s')
	START=$NOW

	T=$(date '+%Y%m%d_%H%M%S')
	echo $T

	ISO=800

	raspistill -v -n -ex verylong -mm spot -t 1000 -ss $SHUTTERSPEED -q 100 -ISO $ISO -o ${T}-rpi3.jpg

#	AVERAGEVALUE=$(convert ${T}-rpi3.jpg -resize 1x1 txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
	echo "Calculate average"
	AVERAGEVALUE=$(cat ${T}-rpi3.jpg|convert -crop 1750x1944 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
	echo "AVERAGEVALUE=$AVERAGEVALUE"

	if [[ $SHUTTERSPEED -eq 6000000 && $AVERAGEVALUE -lt 20 ]]; then
		echo "count stars"
		S=$(cat ${T}-rpi3.jpg|jpegtopnm 2>/dev/null|ppmtopgm|convert -crop 1750x1944 - - |convert - crop.fits && image2xy -O -g 9 crop-0.fits|awk '{ print $3 }')
		echo "stars=[$S]"
	else
		echo "SHUTTERSPEED/AVERAGEVALUE combo is too bright, do not bother counting stars"
		S=0
	fi

	OLDSHUTTERSPEED=$SHUTTERSPEED
	echo -n "SHUTTERSPEED=$SHUTTERSPEED , adjust to "
#	if [[ $AVERAGEVALUE -le 10 ]]; then
#		SHUTTERSPEED=6000000
#	elif [[ $AVERAGEVALUE -lt 90 ]]; then
#		if [[ $SHUTTERSPEED -gt 10000 ]]; then
#			SHUTTERSPEED=$((SHUTTERSPEED + 1000000))
#		else
#			SHUTTERSPEED=$((SHUTTERSPEED + 100))
#		fi
#
#		if [[ $SHUTTERSPEED -gt 6000000 ]]; then
#			SHUTTERSPEED=6000000
#		fi
#	elif [[ $AVERAGEVALUE -ge 250 ]]; then
#		SHUTTERSPEED=1
#	elif [[ $AVERAGEVALUE -gt 110 ]]; then
#		if [[ $SHUTTERSPEED -gt 10000 ]]; then
#			SHUTTERSPEED=$((SHUTTERSPEED - 1000000))
#		else
#			SHUTTERSPEED=$((SHUTTERSPEED - 100))
#		fi
#		if [[ $SHUTTERSPEED -lt 1 ]]; then
#			SHUTTERSPEED=1
#		fi
#	fi
 	if [[ $AVERAGEVALUE -le 10 ]]; then
 		SHUTTERSPEED=6000000
		MUSTGOFAST=1
 	elif [[ $AVERAGEVALUE -lt 90 ]]; then
		MUSTGOFAST=0
 		if [[ $SHUTTERSPEED -gt 10000 ]]; then
 			SHUTTERSPEED=$((SHUTTERSPEED + 1000000))
 		else
 			SHUTTERSPEED=$((SHUTTERSPEED + 100))
 		fi
 	elif [[ $AVERAGEVALUE -ge 250 ]]; then
 		SHUTTERSPEED=1
		MUSTGOFAST=1
 	elif [[ $AVERAGEVALUE -gt 110 ]]; then
		MUSTGOFAST=0
 		if [[ $SHUTTERSPEED -gt 10000 ]]; then
 			SHUTTERSPEED=$((SHUTTERSPEED - 1000000))
 		else
 			SHUTTERSPEED=$((SHUTTERSPEED - 100))
 		fi
 	fi

	if [[ $SHUTTERSPEED -gt 6000000 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too large, set to max 6000000"
		SHUTTERSPEED=6000000
	elif [[ $SHUTTERSPEED -lt 1 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too small, set to min 1"
		SHUTTERSPEED=1
	else
		echo "SHUTTERSPEED=$SHUTTERSPEED"
	fi

	echo "cp ${T}-rpi3.jpg /mnt/live/allsky_temp.jpg"
	cp ${T}-rpi3.jpg /mnt/live/allsky_temp.jpg

	echo "composite /mnt/live/allsky-mask.png /mnt/live/allsky_temp.jpg /mnt/live/allsky_temp2.jpg"
	composite /mnt/live/allsky-mask.png /mnt/live/allsky_temp.jpg /mnt/live/allsky_temp2.jpg

    NOW=$(date '+%s')
    DIFF=$((NOW - START))
    if [[ $DIFF -ge $TARGETPERIOD ]]; then
		LATE=$((DIFF - TARGETPERIOD))
        echo "We're $LATE s late to meet the $TARGETPERIOD s period, sleep 10 anyway"
		SLEEP=10
    else
        MUSTSLEEP=$((TARGETPERIOD - DIFF))
        echo "Sleep $MUSTSLEEP s to match the $TARGETPERIOD s period"
		SLEEP=$MUSTSLEEP
    fi

	OLDEXPOSURE=$(/bin/echo "scale=6; $OLDSHUTTERSPEED/1000000" | /usr/bin/bc -l)
	NEWEXPOSURE=$(/bin/echo "scale=6; $SHUTTERSPEED/1000000" | /usr/bin/bc -l)
	LINE="allskycam1 rpi3\n$(date -u '+%Y-%m-%dT%H:%M:%SZ')\nAverage pixel value = $AVERAGEVALUE\nExposure $OLDEXPOSURE s\n (next $NEWEXPOSURE)\nISO=$ISO\n (next $ISO)\nStars = $S\nSleep $SLEEP s"
	echo "convert /mnt/live/allsky_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/allsky_temp3.jpg"
	convert /mnt/live/allsky_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/allsky_temp3.jpg

	echo "mv /mnt/live/allsky_temp3.jpg /mnt/live/allsky.jpg"
	mv /mnt/live/allsky_temp3.jpg /mnt/live/allsky.jpg

	/usr/bin/logger -t ${0##*/} -i "ShutterSpeed $OLDSHUTTERSPEED resulted in AverageValue $AVERAGEVALUE, new ShutterSpeed $SHUTTERSPEED"

	echo "update allskycamstars.rrd -t stars N:$S > /dev/shm/rrdupdate_allskycamstars"
	echo "update allskycamstars.rrd -t stars N:$S" > /dev/shm/rrdupdate_allskycamstars

	if [[ $MUSTGOFAST -eq 1 ]]; then
		continue
	fi

	echo "sleep $SLEEP"
	sleep $SLEEP

done

