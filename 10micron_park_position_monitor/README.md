# 10micron Park Position Monitor

A Python program that monitors the 10micron mount's parking position accuracy and automatically corrects drift.

## Overview

This program continuously monitors whether the mount is properly parked and detects any position drift from the expected park position. When drift is detected, it attempts automated corrections via INDI first, then the mount's API if needed. If corrections fail, it sends alerts to Mattermost.

## Features

- **Dual Connection Monitoring**: Checks both INDI server and mount API for park status
- **Position Drift Detection**: Compares actual position with configured park position  
- **Automated Correction**: Attempts park corrections via INDI first, then mount API
- **Ultra Precision Mode**: Uses mount's high-precision coordinate format
- **Mattermost Alerting**: Sends alerts when corrections fail
- **Comprehensive Logging**: ISO8601 timestamped logs for all operations

## Requirements

- Python 3.6+
- Required packages: `yaml`, `requests`
- INDI server running at configured host
- 10micron mount accessible via TCP
- Mattermost webhook URL in `~/.mattermosturl`

## Configuration

Edit `10micron_park_position_monitor_config.yaml`:

```yaml
connections:
  indi_host: "192.168.100.14"
  indi_port: 7624
  mount_host: "192.168.100.73"
  mount_port: 3490

monitoring:
  park_position:
    ra: 18.42   # Expected park RA in hours
    dec: 40.08  # Expected park DEC in degrees
    max_offset: 1.0  # Maximum drift tolerance
```

## Usage

```bash
# Normal operation (runs continuously)
./10micron_park_position_monitor.py

# Run once for testing
./10micron_park_position_monitor.py --once --debug

# Specify custom config
./10micron_park_position_monitor.py --config /path/to/config.yaml

# Log output to file
./10micron_park_position_monitor.py 2>&1 | tee monitor.log
```

## How It Works

1. **Main Loop** (60-second intervals):
   - Check if INDI reports mount as parked
   - Confirm park status with mount API
   - Get position data from both sources
   - Compare with configured park position

2. **Drift Detection**:
   - Parse RA/DEC coordinates in ultra precision format
   - Calculate drift from expected park position
   - Handle RA wraparound (0-24 hours)

3. **Correction Process** (when drift detected):
   - First attempt: Send INDI park command
   - Wait and verify position
   - Second attempt: Send mount API park command (`#:hP#`)
   - Wait and verify position again

4. **Alerting**:
   - Send Mattermost alert if both corrections fail
   - Alert every minute until issue is resolved
   - Log all actions with timestamps

## Connection Details

- **INDI Connection**: Persistent TCP connection with threading
- **Mount API Connection**: Persistent TCP with Ultra Precision Mode (`#:U2#`)
- **Commands Used**:
  - `#:Gstat#` - Get mount status (5 = parked)
  - `#:GR#` - Get Right Ascension
  - `#:GD#` - Get Declination  
  - `#:hP#` - Park mount command

## Logging

All operations are logged with ISO8601 timestamps:
- Info: Normal operations and status checks
- Warning: Drift detected, correction attempts
- Error: Failed corrections, connection issues

## Safety Notes

- Only monitors and corrects when mount is already supposed to be parked
- Does not interfere with normal mount operations
- Fails safe - alerts human operators if automated corrections don't work
- Uses configurable drift tolerance to avoid false positives