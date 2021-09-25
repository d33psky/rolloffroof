#!/usr/bin/env python3
import threading
import logging
import time
import signal
import os
import socket
from flask import Flask, jsonify, request, render_template

if os.uname()[4].startswith("arm"):
    import wiringpi
else:
    from unittest.mock import Mock

    wiringpi = Mock()
    wiringpi.digitalRead.return_value = 0

next_possible_green_button_action = 0
GREEN_BUTTON_OPENING = 1
GREEN_BUTTON_STOP = 2
GREEN_BUTTON_CLOSING = 3

received_signal = 0
roof_opening = False
roof_closing = False
roof_opened = False
roof_closed = False

ROOF_SENSORS_OPEN1 = 13
ROOF_SENSORS_CLOSE1 = 12
ROOF_MOTOR_START_RELAY = 0
ROOF_MOTOR_DIRECTION_RELAY = 1
GREEN_BUTTON = 18

MOUNT_IP = "192.168.100.73"
MOUNT_PORT = 3490

FLASK_APP = Flask(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='(%(threadName)-10s) %(message)s',
)


def read_roof_sensor_open():
    """ sensor """
    global roof_opened
    state = wiringpi.digitalRead(ROOF_SENSORS_OPEN1)
    #    logging.debug('roof_sensors_open: {}'.format(state))
    roof_opened = True if state == 1 else False;
    return roof_opened


def read_roof_sensor_close():
    """ sensor """
    global roof_closed
    state = wiringpi.digitalRead(ROOF_SENSORS_CLOSE1)
    #    logging.debug('roof_sensors_close: {}'.format(state))
    roof_closed = True if state == 1 else False;
    return roof_closed


def write_roof_motor_stop():
    """ motor """
    global roof_closing
    global roof_opening
    logging.debug('write_roof_motor_stop')
    wiringpi.digitalWrite(ROOF_MOTOR_START_RELAY, wiringpi.GPIO.LOW)  # stop motor
    wiringpi.digitalWrite(ROOF_MOTOR_DIRECTION_RELAY, wiringpi.GPIO.HIGH)  # roof close direction
    roof_opening = False
    roof_closing = False


def write_roof_motor_close():
    """ motor """
    global roof_closing
    wiringpi.digitalWrite(ROOF_MOTOR_DIRECTION_RELAY, wiringpi.GPIO.HIGH)  # roof close direction
    wiringpi.digitalWrite(ROOF_MOTOR_START_RELAY, wiringpi.GPIO.HIGH)  # start motor
    logging.debug('write_roof_motor_close')
    roof_closing = True


def write_roof_motor_open():
    """ motor """
    global roof_opening
    wiringpi.digitalWrite(ROOF_MOTOR_DIRECTION_RELAY, wiringpi.GPIO.LOW)  # roof open direction
    wiringpi.digitalWrite(ROOF_MOTOR_START_RELAY, wiringpi.GPIO.HIGH)  # start motor
    logging.debug('write_roof_motor_open')
    roof_opening = True


def simple_netcat(host, port, content, sleep):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.sendall(content.encode())
    time.sleep(sleep)
    s.shutdown(socket.SHUT_WR)
    response_ascii = ''
    while True:
        data = s.recv(128)
        if not data:
            break
        response_ascii += data.decode('ascii')
        # print(repr(data))
    s.close()
    return response_ascii


@FLASK_APP.route('/roof/sensors/open', methods=['GET'])
def roof_sensors_open():
    """ api call """
    state = read_roof_sensor_open()
    return jsonify({'roof_sensors_opened': state})


@FLASK_APP.route('/roof/sensors/close', methods=['GET'])
def roof_sensors_close():
    """ api call """
    state = read_roof_sensor_close()
    return jsonify({'roof_sensors_closed': state})


@FLASK_APP.route('/roof/motor/stop', methods=['POST'])
def roof_motor_stop():
    """ api call """
    global roof_closing
    global roof_opening
    global received_signal
    if roof_opening or roof_closing:
        logging.debug('Roof is {opening_or_closing}, force stop'.format(
            opening_or_closing='opening' if roof_opening else 'closing'))
        roof_closing = False
        roof_opening = False
        received_signal = 1
        return jsonify({'roof_motor_stop': True})
    else:
        logging.debug('Roof is not moving, nothing to stop')
        return jsonify({'roof_motor_stop': False})


@FLASK_APP.route('/roof/motor/close', methods=['POST'])
def roof_motor_close():
    """ api call """
    global roof_closing
    global received_signal
    if read_roof_sensor_close():
        logging.debug('Refuse roof_motor_close, Roof is already closed')
        roof_closing = False
        return jsonify({'roof_motor_close': False})
    else:
        # First check if the mount is parked in order to prevent the roof from knocking over the mount.
        response = simple_netcat(MOUNT_IP, MOUNT_PORT, "#:Gstat#", 0.5)
        if response == '5#':
            logging.debug('mount is parked, continue to roof_motor_close')
            roof_closing = True
            received_signal = 1
            return jsonify({'roof_motor_close': True})
        else:
            logging.debug('mount IS NOT PARKED, REFUSE TO roof_motor_close')
            roof_closing = False
            return jsonify({'roof_motor_close': False})


@FLASK_APP.route('/roof/motor/open', methods=['POST'])
def roof_motor_open():
    """ api call """
    global roof_opening
    global received_signal
    if read_roof_sensor_open():
        logging.debug('Refuse roof_motor_open, Roof is already open')
        roof_opening = False
        return jsonify({'roof_motor_open': False})
    else:
        logging.debug('roof_motor_open')
        roof_opening = True
        received_signal = 1
        return jsonify({'roof_motor_open': True})


@FLASK_APP.route('/', methods=['POST', 'GET'])
def index():
    """ web call """
    if request.method == 'POST':
        if request.form.get('Open') == 'Open':
            print("Web interface calling roof_motor_open")
            roof_motor_open()
        elif request.form.get('Close') == 'Close':
            print("Web interface calling roof_motor_close")
            roof_motor_close()
        else:
            print("Web interface calling roof_motor_stop")
            roof_motor_stop()
    return render_template("index.html")


# @FLASK_APP.errorhandler(404)
# def not_found(error):
#    return make_response(jsonify({'error': 'Not found'}), 404)

# kill -SIGUSR1 13534
# https://docs.python.org/3/library/signal.html#signal.signal
def signal_handler(signum, stack_frame):
    """ signals """
    global received_signal
    print("*** signal_handler received:", signum)
    received_signal = signum


def wait_for_button(pin):
    """ wait green button or signal """
    global received_signal
    global roof_opened
    global roof_closed
    global roof_opening
    global roof_closing
    global next_possible_green_button_action
    time.sleep(1)
    while True:
        while wiringpi.digitalRead(pin) == True and received_signal == 0:
            time.sleep(0.01)
        # signal ?
        if received_signal != 0:
            print("Signal {}, opened {}, closed {}, opening {}, closing {}".format(
                received_signal, roof_opened, roof_closed, roof_opening, roof_closing))
            received_signal = 0
            return True
        # possible button press start
        pressed_time = 0
        while wiringpi.digitalRead(pin) == False:
            time.sleep(0.01)
            pressed_time += 10
        if pressed_time >= 100:
            print("Pressed for", pressed_time, "ms")
            if next_possible_green_button_action == GREEN_BUTTON_CLOSING:
                roof_closing = True
            elif next_possible_green_button_action == GREEN_BUTTON_OPENING:
                roof_opening = True
            elif next_possible_green_button_action == GREEN_BUTTON_STOP:
                roof_closing = False
                roof_opening = False
            return True
        else:
            print("Too brief press:", pressed_time, "ms")


class RoofControlThread(threading.Thread):
    """ the non-flask thread """

    def run(self):
        logging.debug('roof thread')
        global received_signal
        global next_possible_green_button_action
        while True:
            print('')
            print(time.strftime("%Y%m%d_%H%M%S"), "Wait for button or signal event")
            wait_for_button(GREEN_BUTTON)
            print(time.strftime("%Y%m%d_%H%M%S"), "Green button pressed or signal received")
            time.sleep(0.5)
            if roof_closing:
                if not read_roof_sensor_close():
                    print(time.strftime("%Y%m%d_%H%M%S"), "Closing roof")
                    write_roof_motor_close()
                    next_possible_green_button_action = GREEN_BUTTON_STOP
                    print('')
                    print(time.strftime("%Y%m%d_%H%M%S"), "Wait for an event to stop closing the roof")
                    while not read_roof_sensor_close() and wiringpi.digitalRead(GREEN_BUTTON) and received_signal == 0:
                        pass
                    print(time.strftime("%Y%m%d_%H%M%S"), "event to stop closing the roof received")
                    received_signal = 0
                    write_roof_motor_stop()
                    next_possible_green_button_action = GREEN_BUTTON_OPENING
                    if read_roof_sensor_close():
                        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is closed")
                else:
                    logging.debug('roof already closed')
            elif roof_opening:
                if not read_roof_sensor_open():
                    print(time.strftime("%Y%m%d_%H%M%S"), "Opening roof")
                    write_roof_motor_open()
                    next_possible_green_button_action = GREEN_BUTTON_STOP
                    print('')
                    print(time.strftime("%Y%m%d_%H%M%S"), "Wait for an event to stop opening the roof")
                    while not read_roof_sensor_open() and wiringpi.digitalRead(GREEN_BUTTON) and received_signal == 0:
                        pass
                    print(time.strftime("%Y%m%d_%H%M%S"), "event to stop opening the roof received")
                    received_signal = 0
                    write_roof_motor_stop()
                    next_possible_green_button_action = GREEN_BUTTON_CLOSING
                    if read_roof_sensor_open():
                        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is open")
                else:
                    logging.debug('roof already open')
            else:
                write_roof_motor_stop()
                received_signal = 0


def init():
    """ set up signals and wiringpi pins """
    global next_possible_green_button_action

    print(time.strftime("%Y%m%d_%H%M%S"), "Set up signal_handler")
    signal.signal(signal.SIGUSR1, signal_handler)
    signal.signal(signal.SIGUSR2, signal_handler)

    wiringpi.wiringPiSetup()

    print(time.strftime("%Y%m%d_%H%M%S"), "Set up GREEN_BUTTON as input")
    wiringpi.pinMode(GREEN_BUTTON, wiringpi.GPIO.INPUT)
    wiringpi.pullUpDnControl(GREEN_BUTTON, wiringpi.GPIO.PUD_UP)

    print(time.strftime("%Y%m%d_%H%M%S"), "Set up roof closed and opened sensors as input")
    wiringpi.pinMode(ROOF_SENSORS_CLOSE1, wiringpi.GPIO.INPUT)
    wiringpi.pinMode(ROOF_SENSORS_OPEN1, wiringpi.GPIO.INPUT)

    print(time.strftime("%Y%m%d_%H%M%S"), "Set up left and right relay as output")
    wiringpi.pinMode(ROOF_MOTOR_START_RELAY, wiringpi.GPIO.OUTPUT)
    wiringpi.pinMode(ROOF_MOTOR_DIRECTION_RELAY, wiringpi.GPIO.OUTPUT)

    if read_roof_sensor_open():
        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is open.")
    if read_roof_sensor_close():
        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is closed.")
        next_possible_green_button_action = GREEN_BUTTON_OPENING
    else:
        next_possible_green_button_action = GREEN_BUTTON_CLOSING
    write_roof_motor_stop()


def main():
    """ main """
    init()

    roof_control_thread = RoofControlThread()
    roof_control_thread.start()

    try:
        FLASK_APP.run(debug=False, host='0.0.0.0')
    except KeyboardInterrupt:
        print(time.strftime("%Y%m%d_%H%M%S"), "KeyboardInterrupt caught in flask. Stop any running motor")
        write_roof_motor_stop()


if __name__ == '__main__':
    main()
