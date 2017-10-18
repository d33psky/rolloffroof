#!/bin/bash

# rpi2 hazcam2

set -e

CAMNAME="hazcam2"
CAMHOST="rpi2"

COMMAND="cd /mnt/nas/${CAMHOST}/tmp/"
T=$(date '+%Y%m%d_%H%M%S') ; echo "$T $COMMAND" ; $COMMAND
LIVEDIR="/mnt/live"

TARGETPERIOD=60
AVERAGEVALUE=0
TARGETVALUE=128

SHUTTERSPEED=400000
SHUTTERSPEED=1
SHUTTERSPEED=100
SHUTTERSPEED=20
SHUTTERSPEED=10000
SHUTTERSPEED=6000000
SHUTTERSPEED=1000000

while :; do 
	NOW=$(date '+%s')
	START=$NOW

	T=$(date '+%Y%m%d_%H%M%S')
	FILENAMEDATE=$T
	ISO=800
	echo "$T shutterspeed = $SHUTTERSPEED ISO = $ISO"

    COMMAND="raspistill -v -n -ex verylong -mm spot -t 1000 -ss $SHUTTERSPEED -q 100 -ISO $ISO -o ${FILENAMEDATE}-${CAMHOST}.jpg"
    T=$(date '+%Y%m%d_%H%M%S') ; echo "$T $COMMAND" ; $COMMAND
	# 2592x1944

#	T=$(date '+%Y%m%d_%H%M%S')
#	echo "$T composite ${LIVEDIR}/${CAMNAME}-mask.png ${FILENAMEDATE}-${CAMHOST}.jpg  ${LIVEDIR}/${CAMNAME}_temp2.jpg"
#	composite ${LIVEDIR}/${CAMNAME}-mask.png ${FILENAMEDATE}-${CAMHOST}.jpg ${LIVEDIR}/${CAMNAME}_temp2.jpg

	T=$(date '+%Y%m%d_%H%M%S')
	echo "$T Calculate average"
    # ImageMagick pixel enumeration: 1,1,65535,srgb
	AVERAGERGB=$(cat ${FILENAMEDATE}-${CAMHOST}.jpg|convert -crop 1000x1000+796+472 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f %.0f %.0f\n", $1/256,$2/256,$3/256 }')
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
#	AVERAGEVALUE=$(cat ${T}-${CAMHOST}.jpg|convert -crop 1750x1944 - - |convert -resize 1x1 - txt: |tail -1|sed -e's/0,0: (//' -e's/,/ /g'|awk '{ printf "%.0f\n", 256*(($1+$2+$3)/3)/65535 }')

	if [[ $SHUTTERSPEED -gt 6000000 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too large, set to max 6000000"
		SHUTTERSPEED=6000000
	elif [[ $SHUTTERSPEED -lt 1 ]]; then
		echo "SHUTTERSPEED=$SHUTTERSPEED too small, set to min 1"
		SHUTTERSPEED=1
	fi

#	if [[ $OLDSHUTTERSPEED -eq 6000000 && $AVERAGEVALUE -lt 20 ]]; then
#		T=$(date '+%Y%m%d_%H%M%S')
#		echo "$T count stars"
#		S=$(cat ${LIVEDIR}/${CAMNAME}_temp2.jpg|jpegtopnm 2>/dev/null|ppmtopgm|convert -crop 1000x1000+796+472 - - |convert - crop.fits && image2xy -O -g 9 crop-0.fits|awk '{ print $3 }')
#		echo "stars=[$S]"
#	echo "update ${CAMNAME}camstars.rrd -t stars N:$S > /dev/shm/rrdupdate_${CAMNAME}camstars"
#	echo "update ${CAMNAME}camstars.rrd -t stars N:$S" > /dev/shm/rrdupdate_${CAMNAME}camstars
#	else
#		echo "$T it is too bright, do not bother counting stars"
#		S=0
#	fi

	if [[ $RED -eq 0 && $GREEN -gt 200 && $BLUE -eq 0 ]]; then
        echo "ANOMALY correct, set to min 100"
        SHUTTERSPEED=100
        MUSTGOFAST=1
    else
        MUSTGOFAST=0
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
	LINE="${CAMNAME} ${CAMHOST}\n$(date -u '+%Y-%m-%dT%H:%M:%SZ')\nRGB $RED $GREEN $BLUE ($AVERAGEVALUE)\nExposure $OLDEXPOSURE s\n (next $NEWEXPOSURE)\nISO $ISO\n (next $ISO)\nSleep $SLEEP s"
    COMMAND="convert ${FILENAMEDATE}-${CAMHOST}.jpg -fill white -pointsize 60 -annotate +50+90 \"$LINE\" ${LIVEDIR}/${CAMNAME}_temp3.jpg"
    T=$(date '+%Y%m%d_%H%M%S') ; echo "$T $COMMAND" #; $COMMAND
    convert ${FILENAMEDATE}-${CAMHOST}.jpg -fill white -pointsize 60 -annotate +50+90 "$LINE" ${LIVEDIR}/${CAMNAME}_temp3.jpg

    COMMAND="mv ${LIVEDIR}/${CAMNAME}_temp3.jpg ${LIVEDIR}/${CAMNAME}.jpg"
    T=$(date '+%Y%m%d_%H%M%S') ; echo "$T $COMMAND" ; $COMMAND

	/usr/bin/logger -t ${0##*/} -i "Exposure $OLDEXPOSURE s, Average $AVERAGEVALUE, Factor $DELTAFACTOR new exposure $NEWEXPOSURE s"

	T=$(date '+%Y%m%d_%H%M%S')
	if [[ $MUSTGOFAST -eq 1 ]]; then
		echo "$T MUSTGOFAST, skip sleep $SLEEP"
		continue
	else
		echo "$T sleep $SLEEP"
		sleep $SLEEP
	fi

done

