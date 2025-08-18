#!/bin/bash

WHICHONE="$1"
TARGET_DIR="/webs/lambermont.dyndns.org/www/astro/rrd"

if [ -z "$WHICHONE" ]; then
	WHICHONE="all"
fi

mytest() {

minmax=`rrdtool graph \
			-A ${TARGET_DIR}/obsenv1.png --start now-1d \
			--title "Observatory environment, last 24h" \
			--vertical-label "temperature [C]" \
			--right-axis-label "humidity [%]" \
			--right-axis 1:0 \
DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE \
DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE \
DEF:hum8=tempandhum-outside.rrd:humidity:AVERAGE \
DEF:hum9=tempandhum-observatory.rrd:humidity:AVERAGE \
DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE \
DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE \
VDEF:temp8max=temp8,MAXIMUM \
VDEF:temp8avg=temp8,AVERAGE \
VDEF:temp8min=temp8,MINIMUM \
VDEF:temp9max=temp9,MAXIMUM \
VDEF:temp9avg=temp9,AVERAGE \
VDEF:temp9min=temp9,MINIMUM \
VDEF:hum8max=hum8,MAXIMUM \
VDEF:hum8avg=hum8,AVERAGE \
VDEF:hum8min=hum8,MINIMUM \
VDEF:hum9max=hum9,MAXIMUM \
VDEF:hum9avg=hum9,AVERAGE \
VDEF:hum9min=hum9,MINIMUM \
VDEF:dew8max=dew8,MAXIMUM \
VDEF:dew8avg=dew8,AVERAGE \
VDEF:dew8min=dew8,MINIMUM \
VDEF:dew9max=dew9,MAXIMUM \
VDEF:dew9avg=dew9,AVERAGE \
VDEF:dew9min=dew9,MINIMUM \
COMMENT:"\t\t\t\t\tlast\t\t    max\t   avg\t  min\l" \
LINE1:temp8#0000FF:"Outside Temperature\t" \
PRINT:temp8max:"outsidetempmax_%6.0lf" \
PRINT:temp8min:"outsidetempmin_%6.0lf" \
LINE1:temp9#FF0000:"Observatory Temperature\t" \
PRINT:temp9max:"obstempmax_%6.0lf" \
PRINT:temp9min:"obstempmin_%6.0lf" \
LINE1:dew8#00FFFF:"Outside Dewpoint\t\t" \
PRINT:dew8max:"outsidedewtempmax_%6.0lf" \
PRINT:dew8min:"outsidedewtempmin_%6.0lf" \
LINE1:dew9#FF00FF:"Observatory Dewpoint\t" \
PRINT:dew9max:"obsdewtempmax_%6.0lf" \
PRINT:dew9min:"obsdewtempmin_%6.0lf" \
LINE1:hum8#00FF00:"Outside     Humidity\t\t" \
PRINT:hum8max:"outsidehummax_%6.0lf" \
PRINT:hum8min:"outsidehummin_%6.0lf" \
LINE1:hum9#000000:"Observatory Humidity\t" \
PRINT:hum9max:"obshummax_%6.0lf" \
PRINT:hum9min:"obshummin_%6.0lf" \
#`

tempmax=-100
tempmin=100
hummax=-100
hummin=100
wtf=`echo "$minmax" | while read line; do 
	case $line in
	*tempmax_*)
		temp=\`echo $line | sed -e's/.* //'\`
		if [ $temp -gt $tempmax ]; then
			tempmax=$temp
		fi
		;;
	*tempmin_*)
		temp=\`echo $line | sed -e's/.* //'\`
		if [ $temp -lt $tempmin ]; then
			tempmin=$temp
		fi
		;;
	*hummax*)
		hum=\`echo $line | sed -e's/.* //'\`
		if [ $hum -gt $hummax ]; then
			hummax=$hum
		fi
		;;
	*hummin*)
		hum=\`echo $line | sed -e's/.* //'\`
		if [ $hum -lt $hummin ]; then
			hummin=$hum
		fi
		;;
	esac
	echo "tempmax=$tempmax"
	echo "tempmin=$tempmin"
	echo "hummax=$hummax"
	echo "hummin=$hummin"
done`

eval "$wtf"
echo "tempmax=$tempmax"
echo "tempmin=$tempmin"
echo "hummax=$hummax"
echo "hummin=$hummin"

exit 0
}

tempandhumiditytest() {

	minmax=`rrdtool graph \
			-A ${TARGET_DIR}/obsenv1.png --start now-1d \
			--title "Observatory environment, last 24h" \
			--vertical-label "temperature [C]" \
			--right-axis-label "humidity [%]" \
			--right-axis 1:0 \
DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE \
DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE \
DEF:hum8=tempandhum-outside.rrd:humidity:AVERAGE \
DEF:hum9=tempandhum-observatory.rrd:humidity:AVERAGE \
DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE \
DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE \
VDEF:temp8max=temp8,MAXIMUM \
VDEF:temp8avg=temp8,AVERAGE \
VDEF:temp8min=temp8,MINIMUM \
VDEF:temp9max=temp9,MAXIMUM \
VDEF:temp9avg=temp9,AVERAGE \
VDEF:temp9min=temp9,MINIMUM \
VDEF:hum8max=hum8,MAXIMUM \
VDEF:hum8avg=hum8,AVERAGE \
VDEF:hum8min=hum8,MINIMUM \
VDEF:hum9max=hum9,MAXIMUM \
VDEF:hum9avg=hum9,AVERAGE \
VDEF:hum9min=hum9,MINIMUM \
VDEF:dew8max=dew8,MAXIMUM \
VDEF:dew8avg=dew8,AVERAGE \
VDEF:dew8min=dew8,MINIMUM \
VDEF:dew9max=dew9,MAXIMUM \
VDEF:dew9avg=dew9,AVERAGE \
VDEF:dew9min=dew9,MINIMUM \
COMMENT:"\t\t\t\t\tlast\t\t    max\t   avg\t  min\l" \
LINE1:temp8#0000FF:"Outside Temperature\t" \
PRINT:temp8max:"outsidetempmax_%6.0lf" \
PRINT:temp8min:"outsidetempmin_%6.0lf" \
LINE1:temp9#FF0000:"Observatory Temperature\t" \
PRINT:temp9max:"obstempmax_%6.0lf" \
PRINT:temp9min:"obstempmin_%6.0lf" \
LINE1:dew8#00FFFF:"Outside Dewpoint\t\t" \
PRINT:dew8max:"outsidedewtempmax_%6.0lf" \
PRINT:dew8min:"outsidedewtempmin_%6.0lf" \
LINE1:dew9#FF00FF:"Observatory Dewpoint\t" \
PRINT:dew9max:"obsdewtempmax_%6.0lf" \
PRINT:dew9min:"obsdewtempmin_%6.0lf" \
LINE1:hum8#00FF00:"Outside     Humidity\t\t" \
PRINT:hum8max:"outsidehummax_%6.0lf" \
PRINT:hum8min:"outsidehummin_%6.0lf" \
LINE1:hum9#000000:"Observatory Humidity\t" \
PRINT:hum9max:"obshummax_%6.0lf" \
PRINT:hum9min:"obshummin_%6.0lf" \
#`

tempmax=-100
tempmin=100
hummax=-100
hummin=100
wtf=`echo "$minmax" | while read line; do 
	case $line in
	*tempmax_*)
		temp=\`echo $line | sed -e's/.* //'\`
		if [ $temp -gt $tempmax ]; then
			tempmax=$temp
		fi
		;;
	*tempmin_*)
		temp=\`echo $line | sed -e's/.* //'\`
		if [ $temp -lt $tempmin ]; then
			tempmin=$temp
		fi
		;;
	*hummax*)
		hum=\`echo $line | sed -e's/.* //'\`
		if [ $hum -gt $hummax ]; then
			hummax=$hum
		fi
		;;
	*hummin*)
		hum=\`echo $line | sed -e's/.* //'\`
		if [ $hum -lt $hummin ]; then
			hummin=$hum
		fi
		;;
	esac
	echo "tempmax=$tempmax"
	echo "tempmin=$tempmin"
	echo "hummax=$hummax"
	echo "hummin=$hummin"
done`

eval "$wtf"

rascale=`echo "100/($hummax - $hummin)" | bc -l`
rashift=`echo "-1 * $hummin * $rascale" | bc -l`

# http://oss.oetiker.ch/rrdtool/forum.en.html#nabble-td5699967
#			--right-axis 1:0 \
#
rrdtool graph \
			-A ${TARGET_DIR}/obsenv1.png --start now-1d \
			--title "Observatory environment, last 24h" \
			--vertical-label "temperature [C]" \
			--right-axis-label "humidity [%]" \
			--right-axis "$rascale:$rashift" \
DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE \
DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE \
DEF:hum8=tempandhum-outside.rrd:humidity:AVERAGE \
CDEF:shum8=hum8,100,/,$hummax,$hummin,-,*,$hummin,+ \
DEF:hum9=tempandhum-observatory.rrd:humidity:AVERAGE \
CDEF:shum9=hum9,100,/,$hummax,$hummin,-,*,$hummin,+ \
DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE \
DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE \
VDEF:temp8max=temp8,MAXIMUM \
VDEF:temp8avg=temp8,AVERAGE \
VDEF:temp8min=temp8,MINIMUM \
VDEF:temp9max=temp9,MAXIMUM \
VDEF:temp9avg=temp9,AVERAGE \
VDEF:temp9min=temp9,MINIMUM \
VDEF:hum8max=hum8,MAXIMUM \
VDEF:hum8avg=hum8,AVERAGE \
VDEF:hum8min=hum8,MINIMUM \
VDEF:hum9max=hum9,MAXIMUM \
VDEF:hum9avg=hum9,AVERAGE \
VDEF:hum9min=hum9,MINIMUM \
VDEF:dew8max=dew8,MAXIMUM \
VDEF:dew8avg=dew8,AVERAGE \
VDEF:dew8min=dew8,MINIMUM \
VDEF:dew9max=dew9,MAXIMUM \
VDEF:dew9avg=dew9,AVERAGE \
VDEF:dew9min=dew9,MINIMUM \
COMMENT:"\t\t\t\t\tlast\t\t    max\t   avg\t  min\l" \
LINE1:temp8#0000FF:"Outside Temperature\t" \
GPRINT:temp8:LAST:"%6.2lf%SC\t" \
GPRINT:temp8max:"%6.2lf\t" \
GPRINT:temp8avg:"%6.2lf\t" \
GPRINT:temp8min:"%6.2lf\tC\l" \
LINE1:temp9#FF0000:"Observatory Temperature\t" \
GPRINT:temp9:LAST:"%6.2lf%SC\t" \
GPRINT:temp9max:"%6.2lf\t" \
GPRINT:temp9avg:"%6.2lf\t" \
GPRINT:temp9min:"%6.2lf\tC\l" \
LINE1:dew8#00FFFF:"Outside Dewpoint\t\t" \
GPRINT:dew8:LAST:"%6.2lf%SC\t" \
GPRINT:dew8max:"%6.2lf\t" \
GPRINT:dew8avg:"%6.2lf\t" \
GPRINT:dew8min:"%6.2lf\tC\l" \
LINE1:dew9#FF00FF:"Observatory Dewpoint\t" \
GPRINT:dew9:LAST:"%6.2lf%SC\t" \
GPRINT:dew9max:"%6.2lf\t" \
GPRINT:dew9avg:"%6.2lf\t" \
GPRINT:dew9min:"%6.2lf\tC\l" \
LINE1:shum8#00FF00:"Outside Humidity\t\t" \
GPRINT:hum8:LAST:"%6.2lf%S%%\\t" \
GPRINT:hum8max:"%6.2lf\t" \
GPRINT:hum8avg:"%6.2lf\t" \
GPRINT:hum8min:"%6.2lf\t%%\\l" \
LINE1:shum9#000000:"Observatory Humidity\t" \
GPRINT:hum9:LAST:"%6.2lf%S%%\\t" \
GPRINT:hum9max:"%6.2lf\t" \
GPRINT:hum9avg:"%6.2lf\t" \
GPRINT:hum9min:"%6.2lf\t%%\\l" \
#
}

tempandhumidity()
{
rrdtool graph \
			-A ${TARGET_DIR}/obsenv1.png --start now-1d \
			--title "Observatory environment, last 24h" \
			--vertical-label "temperature [C]" \
			--right-axis-label "humidity [%]" \
			--right-axis 1:0 \
DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE \
DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE \
DEF:hum8=tempandhum-outside.rrd:humidity:AVERAGE \
DEF:hum9=tempandhum-observatory.rrd:humidity:AVERAGE \
DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE \
DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE \
VDEF:temp8max=temp8,MAXIMUM \
VDEF:temp8avg=temp8,AVERAGE \
VDEF:temp8min=temp8,MINIMUM \
VDEF:temp9max=temp9,MAXIMUM \
VDEF:temp9avg=temp9,AVERAGE \
VDEF:temp9min=temp9,MINIMUM \
VDEF:hum8max=hum8,MAXIMUM \
VDEF:hum8avg=hum8,AVERAGE \
VDEF:hum8min=hum8,MINIMUM \
VDEF:hum9max=hum9,MAXIMUM \
VDEF:hum9avg=hum9,AVERAGE \
VDEF:hum9min=hum9,MINIMUM \
VDEF:dew8max=dew8,MAXIMUM \
VDEF:dew8avg=dew8,AVERAGE \
VDEF:dew8min=dew8,MINIMUM \
VDEF:dew9max=dew9,MAXIMUM \
VDEF:dew9avg=dew9,AVERAGE \
VDEF:dew9min=dew9,MINIMUM \
COMMENT:"\t\t\t\t\tlast\t\t    max\t   avg\t  min\l" \
LINE1:temp8#0000FF:"Outside Temperature\t" \
GPRINT:temp8:LAST:"%6.2lf%SC\t" \
GPRINT:temp8max:"%6.2lf\t" \
GPRINT:temp8avg:"%6.2lf\t" \
GPRINT:temp8min:"%6.2lf\tC\l" \
LINE1:temp9#FF0000:"Observatory Temperature\t" \
GPRINT:temp9:LAST:"%6.2lf%SC\t" \
GPRINT:temp9max:"%6.2lf\t" \
GPRINT:temp9avg:"%6.2lf\t" \
GPRINT:temp9min:"%6.2lf\tC\l" \
LINE1:dew8#00FFFF:"Outside Dewpoint\t\t" \
GPRINT:dew8:LAST:"%6.2lf%SC\t" \
GPRINT:dew8max:"%6.2lf\t" \
GPRINT:dew8avg:"%6.2lf\t" \
GPRINT:dew8min:"%6.2lf\tC\l" \
LINE1:dew9#FF00FF:"Observatory Dewpoint\t" \
GPRINT:dew9:LAST:"%6.2lf%SC\t" \
GPRINT:dew9max:"%6.2lf\t" \
GPRINT:dew9avg:"%6.2lf\t" \
GPRINT:dew9min:"%6.2lf\tC\l" \
LINE1:hum8#00FF00:"Outside Humidity\t\t" \
GPRINT:hum8:LAST:"%6.2lf%S%%\\t" \
GPRINT:hum8max:"%6.2lf\t" \
GPRINT:hum8avg:"%6.2lf\t" \
GPRINT:hum8min:"%6.2lf\t%%\\l" \
LINE1:hum9#000000:"Observatory Humidity\t" \
GPRINT:hum9:LAST:"%6.2lf%S%%\\t" \
GPRINT:hum9max:"%6.2lf\t" \
GPRINT:hum9avg:"%6.2lf\t" \
GPRINT:hum9min:"%6.2lf\t%%\\l" \
#
}

humidity()
{
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Humidity, $period'")
	RRD+=("--vertical-label 'humidity [%]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:hum8=tempandhum-outside.rrd:humidity:AVERAGE")
	RRD+=("DEF:hum9=tempandhum-observatory.rrd:humidity:AVERAGE")
	RRD+=("DEF:hcam=tempandhum-picambucket.rrd:humidity:AVERAGE")
	RRD+=("VDEF:hum8max=hum8,MAXIMUM")
	RRD+=("VDEF:hum8avg=hum8,AVERAGE")
	RRD+=("VDEF:hum8min=hum8,MINIMUM")
	RRD+=("VDEF:hum9max=hum9,MAXIMUM")
	RRD+=("VDEF:hum9avg=hum9,AVERAGE")
	RRD+=("VDEF:hum9min=hum9,MINIMUM")
	RRD+=("VDEF:hcammax=hcam,MAXIMUM")
	RRD+=("VDEF:hcamavg=hcam,AVERAGE")
	RRD+=("VDEF:hcammin=hcam,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\tlast\t\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:hum8#00FF00:'Outside     Humidity\t'")
	RRD+=("GPRINT:hum8:LAST:'%6.2lf%S%%\\t'")
	RRD+=("GPRINT:hum8max:'%6.2lf\t'")
	RRD+=("GPRINT:hum8avg:'%6.2lf\t'")
	RRD+=("GPRINT:hum8min:'%6.2lf\t%%\\l'")
	RRD+=("LINE1:hum9#000000:'Observatory Humidity\t'")
	RRD+=("GPRINT:hum9:LAST:'%6.2lf%S%%\\t'")
	RRD+=("GPRINT:hum9max:'%6.2lf\t'")
	RRD+=("GPRINT:hum9avg:'%6.2lf\t'")
	RRD+=("GPRINT:hum9min:'%6.2lf\t%%\\l'")
	RRD+=("LINE1:hcam#FF0000:'PiCamera    Humidity\t'")
	RRD+=("GPRINT:hcam:LAST:'%6.2lf%S%%\\t'")
	RRD+=("GPRINT:hcammax:'%6.2lf\t'")
	RRD+=("GPRINT:hcamavg:'%6.2lf\t'")
	RRD+=("GPRINT:hcammin:'%6.2lf\t%%\\l'")
	eval ${RRD[@]}
}

dew() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Temperature and Dewpoint, $period'")
	RRD+=("--vertical-label 'temperature [C]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE")
	RRD+=("DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE")
	RRD+=("DEF:tcam=tempandhum-picambucket.rrd:temperature:AVERAGE")
	RRD+=("DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE")
	RRD+=("DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE")
	RRD+=("DEF:dcam=tempandhum-picambucket.rrd:dewpoint:AVERAGE")
	RRD+=("VDEF:temp8max=temp8,MAXIMUM")
	RRD+=("VDEF:temp8avg=temp8,AVERAGE")
	RRD+=("VDEF:temp8min=temp8,MINIMUM")
	RRD+=("VDEF:temp9max=temp9,MAXIMUM")
	RRD+=("VDEF:temp9avg=temp9,AVERAGE")
	RRD+=("VDEF:temp9min=temp9,MINIMUM")
	RRD+=("VDEF:tcammax=tcam,MAXIMUM")
	RRD+=("VDEF:tcamavg=tcam,AVERAGE")
	RRD+=("VDEF:tcammin=tcam,MINIMUM")
	RRD+=("VDEF:dew8max=dew8,MAXIMUM")
	RRD+=("VDEF:dew8avg=dew8,AVERAGE")
	RRD+=("VDEF:dew8min=dew8,MINIMUM")
	RRD+=("VDEF:dew9max=dew9,MAXIMUM")
	RRD+=("VDEF:dew9avg=dew9,AVERAGE")
	RRD+=("VDEF:dew9min=dew9,MINIMUM")
	RRD+=("VDEF:dcammax=dcam,MAXIMUM")
	RRD+=("VDEF:dcamavg=dcam,AVERAGE")
	RRD+=("VDEF:dcammin=dcam,MINIMUM")
#	RRD+=("COMMENT:'\t\t\t\t\tlast     max       avg       min\l'")
	RRD+=("COMMENT:'\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\tlast\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:temp8#0000FF:'Outside Temperature\t\t'")
	RRD+=("GPRINT:temp8:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp8max:'%6.2lf\t'")
	RRD+=("GPRINT:temp8avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp8min:'%6.2lf\tC\l'")
	RRD+=("LINE1:temp9#FF0000:'Observatory Temperature\t'")
	RRD+=("GPRINT:temp9:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp9max:'%6.2lf\t'")
	RRD+=("GPRINT:temp9avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp9min:'%6.2lf\tC\l'")
	RRD+=("LINE1:tcam#00FF00:'PiBucketCamera Temp.\t\t'")
	RRD+=("GPRINT:tcam:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:tcammax:'%6.2lf\t'")
	RRD+=("GPRINT:tcamavg:'%6.2lf\t'")
	RRD+=("GPRINT:tcammin:'%6.2lf\tC\l'")
	RRD+=("LINE1:dew8#00FFFF:'Outside Dewpoint\t\t'")
	RRD+=("GPRINT:dew8:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dew8max:'%6.2lf\t'")
	RRD+=("GPRINT:dew8avg:'%6.2lf\t'")
	RRD+=("GPRINT:dew8min:'%6.2lf\tC\l'")
	RRD+=("LINE1:dew9#FF00FF:'Observatory Dewpoint\t\t'")
	RRD+=("GPRINT:dew9:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dew9max:'%6.2lf\t'")
	RRD+=("GPRINT:dew9avg:'%6.2lf\t'")
	RRD+=("GPRINT:dew9min:'%6.2lf\tC\l'")
	RRD+=("LINE1:dcam#FFFF00:'PiBucketCamera Dewpoint\t'")
	RRD+=("GPRINT:dcam:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dcammax:'%6.2lf\t'")
	RRD+=("GPRINT:dcamavg:'%6.2lf\t'")
	RRD+=("GPRINT:dcammin:'%6.2lf\tC\l'")
	eval ${RRD[@]}
}

dew-old() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Temperature and Dewpoint, $period'")
	RRD+=("--vertical-label 'temperature [C]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE")
	RRD+=("DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE")
	RRD+=("DEF:dew8=tempandhum-outside.rrd:dewpoint:AVERAGE")
	RRD+=("DEF:dew9=tempandhum-observatory.rrd:dewpoint:AVERAGE")
	RRD+=("VDEF:temp8max=temp8,MAXIMUM")
	RRD+=("VDEF:temp8avg=temp8,AVERAGE")
	RRD+=("VDEF:temp8min=temp8,MINIMUM")
	RRD+=("VDEF:temp9max=temp9,MAXIMUM")
	RRD+=("VDEF:temp9avg=temp9,AVERAGE")
	RRD+=("VDEF:temp9min=temp9,MINIMUM")
	RRD+=("VDEF:dew8max=dew8,MAXIMUM")
	RRD+=("VDEF:dew8avg=dew8,AVERAGE")
	RRD+=("VDEF:dew8min=dew8,MINIMUM")
	RRD+=("VDEF:dew9max=dew9,MAXIMUM")
	RRD+=("VDEF:dew9avg=dew9,AVERAGE")
	RRD+=("VDEF:dew9min=dew9,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\tlast     max       avg       min\l'")
	RRD+=("LINE1:temp8#0000FF:'Outside Temperature\t'")
	RRD+=("GPRINT:temp8:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp8max:'%6.2lf\t'")
	RRD+=("GPRINT:temp8avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp8min:'%6.2lf\tC\l'")
	RRD+=("LINE1:temp9#FF0000:'Observatory Temperature\t'")
	RRD+=("GPRINT:temp9:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp9max:'%6.2lf\t'")
	RRD+=("GPRINT:temp9avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp9min:'%6.2lf\tC\l'")
	RRD+=("LINE1:dew8#00FFFF:'Outside Dewpoint\t\t'")
	RRD+=("GPRINT:dew8:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dew8max:'%6.2lf\t'")
	RRD+=("GPRINT:dew8avg:'%6.2lf\t'")
	RRD+=("GPRINT:dew8min:'%6.2lf\tC\l'")
	RRD+=("LINE1:dew9#FF00FF:'Observatory Dewpoint\t'")
	RRD+=("GPRINT:dew9:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dew9max:'%6.2lf\t'")
	RRD+=("GPRINT:dew9avg:'%6.2lf\t'")
	RRD+=("GPRINT:dew9min:'%6.2lf\tC\l'")
	eval ${RRD[@]}
}

temp() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Temperature, $period'")
	RRD+=("--vertical-label 'temperature [C]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:temp8=tempandhum-outside.rrd:temperature:AVERAGE")
	RRD+=("DEF:temp9=tempandhum-observatory.rrd:temperature:AVERAGE")
	RRD+=("VDEF:temp8max=temp8,MAXIMUM")
	RRD+=("VDEF:temp8avg=temp8,AVERAGE")
	RRD+=("VDEF:temp8min=temp8,MINIMUM")
	RRD+=("VDEF:temp9max=temp9,MAXIMUM")
	RRD+=("VDEF:temp9avg=temp9,AVERAGE")
	RRD+=("VDEF:temp9min=temp9,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\t  last\t   max\t   avg\t   min\l'")
	RRD+=("LINE1:temp8#0000FF:'Outside Temperature\t\t'")
	RRD+=("GPRINT:temp8:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp8max:'%6.2lf\t'")
	RRD+=("GPRINT:temp8avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp8min:'%6.2lf\tC\l'")
	RRD+=("LINE1:temp9#FF0000:'Observatory Temperature\t'")
	RRD+=("GPRINT:temp9:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:temp9max:'%6.2lf\t'")
	RRD+=("GPRINT:temp9avg:'%6.2lf\t'")
	RRD+=("GPRINT:temp9min:'%6.2lf\tC\l'")
	eval ${RRD[@]}
}

rain() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Rain sensor drops, $period'")
	RRD+=("--vertical-label '[drops/min]'")
	RRD+=("--right-axis 1:0")
	RRD+=("--lower-limit 0 --rigid")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:drops=rainsensor.rrd:drops:MAX")
	RRD+=("VDEF:dropsmax=drops,MAXIMUM")
	RRD+=("VDEF:dropsavg=drops,AVERAGE")
	RRD+=("VDEF:dropsmin=drops,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\tlast\t   max\t   avg\t  min\l'")
	RRD+=("AREA:drops#0000FF:'Drops/min\t'")
	RRD+=("GPRINT:drops:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:dropsmax:'%6.2lf\t'")
	RRD+=("GPRINT:dropsavg:'%6.2lf\t'")
	RRD+=("GPRINT:dropsmin:'%6.2lf\l'")
	eval ${RRD[@]}
}

sqm() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Sky Brightness, $period'")
	RRD+=("--vertical-label '[magnitude/arcsec^2]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "huge" ]]; then
		RRD+=("--width 2000 --height 500")
	fi
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:sqm=sqm.rrd:sqm:MAX") # ERROR: the RRD does not contain an RRA matching the chosen CF
#	RRD+=("DEF:sqm=sqm.rrd:sqm:AVERAGE")
	RRD+=("VDEF:sqmmax=sqm,MAXIMUM")
	RRD+=("VDEF:sqmavg=sqm,AVERAGE")
	RRD+=("VDEF:sqmmin=sqm,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\tlast\t\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:sqm#0000FF:'Sky Brightness\t'")
	RRD+=("GPRINT:sqm:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:sqmmax:'%6.2lf\t'")
	RRD+=("GPRINT:sqmavg:'%6.2lf\t'")
	RRD+=("GPRINT:sqmmin:'%6.2lf\t\l'")
	eval ${RRD[@]}
}

sqmtest() {
	local size="$1"
	local start="$2"
	local end="$3"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${start}_${end}.png")
	RRD+=("--start $start")
	RRD+=("--end $end")
	RRD+=("--title 'Sky Brightness, $start $end'")
	RRD+=("--vertical-label '[magnitude/arcsec^2]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $start == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
#	RRD+=("DEF:sqm=sqm.rrd:sqm:MAX") # ERROR: the RRD does not contain an RRA matching the chosen CF
	RRD+=("DEF:sqm=sqm.rrd:sqm:AVERAGE")
	RRD+=("VDEF:sqmmax=sqm,MAXIMUM")
	RRD+=("VDEF:sqmavg=sqm,AVERAGE")
	RRD+=("VDEF:sqmmin=sqm,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\tlast\t\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:sqm#0000FF:'Sky Brightness\t'")
	RRD+=("GPRINT:sqm:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:sqmmax:'%6.2lf\t'")
	RRD+=("GPRINT:sqmavg:'%6.2lf\t'")
	RRD+=("GPRINT:sqmmin:'%6.2lf\t\l'")
	eval ${RRD[@]}
}

luminosity() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Sky Luminosity, $period'")
	RRD+=("--vertical-label 'luminosity [lx]'")
	RRD+=("--right-axis 1:0")
	RRD+=("--lower-limit 0 --rigid")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:luminosity=luminosity.rrd:luminosity:MAX")
	RRD+=("VDEF:luminositymax=luminosity,MAXIMUM")
	RRD+=("VDEF:luminosityavg=luminosity,AVERAGE")
	RRD+=("VDEF:luminositymin=luminosity,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\tlast\t\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:luminosity#0000FF:'Sky Brightness\t'")
	RRD+=("GPRINT:luminosity:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:luminositymax:'%6.2lf\t'")
	RRD+=("GPRINT:luminosityavg:'%6.2lf\t'")
	RRD+=("GPRINT:luminositymin:'%6.2lf\t\l'")
	eval ${RRD[@]}
}

skytemp() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'Sky Temperature, $period'")
	RRD+=("--vertical-label 'temperature [C]'")
	RRD+=("--right-axis 1:0")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:BAA_sensor=skytemperature-BAA.rrd:BAA_sensor:AVERAGE")
	RRD+=("DEF:BAA_sky=skytemperature-BAA.rrd:BAA_sky:AVERAGE")
	RRD+=("DEF:BCC_sensor=skytemperature-BCC.rrd:BCC_sensor:AVERAGE")
	RRD+=("DEF:BCC_sky=skytemperature-BCC.rrd:BCC_sky:AVERAGE")
	RRD+=("VDEF:BAA_sensormax=BAA_sensor,MAXIMUM")
	RRD+=("VDEF:BAA_sensoravg=BAA_sensor,AVERAGE")
	RRD+=("VDEF:BAA_sensormin=BAA_sensor,MINIMUM")
	RRD+=("VDEF:BAA_skymax=BAA_sky,MAXIMUM")
	RRD+=("VDEF:BAA_skyavg=BAA_sky,AVERAGE")
	RRD+=("VDEF:BAA_skymin=BAA_sky,MINIMUM")
	RRD+=("VDEF:BCC_sensormax=BCC_sensor,MAXIMUM")
	RRD+=("VDEF:BCC_sensoravg=BCC_sensor,AVERAGE")
	RRD+=("VDEF:BCC_sensormin=BCC_sensor,MINIMUM")
	RRD+=("VDEF:BCC_skymax=BCC_sky,MAXIMUM")
	RRD+=("VDEF:BCC_skyavg=BCC_sky,AVERAGE")
	RRD+=("VDEF:BCC_skymin=BCC_sky,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\tlast\tmax\tavg\tmin\l'")
	RRD+=("LINE1:BAA_sensor#0000FF:'BAA sensor temperature\t'")
	RRD+=("GPRINT:BAA_sensor:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_sensormax:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_sensoravg:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_sensormin:'%6.2lf\tC\l'")
	RRD+=("LINE1:BCC_sensor#00FFFF:'BCC sensor temperature\t'")
	RRD+=("GPRINT:BCC_sensor:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_sensormax:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_sensoravg:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_sensormin:'%6.2lf\tC\l'")
	RRD+=("LINE1:BAA_sky#FF0000:'BAA sky temperature\t\t'")
	RRD+=("GPRINT:BAA_sky:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_skymax:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_skyavg:'%6.2lf\t'")
	RRD+=("GPRINT:BAA_skymin:'%6.2lf\tC\l'")
	RRD+=("LINE1:BCC_sky#FF00FF:'BCC sky temperature\t\t'")
	RRD+=("GPRINT:BCC_sky:LAST:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_skymax:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_skyavg:'%6.2lf\t'")
	RRD+=("GPRINT:BCC_skymin:'%6.2lf\tC\l'")
	eval ${RRD[@]}
}

ups() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'UPS, $period'")
	RRD+=("--vertical-label 'various'")
	RRD+=("--right-axis 1:0")
	RRD+=("--lower-limit 0 --rigid")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:status=ups.rrd:status:AVERAGE")
	RRD+=("DEF:linev=ups.rrd:linev:AVERAGE")
	RRD+=("DEF:loadpct=ups.rrd:loadpct:AVERAGE")
	RRD+=("DEF:bcharge=ups.rrd:bcharge:AVERAGE")
	RRD+=("DEF:timeleft=ups.rrd:timeleft:AVERAGE")
	RRD+=("DEF:itemp=ups.rrd:itemp:AVERAGE")
	RRD+=("DEF:battv=ups.rrd:battv:AVERAGE")
	RRD+=("DEF:linefreq=ups.rrd:linefreq:AVERAGE")
	RRD+=("LINE1:status#000000:'Status\t'")
	RRD+=("LINE1:linev#FF0000:'LineV\t'")
	RRD+=("LINE1:loadpct#FFFF00:'LoadPCT\t'")
	RRD+=("LINE1:bcharge#909090:'Bcharge\t'")
	RRD+=("LINE1:timeleft#0000FF:'TimeLeft\t'")
	RRD+=("LINE1:itemp#00FF00:'ITemp\t'")
	RRD+=("LINE1:battv#00FFFF:'BattV\t'")
	RRD+=("LINE1:linefreq#FF00FF:'LineFreq\t'")
	eval ${RRD[@]}
}

allskycamstars() {
	local size="$1"
	local period="$2"
	declare -a RRD
	RRD=("rrdtool graph")
	RRD+=("-A ${TARGET_DIR}/${FUNCNAME}_${size}_${period}.png")
	RRD+=("--start $period")
	RRD+=("--title 'AllSkyCamera Stars, $period'")
	RRD+=("--vertical-label 'stars [n]'")
	RRD+=("--right-axis 1:0")
	RRD+=("--lower-limit 0 --rigid")
	if [[ $size == "large" ]]; then
		RRD+=("--width 1000 --height 500")
	fi
	if [[ $period == "now-1d" ]]; then
		RRD+=("--x-grid DAY:1:HOUR:1:HOUR:1:0:%H")
	fi
	RRD+=("DEF:stars=allskycamstars.rrd:stars:MAX")
	RRD+=("VDEF:starsmax=stars,MAXIMUM")
	RRD+=("VDEF:starsavg=stars,AVERAGE")
	RRD+=("VDEF:starsmin=stars,MINIMUM")
	RRD+=("COMMENT:'\t\t\t\t\t\t\t\t\t\t\t\t\ttime [h]\n'")
	RRD+=("COMMENT:'\t\t\t\tlast\t    max\t   avg\t  min\l'")
	RRD+=("LINE1:stars#0000FF:'AllSkyCam Stars\t'")
	RRD+=("GPRINT:stars:LAST:'%6.0lf\t'")
	RRD+=("GPRINT:starsmax:'%6.0lf\t'")
	RRD+=("GPRINT:starsavg:'%6.0lf\t'")
	RRD+=("GPRINT:starsmin:'%6.0lf\t\l'")
	eval ${RRD[@]}
}

# time notation https://oss.oetiker.ch/rrdtool/doc/rrdfetch.en.html

case $WHICHONE in
all)
	tempandhumidity
	dew small now-1d
	dew large now-1d
	dew large now-1w
	dew large now-1m
	dew large now-1y
	temp small now-1d
	temp large now-1d
	temp large now-1w
	temp large now-1m
	temp large now-1y
	rain small now-1d
	rain large now-1d
	rain large now-1w
	rain large now-1m
	rain large now-1y
	humidity small now-1d
	humidity large now-1d
	humidity large now-1w
	humidity large now-1m
	humidity large now-1y
	sqm small now-1d
	sqm large now-1d
	sqm large now-1w
	sqm large now-1m
#	sqm huge now-6months
	sqm large now-1y
	luminosity small now-1d
	luminosity large now-1d
	luminosity large now-1w
	luminosity large now-1m
	luminosity large now-1y
	skytemp small now-1d
	skytemp large now-1d
	skytemp large now-1w
	skytemp large now-1m
	skytemp large now-1y
	ups small now-1d
	ups large now-1d
	ups large now-1w
	ups large now-1m
	ups large now-1y
	allskycamstars small now-1d
	allskycamstars large now-1d
	allskycamstars large now-1w
	allskycamstars large now-1m
	allskycamstars large now-1y
	;;
1)
	tempandhumidity
	;;
dew)
	dew small now-1d
	dew large now-1d
	dew large now-1w
	;;
temp)
	temp small now-1d
	temp large now-1d
	temp large now-1w
	;;
humidity)
	humidity small now-1d
	humidity large now-1d
	humidity large now-1w
	;;
rain)
	rain small now-1d
	rain large now-1d
	rain large now-1w
	;;
sqm)
	sqm small now-1d
	sqm large now-1d
	sqm large now-1w
	;;
sqmtest)
	sqmtest large 20160109 start+1d
	;;
luminosity)
	luminosity small now-1d
	luminosity large now-1d
	luminosity large now-1w
	;;
skytemp)
	skytemp small now-1d
	skytemp large now-1d
	skytemp large now-1w
	;;
ht)
	sqm large now-1m
	sqm large now-3m
	sqm large now-1y
	;;
ups)
	ups large now-1d
	;;
esac

#scp /var/www/html/*.png hans@webs:/webs/lambermont.dyndns.org/www/astro/
#scp /var/www/html/*.png hans@lxc-webs:/webs/lambermont.dyndns.org/www/astro/

