#!/bin/bash

# rpi2 hazcam2

set -e
#set -x

cd /mnt/nas/rpi2/tmp/

TARGETPERIOD=60

AVERAGEVALUE=0
SHUTTERSPEED=2
SHUTTERSPEED=100000
SHUTTERSPEED=6000000
SHUTTERSPEED=1000000

while :; do 
	NOW=$(date '+%s')
	START=$NOW

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T shutterspeed = $SHUTTERSPEED"

	raspistill -v -n -ex verylong -mm spot -t 1000 -ss $SHUTTERSPEED -q 100 -ISO 800 -o ${T}-rpi2.jpg

	echo "cp ${T}-rpi2.jpg /mnt/live/hazcam2.jpg.tmp"
	cp ${T}-rpi2.jpg /mnt/live/hazcam2.jpg.tmp
	echo "mv /mnt/live/hazcam2.jpg.tmp /mnt/live/hazcam2.jpg"
	mv /mnt/live/hazcam2.jpg.tmp /mnt/live/hazcam2.jpg

#	AVERAGEVALUE=$(convert ${T}-rpi2.jpg -resize 1x1 txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
	AVERAGEVALUE=$(cat ${T}-rpi2.jpg|convert -crop 1750x1944 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
	echo "AVERAGEVALUE=$AVERAGEVALUE"

	echo "SHUTTERSPEED=$SHUTTERSPEED , adjust to :"
	if [[ $AVERAGEVALUE -lt 80 ]]; then
		if [[ $SHUTTERSPEED -gt 10000 ]]; then
			SHUTTERSPEED=$((SHUTTERSPEED + 500000))
		else
			SHUTTERSPEED=$((SHUTTERSPEED + 100))
		fi

		if [[ $SHUTTERSPEED -gt 6000000 ]]; then
			SHUTTERSPEED=6000000
		fi
	elif [[ $AVERAGEVALUE -gt 120 ]]; then
		if [[ $SHUTTERSPEED -gt 10000 ]]; then
			SHUTTERSPEED=$((SHUTTERSPEED - 500000))
		else
			SHUTTERSPEED=$((SHUTTERSPEED - 100))
		fi
		if [[ $SHUTTERSPEED -lt 1 ]]; then
			SHUTTERSPEED=1
		fi
	fi
	echo "SHUTTERSPEED=$SHUTTERSPEED"

    NOW=$(date '+%s')
    DIFF=$((NOW - START))
    if [[ $DIFF -ge $TARGETPERIOD ]]; then
		LATE=$((DIFF - TARGETPERIOD))
        echo "We're $LATE s late to meet the $TARGETPERIOD s period, sleep 10 anyway"
		sleep 10
    else
        MUSTSLEEP=$((TARGETPERIOD - DIFF))
        echo "Sleep $MUSTSLEEP s to match the $TARGETPERIOD s period"
        sleep $MUSTSLEEP
    fi

done

