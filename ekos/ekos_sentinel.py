#!/usr/bin/env python3

DESCRIPTION = """
EKOS Sentinel, version 2.0 - Automated observatory safety system with configuration support.

Originally created because EKOS scheduler in KStars 3.2.0 waits for good weather before 
opening the observatory, but does not close down when weather gets bad. While newer KStars 
versions may have improved this, this script ensures proper safety shutdown regardless of 
KStars version and prevents future regressions.

Main loop:
    weather safe ?
    yes:
        roof closed ? -> ok (or start scheduler if configured)
    no:
        roof open ? -> EMERGENCY SHUTDOWN:
            - stop scheduler
            - abort all ekos operations (capture/focus/align/guide)
            - park mount
            - close cap (if configured)
            - close roof/dome
            - warm camera

Configuration:
    Uses YAML configuration files for hardware setup:
    - ekos_sentinel_config_production.yaml (real observatory hardware)
    - ekos_sentinel_config_simulator.yaml (INDI simulators for testing)
    
    Specify config with --config parameter or place in same directory.
"""

# All configuration constants have been moved to YAML configuration files:
# - ekos_sentinel_config_production.yaml (real hardware)
# - ekos_sentinel_config_simulator.yaml (INDI simulators)

import argparse
import sys
import time
import shlex
import subprocess
import logging
import yaml
import os
from ekos_cli import EkosDbus


class SentinelConfig:
    def __init__(self, config_file=None):
        self.config = self.load_config(config_file)
        
    def load_config(self, config_file):
        """Load configuration from YAML file"""
        if config_file is None:
            # Try to find a default config file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_configs = [
                os.path.join(script_dir, "ekos_sentinel_config.yaml"),
                os.path.join(script_dir, "ekos_sentinel_config_production.yaml"),
                os.path.join(script_dir, "ekos_sentinel_config_simulator.yaml")
            ]
            
            for config_path in default_configs:
                if os.path.exists(config_path):
                    config_file = config_path
                    break
            
            if config_file is None:
                raise FileNotFoundError("No configuration file found. Please specify --config or create ekos_sentinel_config.yaml")
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
            
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            
        print(f"Loaded configuration from: {config_file}")
        if 'description' in config:
            print(f"Description: {config['description']}")
            
        return config
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation (e.g., 'indi.mount.park_property')"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value


class BasicIndi():
    def __init__(self, host, config):
        self.host = host
        self.config = config
        self.logger = logging.getLogger('ekos_sentinel')
        self.max_retries = config.get('safety.max_retries', 1)
        self.safe_counter = 0
        self.safe_count_max = config.get('safety.unsafe_count_max', 3)

    def get_max_retries(self):
        return self.max_retries

    def set_max_retries(self, retries):
        self.max_retries = int(retries)

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

    def get_weather_safety(self, indi_command_timeout):
        weather_property = self.config.get('indi.weather.property')
        weather_ok_setting = self.config.get('indi.weather.ok_setting')
        weather_stations = self.config.get('indi.weather.station_indexes', [1])
        
        if not weather_property:
            self.logger.warning("No weather property configured - assuming safe weather")
            return True
            
        safe = 0
        for station in weather_stations:
            cmd = "indi_getprop -h {host} -1 '{property}_{station}'".format(
                host=self.host, property=weather_property, station=station)
            ws = self._run(cmd, indi_command_timeout)
            if not ws:
                self.logger.critical("get_weather_safety failed")
                return False
            self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
            if ws.stdout.rstrip() == weather_ok_setting:
                safe += 1
        if safe == len(weather_stations):
            self.safe_counter = 0
            return True
        else:
            self.safe_counter += 1
            if self.safe_counter >= self.safe_count_max:
                self.logger.info("weather unsafe, count {count} >= max {max_count}, report UNSAFE".format(count=self.safe_counter, max_count=self.safe_count_max))
                return False
            else:
                self.logger.info("weather unsafe, count {count} < max {max_count}, report SAFE".format(count=self.safe_counter, max_count=self.safe_count_max))
                return True

    def get_roof_safety(self, indi_command_timeout):
        dome_property = self.config.get('indi.dome.park_property')
        dome_park_setting = self.config.get('indi.dome.park_setting')
        
        if not dome_property:
            self.logger.warning("No dome property configured - assuming roof is safe")
            return True
            
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=dome_property)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_roof_safety failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() == dome_park_setting:
            return True
        else:
            return False

    def get_cap_safety(self, indi_command_timeout):
        cap_property = self.config.get('indi.cap.property')
        cap_setting = self.config.get('indi.cap.setting')
        
        if not cap_property:
            self.logger.debug("get_cap_safety fakes True because no cap property is configured")
            return True
            
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=cap_property)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_cap_safety failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() == cap_setting:
            return True
        else:
            return False

    def get_mount_safety(self, indi_command_timeout):
        mount_park_property = self.config.get('indi.mount.park_property')
        mount_park_setting = self.config.get('indi.mount.park_setting')
        mount_track_property = self.config.get('indi.mount.track_state_property')
        mount_track_setting = self.config.get('indi.mount.track_state_setting')
        mount_coord_property = self.config.get('indi.mount.coord_dec_property')
        mount_park_position = self.config.get('indi.mount.coord_dec_park_position')
        mount_max_offset = self.config.get('indi.mount.coord_dec_max_offset')
        
        if not mount_park_property:
            self.logger.warning("No mount park property configured - assuming mount is safe")
            return True
            
        # multiple steps
        # 1) Mount park property must be in park setting
        cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=mount_park_property)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("get_mount_safety failed at step 1")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.stdout.rstrip() != mount_park_setting:
            return False
            
        # 2) Mount tracking must be off
        if mount_track_property:
            cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=mount_track_property)
            ws = self._run(cmd, indi_command_timeout)
            if not ws:
                self.logger.critical("get_mount_safety failed at step 2")
                return False
            self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
            if ws.stdout.rstrip() != mount_track_setting:
                return False
                
        # 3) Mount position must be within offset of park position
        if mount_coord_property and mount_park_position and mount_max_offset:
            cmd = "indi_getprop -h {host} -1 '{property}'".format(host=self.host, property=mount_coord_property)
            ws = self._run(cmd, indi_command_timeout)
            if not ws:
                self.logger.critical("get_mount_safety failed at step 3")
                return False
            self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
            if abs(float(ws.stdout.rstrip())) - abs(float(mount_park_position)) > float(mount_max_offset):
                return False
                
        return True

    def park_mount(self, indi_command_timeout, mount_park_timeout):
        tries = 0
        mount_parked = False
        while not mount_parked and tries < self.max_retries:
            mount_parked = self._park_mount(indi_command_timeout, mount_park_timeout)
            tries += 1
        return mount_parked

    def _park_mount(self, indi_command_timeout, mount_park_timeout):
        mount_park_property = self.config.get('indi.mount.park_property')
        mount_park_setting = self.config.get('indi.mount.park_setting')
        
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host, property=mount_park_property,
                                                                     setting=mount_park_setting)
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

    def close_cap(self, indi_command_timeout, cap_close_timeout):
        cap_property = self.config.get('indi.cap.property')
        if not cap_property:
            self.logger.debug("close_cap fakes True because no cap property is configured")
            return True
        tries = 0
        cap_closed = False
        while not cap_closed and tries < self.max_retries:
            cap_closed = self._close_cap(indi_command_timeout, cap_close_timeout)
            tries += 1
        return cap_closed

    def _close_cap(self, indi_command_timeout, cap_close_timeout):
        cap_property = self.config.get('indi.cap.property')
        cap_setting = self.config.get('indi.cap.setting')
        
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host, property=cap_property,
                                                                     setting=cap_setting)
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("close_cap failed")
            return False
        self.logger.debug("{} {} {}".format(__class__, cmd, ws.stdout.rstrip()))
        if ws.returncode != 0:
            return False
        cap_closed = False
        cap_close_time = 0
        while not cap_closed and cap_close_time < cap_close_timeout:
            cap_closed = self.get_cap_safety(indi_command_timeout=indi_command_timeout)
            time.sleep(1)
            cap_close_time += 1
        return cap_closed

    def close_roof(self, indi_command_timeout, roof_close_timeout):
        tries = 0
        roof_closed = False
        while not roof_closed and tries < self.max_retries:
            roof_closed = self._close_roof(indi_command_timeout, roof_close_timeout)
            tries += 1
        return roof_closed

    def _close_roof(self, indi_command_timeout, roof_close_timeout):
        dome_property = self.config.get('indi.dome.park_property')
        dome_setting = self.config.get('indi.dome.park_setting')
        
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host, property=dome_property,
                                                                     setting=dome_setting)
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
        camera_property = self.config.get('indi.camera.cooler_property')
        if not camera_property:
            self.logger.debug("warm_camera fakes True because no camera cooler property is configured")
            return True
        tries = 0
        camera_warmed = False
        while not camera_warmed and tries < self.max_retries:
            camera_warmed = self._warm_camera(indi_command_timeout)
            tries += 1
        return camera_warmed

    def _warm_camera(self, indi_command_timeout):
        camera_property = self.config.get('indi.camera.cooler_property')
        camera_setting = self.config.get('indi.camera.cooler_setting')
        
        cmd = "indi_setprop -h {host} '{property}={setting}'".format(host=self.host,
                                                                     property=camera_property,
                                                                     setting=camera_setting)
        self.logger.info("warm_camera: executing command: {}".format(cmd))
        ws = self._run(cmd, indi_command_timeout)
        if not ws:
            self.logger.critical("warm_camera failed")
            time.sleep(1)
            return False
        self.logger.info("warm_camera: command completed with return code: {}, stdout: [{}], stderr: [{}]".format(
            ws.returncode, ws.stdout.rstrip(), ws.stderr.rstrip()))
        return ws.returncode == 0


def alert_and_abort(reason):
    logger = logging.getLogger('ekos_sentinel')
    logger.critical("TODO wake human stating {}".format(reason))
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION,
                                     epilog='Only --indi-host is required for normal operation, the rest is for debugging and testing',
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--indi_host', required=True, type=str, help='INDI server address')
    parser.add_argument('--config', type=str, help='configuration file path (YAML format)')
    parser.add_argument('--indi_command_retries', type=str,
                        help='try INDI commands this amount of times before giving up, defaults to 1')
    parser.add_argument('--debug', action='store_true', help='enable debug level verbosity')
    parser.add_argument('--once', action='store_true', help='run only once, useful for debugging')
    parser.add_argument('--get_weather_safety', action='store_true', help='for testing: only call get_weather_safety')
    parser.add_argument('--get_mount_safety', action='store_true', help='for testing: only call get_mount_safety')
    parser.add_argument('--get_cap_safety', action='store_true', help='for testing: only call get_cap_safety')
    parser.add_argument('--get_roof_safety', action='store_true', help='for testing: only call get_roof_safety')
    parser.add_argument('--park_mount', action='store_true', help='for testing: only call park_mount')
    parser.add_argument('--close_cap', action='store_true', help='for testing: only call close_cap')
    parser.add_argument('--close_roof', action='store_true', help='for testing: only call close_roof')
    parser.add_argument('--warm_camera', action='store_true', help='for testing: only call warm_camera')
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

    # Load configuration
    config = SentinelConfig(args.config)
    
    ekos_dbus = EkosDbus()
    basic_indi = BasicIndi(host=args.indi_host, config=config)

    if args.indi_command_retries:
        basic_indi.set_max_retries(args.indi_command_retries)

    if args.get_weather_safety:
        logger.info(
            "get_weather_safety = [{}]".format(
                basic_indi.get_weather_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))))
        quit(0)

    if args.get_mount_safety:
        logger.info(
            "get_mount_safety = [{}]".format(basic_indi.get_mount_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))))
        quit(0)

    if args.get_roof_safety:
        logger.info(
            "get_roof_safety = [{}]".format(basic_indi.get_roof_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))))
        quit(0)

    if args.get_cap_safety:
        logger.info(
            "get_cap_safety = [{}]".format(basic_indi.get_cap_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))))
        quit(0)

    if args.park_mount:
        logger.info(
            "park_mount = [{}]".format(basic_indi.park_mount(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                             mount_park_timeout=config.get('timeouts.mount_park', 60))))
        quit(0)

    if args.close_cap:
        logger.info(
            "close_cap = [{}]".format(basic_indi.close_cap(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                           cap_close_timeout=config.get('timeouts.cap_close', 60))))
        quit(0)

    if args.close_roof:
        logger.info(
            "close_roof = [{}]".format(basic_indi.close_roof(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                             roof_close_timeout=config.get('timeouts.roof_close', 60))))
        quit(0)

    if args.warm_camera:
        logger.info(
            "warm_camera = [{}]".format(basic_indi.warm_camera(indi_command_timeout=config.get('timeouts.indi_command', 5))))
        quit(0)

    looping = True
    while looping:
        try:
            if args.once:
                looping = False
            weather_safety_status = basic_indi.get_weather_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))
            roof_safety_status = basic_indi.get_roof_safety(indi_command_timeout=config.get('timeouts.indi_command', 5))
            
            if weather_safety_status is None or roof_safety_status is None:
                sleep_time = config.get('safety.main_loop_sleep_seconds', 60)
                logger.error('Failed to get safety status from INDI server - INDI server may be down. Will retry in {} seconds.'.format(sleep_time))
                if looping:
                    logger.debug("sleep {}".format(sleep_time))
                    time.sleep(sleep_time)
                continue
                
            if weather_safety_status:
                if roof_safety_status:
                    logger.info('weather is safe, roof is closed, but we do not start ekos scheduler')
                    # ekos_dbus.start_scheduler()
                else:
                    logger.info('weather is safe, roof is open')
            else:
                if roof_safety_status:
                    logger.info('weather is unsafe, roof is closed')
                else:
                    # TODO: Future enhancement - detect if scheduler was active vs manual imaging
                    # If scheduler was active, we should sleep here to let scheduler handle shutdown sequence
                    # If manual imaging, proceed immediately with our emergency sequence
                    #sleep_time = config.get('safety.main_loop_sleep_seconds', 60)
                    #logger.warning('weather is unsafe, roof is open. Sleep {} seconds in case ekos scheduler handles shutdown'.format(2 * sleep_time))
                    #time.sleep(sleep_time)
                    logger.warning('weather is unsafe, roof is open, stop all ekos operations')
                    try:
                        ekos_dbus.stop_scheduler()
                        logger.info('Stopped ekos scheduler')
                    except Exception as e:
                        logger.error('Failed to stop ekos scheduler: {}'.format(e))
                    
                    # Stop all active imaging operations (capture, focus, align, guide)
                    try:
                        success = ekos_dbus.abort_all_operations()
                        if success:
                            logger.info('Successfully aborted all ekos operations')
                        else:
                            logger.warning('Some ekos operations failed to abort - see previous messages')
                    except Exception as e:
                        logger.error('Failed to abort ekos operations: {}'.format(e))
                    
                    # Now proceed with hardware safety actions

                    logger.warning('park mount')
                    success = basic_indi.park_mount(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                    mount_park_timeout=config.get('timeouts.mount_park', 60))
                    if not success:
                        alert_and_abort("Failed to park the mount, tried {} times".format(basic_indi.get_max_retries()))

                    logger.warning('close cap')
                    success = basic_indi.close_cap(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                   cap_close_timeout=config.get('timeouts.cap_close', 60))
                    if not success:
                        alert_and_abort("Failed to close the cap, tried {} times".format(basic_indi.get_max_retries()))

                    logger.warning('close roof')
                    success = basic_indi.close_roof(indi_command_timeout=config.get('timeouts.indi_command', 5),
                                                    roof_close_timeout=config.get('timeouts.roof_close', 60))
                    if not success:
                        alert_and_abort("Failed to close the roof, tried {} times".format(basic_indi.get_max_retries()))

                    logger.warning('warm camera')
                    success = basic_indi.warm_camera(indi_command_timeout=config.get('timeouts.indi_command', 5))
                    if not success:
                        logger.warning('failed to warm the camera, this is not critical to safety so just continue')
            if looping:
                sleep_time = config.get('safety.main_loop_sleep_seconds', 60)
                logger.debug("sleep {}".format(sleep_time))
                time.sleep(sleep_time)
        except Exception as e:
            sleep_time = config.get('safety.main_loop_sleep_seconds', 60)
            logger.error('Unexpected error in main loop: {}. Will retry in {} seconds.'.format(e, sleep_time))
            if looping:
                time.sleep(sleep_time)


if __name__ == "__main__":
    main()
