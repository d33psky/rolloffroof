#!/usr/bin/env python3

# weather safe ?
# yes:
#     scheduler running ?
#     yes:
#         ok
#     no:
#         start scheduler
# no:
#     scheduler running ?
#     yes:
#         stop scheduler
#         park mount
#         close roof
#         warm ccd
#     no:
#         ok

import argparse
import sys
import time
import shlex
import subprocess
import logging
from ekos_cli import EkosDbus

INDI_DOME_PARK_PROPERTY = 'Dome Scripting Gateway.DOME_PARK.PARK'
INDI_DOME_PARK_PROPERTY_PARK_SETTING = 'On'
INDI_WEATHER_PROPERTY = 'Weather Meta.WEATHER_STATUS.STATION_STATUS'
INDI_WEATHER_PROPERTY_OK_SETTING = 'Ok'
WEATHER_META_STATION_INDEXES = {1, 2}
INDI_MOUNT_PARK_PROPERTY = '10micron.TELESCOPE_PARK.PARK'
INDI_MOUNT_PARK_PROPERTY_PARK_SETTING = 'On'
INDI_MOUNT_TRACK_STATE = '10micron.TELESCOPE_TRACK_STATE.TRACK_ON'
INDI_MOUNT_TRACK_STATE_PROPERTY = 'Off'
INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC = '10micron.EQUATORIAL_EOD_COORD.DEC'
INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_PROPERTY = '39'
INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_MAX_OFFSET = '1'
INDI_CAMERA_COOLER = 'ASI1600MM-Cool.CCD_COOLER.COOLER_ON'
INDI_CAMERA_COOLER_PROPERTY = 'Off'
MAIN_LOOP_SLEEP_SECONDS = 60
INDI_COMMAND_TIMEOUT = 5
MOUNT_PARK_TIMEOUT = 60
ROOF_CLOSE_TIMEOUT = 60


class BasicIndi():
    def __init__(self, host):
        self.host = host
        self.logger = logging.getLogger('ekos_sentinel')

    def _run(self, cmd, timeout):
        try:
            ws = subprocess.run(shlex.split(cmd),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=timeout, check=True
                                )
        except subprocess.CalledProcessError as cpe:
            self.logger.critical(
                "Command [{}] exited with value [{}] stdout [{}] stderr [{}]".format(cmd, cpe.returncode,
                                                                                     cpe.stdout.rstrip(),
                                                                                     cpe.stderr.rstrip()))
            return None
        except subprocess.TimeoutExpired:
            self.logger.critical("Command [{}] timed out after {} seconds".format(cmd, timeout))
            return None
        return ws

    def get_weather_safety(self, weather_meta_station_indexes, indi_command_timeout):
        safe = 0
        for station in weather_meta_station_indexes:
            cmd = "indi_getprop -h {host} -1 '{property}_{station}'".format(
                host=self.host, property=INDI_WEATHER_PROPERTY, station=station)
            ws = self._run(cmd, indi_command_timeout)
            if not ws:
                self.logger.critical("get_weather_safety failed")
                return False
            self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
            if ws.stdout.rstrip() == INDI_WEATHER_PROPERTY_OK_SETTING:
                safe += 1
        if safe == len(weather_meta_station_indexes):
            return True
        else:
            return False

    def get_roof_safety(self, indi_command_timeout):
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=INDI_DOME_PARK_PROPERTY)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_roof_safety failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() == INDI_DOME_PARK_PROPERTY_PARK_SETTING:
            return True
        else:
            return False

    def get_mount_safety(self, indi_command_timeout):
        # multiple steps
        # 1) INDI_MOUNT_PARK_PROPERTY must be INDI_MOUNT_PARK_PROPERTY_PARK_SETTING
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=INDI_MOUNT_PARK_PROPERTY)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_mount_safety failed at step 1")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() != INDI_MOUNT_PARK_PROPERTY_PARK_SETTING:
            return False
        # 2) INDI_MOUNT_TRACK_STATE must be INDI_MOUNT_TRACK_STATE_PROPERTY
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=INDI_MOUNT_TRACK_STATE)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_mount_safety failed at step 2")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() != INDI_MOUNT_TRACK_STATE_PROPERTY:
            return False
        # 3) INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC needs to be within INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_MAX_OFFSET
        #    to INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_PROPERTY (park position)
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host,
                                                              property=INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_mount_safety failed at step 3")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if abs(float(ws.stdout.rstrip())) - abs(float(INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_PROPERTY)) > float(
                INDI_MOUNT_EQUATORIAL_EOD_COORD_DEC_MAX_OFFSET):
            return False
        return True

    def park_mount(self, indi_command_timeout, mount_park_timeout):
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host, property=INDI_MOUNT_PARK_PROPERTY,
                                                                     setting=INDI_MOUNT_PARK_PROPERTY_PARK_SETTING)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("park_mount failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.returncode != 0:
            return False
        mount_parked = False
        mount_park_time = 0
        while not mount_parked and mount_park_time < mount_park_timeout:
            mount_parked = self.get_mount_safety(indi_command_timeout)
            time.sleep(1)
            mount_park_time += 1
        return mount_parked

    def close_roof(self, indi_command_timeout, roof_close_timeout):
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host, property=INDI_DOME_PARK_PROPERTY,
                                                                     setting=INDI_DOME_PARK_PROPERTY_PARK_SETTING)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("close_roof failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.returncode != 0:
            return False
        roof_closed = False
        roof_close_time = 0
        while not roof_closed and roof_close_time < roof_close_timeout:
            roof_closed = self.get_roof_safety(indi_command_timeout=indi_command_timeout)
            time.sleep(1)
            roof_close_time += 1
        return roof_closed

    def warm_camera(self, indi_command_timeout):
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host,
                                                                     property=INDI_CAMERA_COOLER,
                                                                     setting=INDI_CAMERA_COOLER_PROPERTY)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("warm_camera failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        return ws.returncode == 0


def alert_and_abort(reason):
    logger = logging.getLogger('ekos_sentinel')
    logger.critical("TODO wake human stating {}".format(reason))
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Ekos Sentinel')
    parser.add_argument('--debug', action='store_true', help='enable debug level verbosity')
    parser.add_argument('--once', action='store_true', help='run only once, useful for debugging')
    parser.add_argument('--indi_host', required=True, type=str, help='INDI server address')
    parser.add_argument('--get_roof_safety', action='store_true', help='for testing: only call get_roof_safety')
    parser.add_argument('--get_mount_safety', action='store_true', help='for testing: only call get_mount_safety')
    args = parser.parse_args()

    logger = logging.getLogger('ekos_sentinel')
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    null_handler = logging.NullHandler()
    logger.addHandler(null_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter("%(asctime)s %(name)s %(levelname)-8s %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    ekos_dbus = EkosDbus()
    basic_indi = BasicIndi(host=args.indi_host)

    if args.get_mount_safety:
        logger.info(
            "get_mount_safety = [{}]".format(basic_indi.get_mount_safety(indi_command_timeout=INDI_COMMAND_TIMEOUT)))
        quit(0)

    if args.get_roof_safety:
        logger.info(
            "get_roof_safety = [{}]".format(basic_indi.get_roof_safety(indi_command_timeout=INDI_COMMAND_TIMEOUT)))
        quit(0)

    looping = True
    while looping:
        if args.once:
            looping = False
        weather_safety_status = basic_indi.get_weather_safety(weather_meta_station_indexes=WEATHER_META_STATION_INDEXES,
                                                              indi_command_timeout=INDI_COMMAND_TIMEOUT)
        roof_safety_status = basic_indi.get_roof_safety(indi_command_timeout=INDI_COMMAND_TIMEOUT)
        if weather_safety_status:
            if roof_safety_status:
                logger.info('weather is safe, roof is closed, start ekos scheduler')
                ekos_dbus.start_scheduler()
            else:
                logger.info('weather is safe, roof is open')
        else:
            if roof_safety_status:
                logger.info('weather is unsafe, roof is closed')
            else:
                logger.warning('weather is unsafe, roof is open, stop ekos scheduler')
                ekos_dbus.stop_scheduler()
                # there's no way to tell yet if stopping the ekos scheduler succeeded or not
                # furthermore stopping the scheduler does not park or close anything, so that is done here :

                logger.warning('park mount')
                success = basic_indi.park_mount(indi_command_timeout=INDI_COMMAND_TIMEOUT,
                                                mount_park_timeout=MOUNT_PARK_TIMEOUT)
                if not success:
                    alert_and_abort('Failed to park the mount')

                logger.warning('close roof')
                success = basic_indi.close_roof(indi_command_timeout=INDI_COMMAND_TIMEOUT,
                                                roof_close_timeout=ROOF_CLOSE_TIMEOUT)
                if not success:
                    alert_and_abort('Failed to close the roof')

                logger.warning('warm camera')
                success = basic_indi.warm_camera(indi_command_timeout=INDI_COMMAND_TIMEOUT)
                if not success:
                    logger.warning('failed to warm the camera, this is not critical to safety so just continue')
        if looping:
            logger.debug("sleep {}".format(MAIN_LOOP_SLEEP_SECONDS))
            time.sleep(MAIN_LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
