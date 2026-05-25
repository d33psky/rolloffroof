# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an observatory control system for managing a roll-off roof telescope observatory. The system integrates hardware sensors, motor control, weather monitoring, and astronomical equipment coordination. It's designed to safely operate a motorized roof that can open/close based on safety conditions and mount status.

## Key Components

### Roof Control System
- **roof/controller.py**: Flask-based web API for roof control with physical button integration
- **manualroofcontrol.py**: Standalone script for manual roof operation
- Motor control via GPIO relays with safety sensors for open/closed positions
- Safety feature: checks if mount is parked before allowing roof closure

### Hardware Integration
- **C executables**: Light sensor (TSL237), rain sensor (RG11), I2C device readers
- **GPIO sensors**: Temperature/humidity (DHT22), roof position sensors
- **Relay control**: Motor direction and start/stop
- Built using CMake with pigpio library for hardware interfacing

### Data Collection & Monitoring
- **loops.pl**: Main sensor data collection loop (Perl)
- **collector/sensors_to_database.py**: RRD to MySQL data pipeline
- **collector/weather_safety_service.py**: Weather condition monitoring
- Continuous monitoring of temperature, humidity, dewpoint, sky conditions, UPS status

### Astronomical Equipment
- **ekos/ekos_cli.py**: KStars/Ekos integration via D-Bus for telescope control
- **ekos/ekos_sentinel.py**: Automated weather monitoring and safety shutdown system
- **roof/is-the-mount-parked.py**: Mount parking status checker
- Coordinates between roof operation and telescope positioning
- Autonomous weather monitoring with emergency shutdown sequence

### Shell Scripts & Utilities
- **allsky1/**, **hazcam2/**: Camera control scripts
- **etc/rc.local**: System startup configuration
- **status.pl**: System status reporting

## Build & Development Commands

### Building C Components
```bash
mkdir build && cd build
cmake ..
make
```
This builds sensor reading utilities that interface with pigpio library.

### Running Core Services
```bash
# Start roof controller (Flask web interface)
python3 roof/controller.py

# Manual roof control
python3 manualroofcontrol.py

# Start sensor data collection
perl loops.pl

# Check mount parking status
python3 roof/is-the-mount-parked.py
```

### Database Operations
```bash
# Feed sensor data to database
python3 collector/sensors_to_database.py update <db> -t <keys> <values>

# Monitor weather safety
python3 collector/weather_safety_service.py
```

### Ekos/KStars Control
```bash
# Start Ekos
python3 ekos/ekos_cli.py --start_ekos

# Load profile and start
python3 ekos/ekos_cli.py --profile "ProfileName"

# Load and start scheduler
python3 ekos/ekos_cli.py --load_schedule /path/to/schedule.esl --start_scheduler

# Abort individual Ekos operations
python3 ekos/ekos_cli.py --abort_capture
python3 ekos/ekos_cli.py --abort_focus
python3 ekos/ekos_cli.py --abort_align
python3 ekos/ekos_cli.py --abort_guide

# Abort all Ekos operations (capture, focus, align, guide)
python3 ekos/ekos_cli.py --abort_all

# Run Ekos Sentinel (weather monitoring with automatic shutdown)
python3 ekos/ekos_sentinel.py --indi_host localhost --config ekos/ekos_sentinel_config_production.yaml

# Run with simulator configuration for testing
python3 ekos/ekos_sentinel.py --indi_host localhost --config ekos/ekos_sentinel_config_simulator.yaml

# Test individual safety checks
python3 ekos/ekos_sentinel.py --indi_host localhost --config ekos/ekos_sentinel_config_simulator.yaml --get_weather_safety
python3 ekos/ekos_sentinel.py --indi_host localhost --config ekos/ekos_sentinel_config_simulator.yaml --get_mount_safety
python3 ekos/ekos_sentinel.py --indi_host localhost --config ekos/ekos_sentinel_config_simulator.yaml --get_roof_safety

# Test individual control actions
python3 ekos/ekos_sentinel.py --indi_host localhost --park_mount
python3 ekos/ekos_sentinel.py --indi_host localhost --close_roof
python3 ekos/ekos_sentinel.py --indi_host localhost --warm_camera

# Run once for debugging
python3 ekos/ekos_sentinel.py --indi_host localhost --once --debug
```

## Configuration

### Ekos Sentinel Configuration
The ekos_sentinel.py uses YAML configuration files to support different hardware setups:

- **ekos_sentinel_config_production.yaml**: Real observatory hardware configuration
- **ekos_sentinel_config_simulator.yaml**: INDI simulator configuration for testing

Configuration sections:
- `indi`: INDI device properties for weather, mount, dome, camera, cap
- `timeouts`: Command and operation timeouts
- `safety`: Safety thresholds and loop timing

The configuration system automatically finds config files or accepts `--config` parameter.

## Architecture Notes

### Safety Systems
- Mount parking verification before roof closure (roof/controller.py:152-162)
- Continuous sensor monitoring with automatic stops
- Physical button override capabilities
- Signal handling for emergency stops
- **Ekos Sentinel**: Automated weather monitoring with emergency shutdown sequence
  - Monitors weather conditions via INDI weather stations
  - Automatically stops scheduler, parks mount, closes cap/roof, warms camera on unsafe weather
  - Implements safety counter (3 consecutive unsafe readings) to prevent false triggers
  - Multi-step mount safety verification (park status, tracking off, position check)

### Network Communication
- Roof controller runs Flask web API on 0.0.0.0:5000
- Mount communication via TCP socket to 192.168.100.73:3490
- RRD data transmission to 192.168.100.81:7777
- INDI server communication for telescope/weather equipment control
- D-Bus communication with KStars/Ekos for scheduler control

### Data Flow
1. Hardware sensors → loops.pl → RRD files → MySQL database
2. Weather data → safety evaluation → roof control decisions
3. Mount status → safety check → roof operation approval
4. INDI weather stations → ekos_sentinel.py → automated shutdown sequence
5. D-Bus → KStars/Ekos scheduler control → coordinated observatory operations

### Hardware Dependencies
- Raspberry Pi GPIO via wiringpi/pigpio libraries
- I2C devices for environmental sensors
- Relay modules for motor control
- UPS monitoring via apcaccess

## Development Notes

- Python scripts use environment detection (ARM vs non-ARM) for hardware mocking
- MySQL credentials hardcoded as 'sens'/'sens' for local database
- Time-based database operations prevent excessive updates
- Signal handling (SIGUSR1/SIGUSR2) for remote control