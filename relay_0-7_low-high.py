#!/usr/bin/env python3

import wiringpi as wp
import time
import sys

wp.wiringPiSetup()

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
	gpiostate = wp.GPIO.HIGH
elif state == "low" :
	gpiostate = wp.GPIO.LOW
else :
	print("need state high or low")
	sys.exit(1)

print("Set relay", relay, "to", state, "(", gpiostate, ")");

stateFile = open("/dev/shm/state_relay" + relay, 'w')
stateFile.write(state + '\n')
stateFile.close()

#quit()

wp.pinMode(int(relay), wp.GPIO.OUTPUT)

#print("write :")

wp.digitalWrite(int(relay), gpiostate)

#print("high")
#wp.digitalWrite(relay, wp.GPIO.HIGH)

#time.sleep(3.0)

#print("low")
#wp.digitalWrite(relay, wp.GPIO.LOW)

#print("quit")
quit()

