#!/usr/bin/env python3

"""
Mount Position Monitor - Checks mount parking position accuracy and corrects drift

This program monitors the mount's parking status and position accuracy:
1. Checks if INDI thinks the mount is parked
2. Confirms parking status with mount's own API
3. Compares position data between INDI and mount API
4. Detects position drift from expected park position
5. Attempts automated corrections via INDI first, then mount API
6. Sends Mattermost alerts if corrections fail

Connections:
- INDI server at 192.168.100.14:7624 (persistent TCP)
- Mount API at 192.168.100.73:3490 (persistent TCP)

Main loop runs every 60 seconds with comprehensive logging.
"""

import argparse
import datetime
import json
import logging
import math
import os
import shlex
import socket
import subprocess
import sys
import threading
import time
import yaml
from pathlib import Path
from queue import Queue, Empty
import requests


class MountPositionConfig:
    """Configuration loader for mount position monitor"""
    
    def __init__(self, config_file=None):
        self.config = self.load_config(config_file)
        
    def load_config(self, config_file):
        """Load configuration from YAML file"""
        if config_file is None:
            # Try to find a default config file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_configs = [
                os.path.join(script_dir, "10micron_park_position_monitor_config.yaml")
            ]
            
            for config_path in default_configs:
                if os.path.exists(config_path):
                    config_file = config_path
                    break
            
            if config_file is None:
                raise FileNotFoundError("No configuration file found. Please specify --config or create 10micron_park_position_monitor_config.yaml")
        
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


class IndiConnection:
    """Thread-safe INDI connection handler"""
    
    def __init__(self, host, port, config):
        self.host = host
        self.port = port
        self.config = config
        self.logger = logging.getLogger('mount_position_monitor.indi')
        self.socket = None
        self.connected = False
        self.request_queue = Queue()
        self.response_queue = Queue()
        self.thread = None
        self.running = False
        
    def start(self):
        """Start the INDI connection thread"""
        self.running = True
        self.thread = threading.Thread(target=self._connection_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """Stop the INDI connection thread"""
        self.running = False
        if self.thread:
            self.thread.join()
            
    def _connection_loop(self):
        """Main connection loop running in thread"""
        while self.running:
            try:
                if not self.connected:
                    self._connect()
                
                # Process requests
                try:
                    request = self.request_queue.get(timeout=1.0)
                    response = self._execute_command(request['command'])
                    self.response_queue.put({
                        'id': request['id'],
                        'response': response,
                        'error': None
                    })
                except Empty:
                    continue
                    
            except Exception as e:
                self.logger.error(f"INDI connection error: {e}")
                self.connected = False
                if self.socket:
                    self.socket.close()
                    self.socket = None
                time.sleep(5)  # Wait before reconnecting
                
    def _connect(self):
        """Establish connection to INDI server"""
        try:
            self.logger.info(f"Connecting to INDI server at {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.config.get('timeouts.indi_command', 5))
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.logger.info("INDI connection established")
        except Exception as e:
            self.logger.error(f"Failed to connect to INDI: {e}")
            self.connected = False
            
    def _execute_command(self, command):
        """Execute INDI command via subprocess"""
        try:
            timeout = self.config.get('timeouts.indi_command', 5)
            result = subprocess.run(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=timeout,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"INDI command failed: {command}, error: {e.stderr}")
            return None
        except subprocess.TimeoutExpired:
            self.logger.error(f"INDI command timed out: {command}")
            return None
            
    def get_property(self, property_name):
        """Get INDI property value"""
        command = f"indi_getprop -h {self.host} -1 '{property_name}'"
        request_id = f"get_{int(time.time())}"
        
        self.request_queue.put({
            'id': request_id,
            'command': command
        })
        
        # Wait for response
        timeout = self.config.get('timeouts.indi_command', 5)
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.response_queue.get(timeout=0.1)
                if response['id'] == request_id:
                    return response['response']
            except Empty:
                continue
                
        return None
        
    def set_property(self, property_name, value):
        """Set INDI property value"""
        command = f"indi_setprop -h {self.host} '{property_name}={value}'"
        request_id = f"set_{int(time.time())}"
        
        self.request_queue.put({
            'id': request_id,
            'command': command
        })
        
        # Wait for response
        timeout = self.config.get('timeouts.indi_command', 5)
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.response_queue.get(timeout=0.1)
                if response['id'] == request_id:
                    return response['response'] is not None
            except Empty:
                continue
                
        return False


class MountApiConnection:
    """Thread-safe Mount API connection handler"""
    
    def __init__(self, host, port, config):
        self.host = host
        self.port = port
        self.config = config
        self.logger = logging.getLogger('mount_position_monitor.mount_api')
        self.socket = None
        self.connected = False
        self.lock = threading.Lock()
        self.thread = None
        self.running = False
        
    def start(self):
        """Start the Mount API connection thread"""
        self.running = True
        self.thread = threading.Thread(target=self._connection_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """Stop the Mount API connection thread"""
        self.running = False
        if self.thread:
            self.thread.join()
            
    def _connection_loop(self):
        """Main connection loop running in thread"""
        while self.running:
            try:
                if not self.connected:
                    self._connect()
                time.sleep(1)  # Keep connection alive
            except Exception as e:
                self.logger.error(f"Mount API connection error: {e}")
                self.connected = False
                if self.socket:
                    self.socket.close()
                    self.socket = None
                time.sleep(5)  # Wait before reconnecting
                
    def _connect(self):
        """Establish connection to Mount API"""
        try:
            self.logger.info(f"Connecting to Mount API at {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.config.get('timeouts.mount_command', 5))
            self.socket.connect((self.host, self.port))
            
            # Set Ultra Precision Mode for better coordinate format
            self.logger.info("Setting Ultra Precision Mode")
            self.socket.sendall(b"#:U2#")
            time.sleep(0.5)  # Allow command to process
            
            self.connected = True
            self.logger.info("Mount API connection established with Ultra Precision Mode")
        except Exception as e:
            self.logger.error(f"Failed to connect to Mount API: {e}")
            self.connected = False
            
    def send_command(self, command):
        """Send command to mount and return response"""
        with self.lock:
            if not self.connected:
                return None
                
            try:
                self.socket.sendall(command.encode())
                
                # Some commands like #:hP# don't return anything, just send success
                if command in ["#:hP#", "#:PO#", "#:KA#"]:
                    time.sleep(0.1)  # Brief pause for command processing
                    return "OK"  # Indicate command was sent successfully
                
                time.sleep(0.5)  # Wait for response
                
                response = b''
                while True:
                    data = self.socket.recv(128)
                    if not data:
                        break
                    response += data
                    if b'#' in response:  # Mount responses end with #
                        break
                        
                return response.decode('ascii').strip()
            except Exception as e:
                self.logger.error(f"Mount command failed: {command}, error: {e}")
                self.connected = False
                return None


class MountPositionMonitor:
    """Main mount position monitoring class"""
    
    def __init__(self, indi_host, config_file=None):
        self.config = MountPositionConfig(config_file)
        self.indi_host = indi_host
        self.logger = logging.getLogger('mount_position_monitor')
        
        # Initialize connections
        self.indi = IndiConnection(
            self.config.get('connections.indi_host', indi_host), 
            self.config.get('connections.indi_port', 7624), 
            self.config
        )
        self.mount_api = MountApiConnection(
            self.config.get('connections.mount_host', '192.168.100.73'),
            self.config.get('connections.mount_port', 3490),
            self.config
        )
        
        # State tracking
        self.last_mattermost_alert = 0
        self.consecutive_failures = 0
        
    def start(self):
        """Start the monitoring system"""
        self.logger.info("Starting mount position monitor")
        self.indi.start()
        self.mount_api.start()
        
        # Wait for connections to establish
        time.sleep(2)
        
        try:
            self.main_loop()
        except KeyboardInterrupt:
            self.logger.info("Shutdown requested by user")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the monitoring system"""
        self.logger.info("Stopping mount position monitor")
        self.indi.stop()
        self.mount_api.stop()
        
    def main_loop(self):
        """Main monitoring loop - runs every 60 seconds"""
        loop_sleep = self.config.get('monitoring.loop_sleep_seconds', 60)
        
        while True:
            start_time = time.time()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
            
            self.logger.info(f"[{timestamp}] Starting monitoring cycle")
            
            try:
                self.check_mount_position()
            except Exception as e:
                self.logger.error(f"[{timestamp}] Monitoring cycle failed: {e}")
                
            # Calculate sleep time to maintain 60-second intervals
            elapsed = time.time() - start_time
            sleep_time = max(0, loop_sleep - elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def check_mount_position(self):
        """Main position checking logic"""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Step 1: Check if INDI thinks mount is parked
        indi_park_property = self.config.get('indi.mount.park_property')
        indi_park_status = self.indi.get_property(indi_park_property)
        
        self.logger.info(f"[{timestamp}] INDI park status: {indi_park_status}")
        
        if not indi_park_status or indi_park_status != self.config.get('indi.mount.park_setting'):
            self.logger.info(f"[{timestamp}] Mount not parked according to INDI, skipping position check")
            return
            
        # Step 2: Confirm with mount API
        mount_status = self.mount_api.send_command("#:Gstat#")
        self.logger.info(f"[{timestamp}] Mount API status: {mount_status}")
        
        if mount_status != "5#":
            self.logger.warning(f"[{timestamp}] Mount API reports not parked (status: {mount_status})")
            self.attempt_park_correction()
            return
            
        # Step 3: Get position data from both sources
        mount_ra = self.mount_api.send_command("#:GR#")
        mount_dec = self.mount_api.send_command("#:GD#")
        
        indi_ra_property = self.config.get('indi.mount.coord_ra_property')
        indi_dec_property = self.config.get('indi.mount.coord_dec_property')
        
        indi_ra = self.indi.get_property(indi_ra_property) if indi_ra_property else None
        indi_dec = self.indi.get_property(indi_dec_property) if indi_dec_property else None
        
        self.logger.info(f"[{timestamp}] Mount API position - RA: {mount_ra}, DEC: {mount_dec}")
        self.logger.info(f"[{timestamp}] INDI position - RA: {indi_ra}, DEC: {indi_dec}")
        
        # Step 4: Check for position drift
        if self.check_position_drift(mount_ra, mount_dec, timestamp):
            self.attempt_park_correction()
        else:
            self.logger.info(f"[{timestamp}] Mount position is within acceptable tolerance")
            self.consecutive_failures = 0  # Reset failure counter on success
    
    def check_position_drift(self, ra, dec, timestamp):
        """Check if mount position has drifted from park position"""
        try:
            expected_ra = self.config.get('monitoring.park_position.ra')
            expected_dec = self.config.get('monitoring.park_position.dec')
            max_offset = self.config.get('monitoring.park_position.max_offset', 1.0)
            
            if not expected_dec or not dec:
                self.logger.warning(f"[{timestamp}] Cannot check drift - missing DEC data")
                return False
                
            # Parse DEC from mount (Ultra Precision format: +DD:MM:SS.SS#)
            dec_cleaned = dec.replace('#', '').strip()
            try:
                # Handle both formats: +DD:MM:SS.SS or +DD*MM (fallback)
                if ':' in dec_cleaned:
                    # Ultra precision format: +DD:MM:SS.SS
                    parts = dec_cleaned.replace('+', '').replace('-', '').split(':')
                    deg = float(parts[0])
                    min_val = float(parts[1]) if len(parts) > 1 else 0
                    sec = float(parts[2]) if len(parts) > 2 else 0
                    dec_degrees = deg + min_val/60 + sec/3600
                    if dec_cleaned.startswith('-'):
                        dec_degrees = -dec_degrees
                elif '*' in dec_cleaned:
                    # Fallback format: +DD*MM
                    parts = dec_cleaned.replace('+', '').replace('-', '').split('*')
                    deg = float(parts[0])
                    min_val = float(parts[1]) if len(parts) > 1 else 0
                    dec_degrees = deg + min_val/60
                    if dec_cleaned.startswith('-'):
                        dec_degrees = -dec_degrees
                else:
                    # Simple decimal degrees
                    dec_degrees = float(dec_cleaned)
            except:
                self.logger.error(f"[{timestamp}] Failed to parse DEC: {dec}")
                return False
                
            dec_drift = abs(dec_degrees - float(expected_dec))
            
            # Check RA drift if available
            ra_drift = 0
            if expected_ra and ra:
                ra_cleaned = ra.replace('#', '').strip()
                try:
                    # Parse RA (Ultra Precision format: HH:MM:SS.SS)
                    if ':' in ra_cleaned:
                        parts = ra_cleaned.split(':')
                        hours = float(parts[0])
                        min_val = float(parts[1]) if len(parts) > 1 else 0
                        sec = float(parts[2]) if len(parts) > 2 else 0
                        ra_hours = hours + min_val/60 + sec/3600
                    else:
                        # Simple decimal hours
                        ra_hours = float(ra_cleaned)
                    
                    ra_drift = abs(ra_hours - float(expected_ra))
                    # Handle RA wraparound (0-24 hours)
                    if ra_drift > 12:
                        ra_drift = 24 - ra_drift
                except:
                    self.logger.error(f"[{timestamp}] Failed to parse RA: {ra}")
                    ra_drift = 0
            
            total_drift = max(dec_drift, ra_drift)
            
            self.logger.info(f"[{timestamp}] Position drift check - Expected RA: {expected_ra}, Actual: {ra}")
            self.logger.info(f"[{timestamp}] Position drift check - Expected DEC: {expected_dec}, Actual: {dec_degrees}")
            self.logger.info(f"[{timestamp}] Drift - RA: {ra_drift}, DEC: {dec_drift}, Max: {total_drift}")
            
            if total_drift > max_offset:
                self.logger.warning(f"[{timestamp}] Position drift detected: {total_drift} degrees (threshold: {max_offset})")
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"[{timestamp}] Error checking position drift: {e}")
            return False
    
    def attempt_park_correction(self):
        """Attempt to correct park position via INDI first, then Mount API"""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # First attempt: INDI park command
        self.logger.info(f"[{timestamp}] Attempting park correction via INDI")
        
        indi_park_property = self.config.get('indi.mount.park_property')
        indi_park_setting = self.config.get('indi.mount.park_setting')
        
        if self.indi.set_property(indi_park_property, indi_park_setting):
            self.logger.info(f"[{timestamp}] INDI park command sent successfully")
            
            # Wait and check if it worked
            time.sleep(self.config.get('timeouts.mount_park', 30))
            if self.verify_park_position():
                self.logger.info(f"[{timestamp}] INDI park correction successful")
                self.consecutive_failures = 0
                return
                
        # Second attempt: Mount API park command
        self.logger.info(f"[{timestamp}] Attempting park correction via Mount API")
        
        response = self.mount_api.send_command("#:hP#")
        if response == "OK":
            self.logger.info(f"[{timestamp}] Mount API park command sent successfully")
            
            # Wait and check if it worked
            time.sleep(self.config.get('timeouts.mount_park', 30))
            if self.verify_park_position():
                self.logger.info(f"[{timestamp}] Mount API park correction successful")
                self.consecutive_failures = 0
                return
                
        # Both corrections failed
        self.consecutive_failures += 1
        self.logger.error(f"[{timestamp}] Park correction failed (attempt {self.consecutive_failures})")
        
        # Send alert if needed
        self.send_mattermost_alert_if_needed()
    
    def verify_park_position(self):
        """Verify that the mount is properly parked"""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        
        # Check mount status
        mount_status = self.mount_api.send_command("#:Gstat#")
        if mount_status != "5#":
            self.logger.warning(f"[{timestamp}] Park verification failed - mount status: {mount_status}")
            return False
            
        # Check position
        mount_ra = self.mount_api.send_command("#:GR#")
        mount_dec = self.mount_api.send_command("#:GD#")
        if not self.check_position_drift(mount_ra, mount_dec, timestamp):
            return True
            
        return False
    
    def send_mattermost_alert_if_needed(self):
        """Send Mattermost alert if enough time has passed since last alert"""
        current_time = time.time()
        alert_interval = self.config.get('alerting.mattermost_interval_seconds', 60)
        
        if current_time - self.last_mattermost_alert >= alert_interval:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
            message = f"[{timestamp}] Mount Position Monitor ALERT: Park correction failed {self.consecutive_failures} times. Mount may have drifted from park position."
            
            self.send_mattermost_alert(message)
            self.last_mattermost_alert = current_time
    
    def send_mattermost_alert(self, message):
        """Send alert to Mattermost using existing pattern"""
        try:
            home = str(Path.home())
            mattermost_url_file = open(home + "/.mattermosturl", 'r')
            url = mattermost_url_file.read().rstrip('\n')
            mattermost_url_file.close()
            
            payload = {'text': message}
            r = requests.post(url, data={'payload': json.dumps(payload, sort_keys=True, indent=4)})
            
            if r.status_code != 200:
                try:
                    error_response = json.loads(r.text)
                except ValueError:
                    error_response = {'message': r.text, 'status_code': r.status_code}
                self.logger.error(f"Mattermost alert failed: {error_response}")
            else:
                self.logger.info(f"Mattermost alert sent: {message}")
                
        except Exception as e:
            self.logger.error(f"Failed to send Mattermost alert: {e}")


def setup_logging(debug=False):
    """Setup logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Mount Position Monitor - Checks parking position accuracy and corrects drift"
    )
    parser.add_argument("--indi_host", default="192.168.100.14", 
                       help="INDI server host (default: 192.168.100.14)")
    parser.add_argument("--config", 
                       help="Configuration file path")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    parser.add_argument("--once", action="store_true",
                       help="Run once and exit (for testing)")
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    try:
        monitor = MountPositionMonitor(args.indi_host, args.config)
        
        if args.once:
            monitor.indi.start()
            monitor.mount_api.start()
            time.sleep(2)  # Wait for connections
            monitor.check_mount_position()
            monitor.stop()
        else:
            monitor.start()
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()