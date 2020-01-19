#!/bin/bash
# rpi3 allsky

set -e

cd /mnt/live/rpi3tmp/

TARGETPERIOD=60
AVERAGEVALUE=0
TARGETVALUE=128

SHUTTERSPEED=400000
SHUTTERSPEED=1
SHUTTERSPEED=100
SHUTTERSPEED=20
SHUTTERSPEED=10000
SHUTTERSPEED=1000000
SHUTTERSPEED=6000000

while :; do 
	NOW=$(date '+%s')
	START=$NOW

	T=$(date '+%Y%m%d_%H%M%S')
	FILENAMEDATE=$T
	echo "$T shutterspeed = $SHUTTERSPEED"

	ISO=800

	raspistill -v -n -ex verylong -mm spot -t 1000 -ss $SHUTTERSPEED -q 100 -ISO $ISO -o ${FILENAMEDATE}-rpi3.jpg
	# 2592x1944

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T composite /mnt/live/allsky-mask.png ${FILENAMEDATE}-rpi3.jpg  /mnt/live/allsky_temp2.jpg"
	composite /mnt/live/allsky-mask.png ${FILENAMEDATE}-rpi3.jpg /mnt/live/allsky_temp2.jpg

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T Calculate average"
    # ImageMagick pixel enumeration: 1,1,255,srgb
	AVERAGERGB=$(cat /mnt/live/allsky_temp2.jpg|convert -crop 1000x1000+796+472 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f %.0f %.0f\n", $1,$2,$3 }')
	RED=$(  echo $AVERAGERGB|cut -d' ' -f 1)
	GREEN=$(echo $AVERAGERGB|cut -d' ' -f 2)
	BLUE=$( echo $AVERAGERGB|cut -d' ' -f 3)
	AVERAGEVALUE=$(echo $AVERAGERGB|awk '{ printf "%.0f\n", ($1+$2+$3)/3 }')
	T=$(date '+%Y%m%d_%H%M%S')
	echo -n "$T RGB = $RED $GREEN $BLUE AVERAGE=$AVERAGEVALUE "
	OLDSHUTTERSPEED=$SHUTTERSPEED
	DELTAAVERAGEVALUE=$((TARGETVALUE - AVERAGEVALUE)) # range: 128-1=127, or 128-255=-127
	DELTAFACTOR=$((1 + (OLDSHUTTERSPEED/200))) # range 1..3001
	SHUTTERSPEED=$((SHUTTERSPEED + (DELTAFACTOR * DELTAAVERAGEVALUE)))
	echo "DELTAAVERAGE=$DELTAAVERAGEVALUE DELTAFACTOR=$DELTAFACTOR SHUTTERSPEED=${OLDSHUTTERSPEED}->${SHUTTERSPEED}"

	if [[ $SHUTTERSPEED -gt 6000000 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too large, set to max 6000000"
		SHUTTERSPEED=6000000
	elif [[ $SHUTTERSPEED -lt 1 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too small, set to min 1"
		SHUTTERSPEED=1
	fi

	if [[ $OLDSHUTTERSPEED -eq 6000000 && $AVERAGEVALUE -lt 20 ]]; then
		T=$(date '+%Y%m%d_%H%M%S')
		echo "$T count stars"
#S=$(cat /mnt/live/allsky_temp2.jpg|jpegtopnm 2>/dev/null|ppmtopgm|convert -crop 1000x1000+796+472 - - |convert - crop.fits && image2xy -O -g 9 crop-0.fits|awk '{ print $3 }')
		S=$(cat /mnt/live/allsky_temp2.jpg|jpegtopnm 2>/dev/null|ppmtopgm|convert -crop 1000x1000+796+472 - - |convert - crop.fits && image2xy -O -g 9 crop.fits|awk '{ print $3 }')
		echo "stars=[$S]"
	else
		echo "$T it is too bright, do not bother counting stars"
		S=0
	fi

	if [[ $RED -eq 0 && $GREEN -gt 200 && $BLUE -eq 0 ]]; then
        echo "ANOMALY correct, set to min 100"
        SHUTTERSPEED=100
    fi

	T=$(date '+%Y%m%d_%H%M%S')
    NOW=$(date '+%s')
    DIFF=$((NOW - START))
    if [[ $DIFF -ge $TARGETPERIOD ]]; then
		LATE=$((DIFF - TARGETPERIOD))
        echo "$T We're $LATE s late to meet the $TARGETPERIOD s period, sleep 10 anyway"
		SLEEP=10
    else
        MUSTSLEEP=$((TARGETPERIOD - DIFF))
        echo "$T Sleep $MUSTSLEEP s to match the $TARGETPERIOD s period"
		SLEEP=$MUSTSLEEP
    fi

	OLDEXPOSURE=$(/bin/echo "scale=6; $OLDSHUTTERSPEED/1000000" | /usr/bin/bc -l)
	NEWEXPOSURE=$(/bin/echo "scale=6; $SHUTTERSPEED/1000000" | /usr/bin/bc -l)
	LINE="allskycam1 rpi3\n$(date -u '+%Y-%m-%dT%H:%M:%SZ')\nRGB $RED $GREEN $BLUE ($AVERAGEVALUE)\nExposure $OLDEXPOSURE s\n (next $NEWEXPOSURE)\nISO $ISO\n (next $ISO)\nStars $S\nSleep $SLEEP s"
	echo "$T convert /mnt/live/allsky_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/allsky_temp3.jpg"
	convert /mnt/live/allsky_temp2.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" /mnt/live/allsky_temp3.jpg

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T mv /mnt/live/allsky_temp3.jpg /mnt/live/allsky.jpg"
	mv /mnt/live/allsky_temp3.jpg /mnt/live/allsky.jpg

	/usr/bin/logger -t ${0##*/} -i "Exposure $OLDEXPOSURE s, Average $AVERAGEVALUE, Factor $DELTAFACTOR new exposure $NEWEXPOSURE s"

    cp /mnt/live/allsky.jpg /mnt/live/rpi3tmp/${FILENAMEDATE}-rpi3b.jpg

	echo "update allskycamstars.rrd -t stars N:$S > /dev/shm/rrdupdate_allskycamstars"
	echo "update allskycamstars.rrd -t stars N:$S" > /dev/shm/rrdupdate_allskycamstars

	T=$(date '+%Y%m%d_%H%M%S')
	if [[ $MUSTGOFAST -eq 1 ]]; then
		echo "$T MUSTGOFAST, skip sleep $SLEEP"
		continue
	else
		echo "$T sleep $SLEEP"
		sleep $SLEEP
	fi

done

