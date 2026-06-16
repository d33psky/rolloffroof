#!/usr/bin/env python3
import atexit
import json
import threading
import logging
import time
import signal
import os
import socket
import sys
import traceback
from datetime import datetime, timezone
import requests
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

ROOF_TRAVEL_TIMEOUT_S = 70   # measured open/close ~54 s in 2015; abort + alert beyond this

MOUNT_IP = "192.168.100.73"
MOUNT_PORT = 3490

FLASK_APP = Flask(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format='(%(threadName)-10s) %(message)s',
)


# --------------------------------------------------------------------------
# Mattermost notify (inline)
#
# NOTE: This helper duplicates the minimal POST + emoji + mention logic from
# /home/hans/src/rolloffroof/ekos/observatorylib.py:Reporter (on vostro).
# rpi1 runs Python 3.5.3 and has no observatorylib deployed, hence this
# inline copy. When changing the severity/emoji/mention convention, update
# BOTH files in lockstep.
# --------------------------------------------------------------------------
MATTERMOST_URL_FILE = "/root/.mattermosturl-observatory"
MATTERMOST_SOURCE = "roof-controller"
MATTERMOST_MENTION = "@hans"
MATTERMOST_MENTION_SEVERITIES = ("critical",)  # warn intentionally NOT mentioned — silent channel log
MATTERMOST_EMOJI = {
    "info": ":information_source:",
    "warn": ":warning:",
    "critical": ":rotating_light:",
}


def _notify_mattermost_worker(severity, message):
    try:
        with open(MATTERMOST_URL_FILE) as f:
            url = f.read().rstrip("\n")
        emoji = MATTERMOST_EMOJI.get(severity, ":information_source:")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        if MATTERMOST_MENTION and severity in MATTERMOST_MENTION_SEVERITIES:
            body = "{} {}".format(MATTERMOST_MENTION, message)
        else:
            body = message
        line = "{} [{} {}] {}".format(emoji, ts, MATTERMOST_SOURCE, body)
        requests.post(url, data={"payload": json.dumps({"text": line})}, timeout=10)
    except Exception as e:
        logging.error("notify_mattermost failed: %s", e)


def notify_mattermost(severity, message):
    """Non-blocking: spawns a daemon thread to POST. Returns immediately."""
    threading.Thread(
        target=_notify_mattermost_worker,
        args=(severity, message),
        daemon=True,
    ).start()


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
            notify_mattermost("critical", "API roof_motor_close REFUSED: mount IS NOT PARKED (response={!r})".format(response))
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
            notify_mattermost("critical", "Green button pressed ({} ms)".format(pressed_time))
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
        try:
            self._run_loop()
        except Exception:
            exc_type, exc_value, exc_tb = sys.exc_info()
            _crash_notify("RoofControlThread", exc_type, exc_value, exc_tb)
            raise

    def _run_loop(self):
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
                    motion_start = time.time()
                    exit_reason = None
                    while exit_reason is None:
                        if read_roof_sensor_close():
                            exit_reason = "sensor"
                        elif not wiringpi.digitalRead(GREEN_BUTTON):
                            exit_reason = "button"
                        elif received_signal != 0:
                            exit_reason = "signal"
                        elif time.time() - motion_start > ROOF_TRAVEL_TIMEOUT_S:
                            exit_reason = "timeout"
                            notify_mattermost("critical", "Roof motor TIMEOUT after {}s during closing - motor stopped".format(ROOF_TRAVEL_TIMEOUT_S))
                    print(time.strftime("%Y%m%d_%H%M%S"), "event to stop closing the roof received: {}".format(exit_reason))
                    if exit_reason == "button":
                        notify_mattermost("critical", "Green button pressed during closing - motor stopped")
                    received_signal = 0
                    write_roof_motor_stop()
                    next_possible_green_button_action = GREEN_BUTTON_OPENING
                    if read_roof_sensor_close():
                        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is closed")
                        notify_mattermost("info", "Roof is closed")
                else:
                    logging.debug('roof already closed')
            elif roof_opening:
                if not read_roof_sensor_open():
                    print(time.strftime("%Y%m%d_%H%M%S"), "Opening roof")
                    write_roof_motor_open()
                    next_possible_green_button_action = GREEN_BUTTON_STOP
                    print('')
                    print(time.strftime("%Y%m%d_%H%M%S"), "Wait for an event to stop opening the roof")
                    motion_start = time.time()
                    exit_reason = None
                    while exit_reason is None:
                        if read_roof_sensor_open():
                            exit_reason = "sensor"
                        elif not wiringpi.digitalRead(GREEN_BUTTON):
                            exit_reason = "button"
                        elif received_signal != 0:
                            exit_reason = "signal"
                        elif time.time() - motion_start > ROOF_TRAVEL_TIMEOUT_S:
                            exit_reason = "timeout"
                            notify_mattermost("critical", "Roof motor TIMEOUT after {}s during opening - motor stopped".format(ROOF_TRAVEL_TIMEOUT_S))
                    print(time.strftime("%Y%m%d_%H%M%S"), "event to stop opening the roof received: {}".format(exit_reason))
                    if exit_reason == "button":
                        notify_mattermost("critical", "Green button pressed during opening - motor stopped")
                    received_signal = 0
                    write_roof_motor_stop()
                    next_possible_green_button_action = GREEN_BUTTON_CLOSING
                    if read_roof_sensor_open():
                        print(time.strftime("%Y%m%d_%H%M%S"), "Roof is open")
                        notify_mattermost("warn", "Roof is open")
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
    notify_mattermost("critical", "Controller started")


_exit_notify_done = False


def _exit_notify():
    """atexit + SIGTERM handler synchronously posts the exit alert (daemon
    threads would be killed before delivery, so notify_mattermost's async
    path isn't safe here)."""
    global _exit_notify_done
    if _exit_notify_done:
        return
    _exit_notify_done = True
    _notify_mattermost_worker("critical", "Controller exiting")


atexit.register(_exit_notify)


def _sigterm_handler(signum, frame):
    print(time.strftime("%Y%m%d_%H%M%S"), "SIGTERM received, exiting cleanly")
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _sigterm_handler)


def _crash_notify(where, exc_type, exc_value, exc_tb):
    """Synchronously notify of an unhandled exception with backtrace, then mark
    the exit-notify as already done so atexit doesn't also post a generic
    'Controller exiting' for the same crash."""
    global _exit_notify_done
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip()
    msg = "Controller CRASHED in {}: {}: {}\n```\n{}\n```".format(
        where, exc_type.__name__, exc_value, tb_str)
    if len(msg) > 3500:
        msg = msg[:3500] + "\n... (truncated)\n```"
    _notify_mattermost_worker("critical", msg)
    _exit_notify_done = True


def _main_excepthook(exc_type, exc_value, exc_tb):
    _crash_notify("main", exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _main_excepthook


def _exit_motor_stop():
    """Belt-and-braces: guarantee the motor is OFF on any exit path
    (clean exit, SIGTERM, crash). Registered LAST so it runs FIRST in atexit's
    LIFO order — before the (slow) Mattermost POST and before the daemon
    RoofControlThread is killed by interpreter shutdown."""
    try:
        write_roof_motor_stop()
    except Exception:
        pass


atexit.register(_exit_motor_stop)


def main():
    """ main """
    init()

    roof_control_thread = RoofControlThread()
    roof_control_thread.daemon = True   # don't block interpreter shutdown — atexit (_exit_motor_stop) ensures motor is OFF before the daemon is killed
    roof_control_thread.start()

    try:
        FLASK_APP.run(debug=False, host='0.0.0.0')
    except KeyboardInterrupt:
        print(time.strftime("%Y%m%d_%H%M%S"), "KeyboardInterrupt caught in flask. Stop any running motor")
        write_roof_motor_stop()


if __name__ == '__main__':
    main()
