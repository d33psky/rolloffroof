#!/bin/bash

# rpi2 hazcam2

set -e
#set -x

cd /mnt/nas/rpi2/tmp/

TARGETPERIOD=60

AVERAGEVALUE=0
SHUTTERSPEED=2
SHUTTERSPEED=6000000
SHUTTERSPEED=4000000
SHUTTERSPEED=100000

ISO=800

while :; do 
	NOW=$(date '+%s')
	START=$NOW

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T shutterspeed = $SHUTTERSPEED"

	raspistill -v -n -ex verylong -mm spot -t 1000 -ss $SHUTTERSPEED -q 100 -ISO $ISO -o ${T}-rpi2.jpg

	echo "Calculate average"
    # ImageMagick pixel enumeration: 1,1,255,srgb
    #AVERAGEVALUE=$(cat ${T}-rpi2.jpg|convert -crop 1750x1944 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
    # ImageMagick pixel enumeration: 1,1,65535,srgb
	AVERAGEVALUE=$(cat ${T}-rpi2.jpg|convert -crop 1750x1944 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", 256*(($1+$2+$3)/3)/65535 }')
	echo "AVERAGEVALUE=$AVERAGEVALUE"

	OLDSHUTTERSPEED=$SHUTTERSPEED
	echo "SHUTTERSPEED=$SHUTTERSPEED , adjust to :"
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

	echo "cp ${T}-rpi2.jpg /mnt/live/hazcam2_temp2.jpg"
	cp ${T}-rpi2.jpg /mnt/live/hazcam2_temp2.jpg

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
	LINE="hazcam2 rpi2\n$(date -u '+%Y-%m-%dT%H:%M:%SZ')\nAverage pixel value = $AVERAGEVALUE\nExposure $OLDEXPOSURE s\n (next $NEWEXPOSURE)\nISO=$ISO\n (next $ISO)\nSleep $SLEEP s"
	echo "convert /mnt/live/hazcam2_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/hazcam2_temp3.jpg"
	convert /mnt/live/hazcam2_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/hazcam2_temp3.jpg

	echo "mv /mnt/live/hazcam2_temp3.jpg /mnt/live/hazcam2.jpg"
	mv /mnt/live/hazcam2_temp3.jpg /mnt/live/hazcam2.jpg

	if [[ $MUSTGOFAST -eq 1 ]]; then
        echo "do not sleep $SLEEP because MUSTGOFAST is set"
		continue
	fi

	echo "sleep $SLEEP"
	sleep $SLEEP

done

