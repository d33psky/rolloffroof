#!/usr/bin/env python3

import wiringpi2 as wp2
import time
import sys

wp2.wiringPiSetup()

relay0=0
relay1=1
relay2=2
relay3=3
relay4=4
relay5=5
relay6=6
relay7=7

# 0-7
relay=sys.argv[1]

# high low
state=sys.argv[2]

if state == "high" :
	gpiostate = wp2.GPIO.HIGH
elif state == "low" :
	gpiostate = wp2.GPIO.LOW
else :
	print("need state high or low")
	sys.exit(1)

print("Set relay", relay, "to", state, "(", gpiostate, ")");

stateFile = open("/dev/shm/state_relay" + relay, 'w')
stateFile.write(state + '\n')
stateFile.close()

#quit()

wp2.pinMode(int(relay), wp2.GPIO.OUTPUT)

#print("write :")

wp2.digitalWrite(int(relay), gpiostate)

#print("high")
#wp2.digitalWrite(relay, wp2.GPIO.HIGH)

#time.sleep(3.0)

#print("low")
#wp2.digitalWrite(relay, wp2.GPIO.LOW)

#print("quit")
quit()

