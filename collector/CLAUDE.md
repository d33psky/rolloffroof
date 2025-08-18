# Observatory Data Collection & Weather Safety System

## System Architecture Overview

The observatory's weather monitoring and safety system runs on the **lxc-rrd container** and processes sensor data from multiple sources in the observatory. The system implements a comprehensive safety evaluation pipeline that determines whether conditions are safe for telescope operations.

**Data Flow:**
```
Observatory Sensors (RPI) → TCP Server (port 7777) → Parallel Processing:
                                                   ├── MySQL Database (sensors_to_database.py)
                                                   └── RRD Databases (rrdtool)
                                                       ↓
Decision Engine ← MySQL Database → Safety Evaluation → Mattermost Notifications
     ↓
Visualization ← RRD Databases → PNG Graphs → Web Server (NFS mount)
```

## Core Components on lxc-rrd Container

### TCP Server (`collector/server.pl`)
**Location:** `/home/user/rrd/server.pl`
**Port:** 7777
**Protocol:** TCP

The main data ingestion service that:
- Listens for RRD update messages from observatory systems
- Receives sensor data from `loops.pl` running on Raspberry Pi in observatory
- Validates incoming messages (must start with "update")
- Dispatches data in parallel to both:
  - MySQL database via `sensors_to_database.py`
  - RRD databases via `rrdtool`

**Startup:** Automatically started at boot via cron:
```bash
@reboot cd ./rrd/ && screen -dmS server ./server.pl
```

**Monitoring:** View live process with `screen -rx` (detach with Ctrl-A D)

### MySQL Data Pipeline (`collector/sensors_to_database.py`)
**Purpose:** Converts RRD update format to MySQL records

**Key Features:**
- Parses RRD update syntax: `update database.rrd -t keys values`
- Maps sensor data to MySQL columns using predefined dictionaries
- Implements smart INSERT/UPDATE logic:
  - INSERT: When more than 1 minute since last record
  - UPDATE: When within same minute (multiple sensor updates)
- Automatically triggers weather safety evaluation via `query_sky_and_obsy_conditions.py`

**Database Mappings:**
```python
# RRD filename → MySQL table prefix
'tempandhum-observatory.rrd': 'observatory',
'tempandhum-outside.rrd': 'outside', 
'skytemperature-BAA.rrd': 'BAA1_temperature',
'skytemperature-BCC.rrd': 'BCC1_temperature',
'sqm.rrd': 'sqm1',
'rainsensor.rrd': 'rainsensor1',
'ups.rrd': 'ups1'
```

**Sensor Data Types:**
- **Temperature/Humidity:** Observatory and outside conditions, dewpoint calculation
- **Sky Temperature:** Infrared sensors BAA and BCC (cloud detection)  
- **Sky Quality:** SQM readings and frequency measurements
- **Rain Detection:** Pulse counting and drop calculation
- **UPS Monitoring:** Status, voltage, battery charge, temperature
- **All-Sky Camera:** Temperature, humidity, star count

### Weather Safety Engine (`collector/query_sky_and_obsy_conditions.py`)
**Purpose:** Comprehensive safety evaluation for telescope operations

**Safety Conditions Evaluated:**

1. **Database Connectivity** 
   - Ensures sensor data is current (within 2 minutes)
   - Triggers emergency closure if data feed fails

2. **Sky Darkness (SQM)**
   - Threshold: ≥17.5 mag/arcsec² (adjustable with hysteresis)
   - Historical validation: Must be dark for sufficient duration
   - Prevents opening during twilight/dawn

3. **Cloud Detection (Infrared Sky Temperature)**
   - **BAA Sensor:** Sky-sensor temperature delta ≥13°C
   - **BCC Sensor:** Sky-sensor temperature delta ≥14°C
   - Clear sky shows large temperature difference
   - Either sensor can satisfy clear sky requirement

4. **Rain Detection**
   - Threshold: ≤1 drop per minute
   - Historical validation: Must be dry for extended period
   - Prevents water damage to equipment

5. **Power Status (UPS)**
   - Requires mains power connection (status = 1)
   - Battery charge ≥99% 
   - Handles temporary self-test conditions

6. **Hysteresis System**
   - Prevents rapid oscillation between open/closed states
   - Different thresholds when roof is already open vs. closed
   - Configurable delays prevent immediate re-opening after closure

**Decision Logic:**
- **All conditions met:** Roof can open ("All sensors are go")
- **Any condition fails:** Roof must close (detailed reason provided)
- **State changes:** Logged to events table and sent to Mattermost

**Notification System:**
- Mattermost webhook integration
- Alerts sent only on state changes (not continuous status)
- Detailed reason codes for troubleshooting

### Visualization Pipeline (`collector/graph.sh`)
**Purpose:** Generate real-time sensor graphs for web monitoring

**Graph Generation:**
- Uses `rrdtool graph` to create PNG images
- Multiple time periods: 1 day, 1 week, 1 month, 1 year
- Configurable sizes: small, large, huge (for different use cases)

**Graph Types:**
- **Environmental:** Temperature, humidity, dewpoint (observatory + outside)
- **Sky Conditions:** SQM brightness, luminosity, infrared sky temperature
- **Weather:** Rain sensor drops per minute
- **Power:** UPS status, voltage, battery levels
- **All-Sky Camera:** Star count, temperature/humidity

**Output Location:** `/webs/lambermont.dyndns.org/www/astro/rrd/`
**Web Access:** Served via NFS mount to web server container

**Execution:** Runs every minute via cron:
```bash
* * * * * cd ./rrd/ && ./graph.sh
```

## External Components

### Data Sources (Observatory)
- **`loops.pl`** on Raspberry Pi
  - Collects sensor data every 60 seconds
  - Reads GPIO sensors (temperature/humidity)
  - Interfaces with specialized hardware (SQM, rain sensor, UPS)
  - Sends formatted RRD update messages to lxc-rrd:7777

### Data Consumers
- **`weather_status.py`** - JSON API service for observatory computer
  - Returns current roof status and reasons
  - Used by telescope control software for safety decisions
  - Configurable database connection via `.my.cnf.python`

## Database Schema

### `sensors` Table
Primary time-series table storing all sensor readings:
- **Timestamp:** `create_time` (UTC)
- **Environmental:** `observatory_temperature1`, `observatory_humidity1`, `observatory_dewpoint1`
- **Sky Conditions:** `BAA1_temperature_sky`, `BAA1_temperature_sensor`, `BCC1_temperature_sky`, `BCC1_temperature_sensor`
- **Sky Quality:** `sqm1_sqm`, `sqm1_frequency`, `sqm1_luminosity`
- **Weather:** `rainsensor1_drops`, `rainsensor1_pulses`
- **Power:** `ups1_status`, `ups1_linev`, `ups1_bcharge`, `ups1_timeleft`
- **All-Sky:** `allskycam1_temperature`, `allskycam1_humidity`, `allskycam1_stars`

### `roof` Table
Safety decision log:
- **`roof_id`** - Primary key
- **`create_time`** - Decision timestamp (UTC)
- **`sensors_id`** - Link to sensor data used
- **`open_ok`** - Boolean: safe to open (1) or must close (0)
- **`reasons`** - Detailed explanation of decision

### `events` Table
State change tracking:
- **`create_time`** - Event timestamp
- **`event`** - Type: "opening", "closing", "stays open", "stays closed"  
- **`reason`** - Detailed explanation

## Configuration & Thresholds

### Safety Thresholds
```python
# Sky darkness (with hysteresis)
sqm_threshold = 17.5  # mag/arcsec²
sqm_hysteresis = 3.0  # when roof already open

# Cloud detection (sky temperature delta)
baa_threshold = 13.0  # degrees C
bcc_threshold = 14.0  # degrees C
temp_hysteresis = 3.0  # when roof already open

# Rain detection
rain_threshold = 1.0  # drops per minute

# Power requirements  
ups_battery_min = 99.0  # percent charge
```

### Database Configuration
- **Host:** lxc-rrd (localhost for server.pl)
- **Database:** observatory1
- **User:** sens
- **Password:** sens
- **Port:** 3306

### External Integrations
- **Mattermost webhook:** Stored in `~/.mattermosturl`
- **Web graphs:** NFS mount to separate web server container

## Production Environment

### Container Access
```bash
ssh lxc-rrd
```

### Process Monitoring
```bash
# View live server.pl output
screen -rx

# Detach from screen session
# Press: Ctrl-A then D
```

### Directory Structure
```
~/rolloffroof/          # Git repository (development)
├── collector/          # Scripts analyzed in this document
└── ...

~/rrd/                  # Production runtime directory
├── server.pl          # Main TCP server
├── sensors_to_database.py
├── query_sky_and_obsy_conditions.py  
├── graph.sh
└── ...
```

### Cron Jobs
```bash
# Start main server at boot
@reboot cd ./rrd/ && screen -dmS server ./server.pl

# Generate graphs every minute  
* * * * * cd ./rrd/ && ./graph.sh
```

## Known Issues & Technical Debt

1. **Empty Script:** `weather_safety_service.py` exists but contains only a shebang line
2. **Manual Sync:** Scripts must be manually copied from git repo (`~/rolloffroof/`) to runtime (`~/rrd/`)
3. **Mixed Languages:** System uses both Perl (server.pl, loops.pl) and Python (data processing)
4. **Hardcoded Paths:** Various scripts contain absolute paths that may need adjustment
5. **Single Point of Failure:** All data flows through one TCP server process

## Safety Features & Error Handling

### Sensor Criticality System
The system categorizes sensors by criticality and handles failures appropriately:

**Critical Sensors (failure causes closure):**
- **Infrared sky temperature sensors (BAA1/BCC1):** 5-minute tolerance
  - Essential for cloud detection
  - Failure assumes cloudy conditions → close roof
  - Either sensor can satisfy clear sky requirement

**Non-Critical Sensors (failure allows continued operation):**
- **SQM (Sky Quality Meter):** 3-minute tolerance
  - Nice-to-have darkness measurement
  - Failure assumes acceptable conditions → continue operation
- **Rain sensor:** 2-minute tolerance  
  - Important but not immediately critical
  - Failure assumes no rain → continue operation
- **UPS monitoring:** 2-minute tolerance
  - Power status monitoring
  - Failure assumes power OK → continue operation
- **Temperature/humidity sensors:** Eternal tolerance
  - Environmental monitoring only
  - Failure has no impact on safety decisions

### Fail-Safe Design
- **Database timeout:** Main data feed failure triggers immediate closure
- **Multiple sensors:** Redundant cloud detection (BAA + BCC infrared sensors)
- **Historical validation:** Conditions must be stable over time
- **State persistence:** Previous decisions influence current thresholds (hysteresis)
- **Graceful degradation:** Non-critical sensor failures don't halt operations

### Error Recovery
- **SQL injection protection:** Empty sensor values converted to NULL
- **NoneType handling:** Missing data handled without crashes
- **Sensor age validation:** Data freshness checked before use
- **Automatic fallback:** Non-critical sensors default to safe assumptions

## Monitoring & Troubleshooting

### Log Sources
- **Screen session:** Live server.pl output (`screen -rx`)
- **Database logs:** MySQL `roof` and `events` tables
- **Mattermost:** Real-time notifications of state changes

### Common Issues & Messages

**Database & Connectivity:**
- **"DB not ok":** Main sensor data feed interrupted → emergency closure
- **"DB last timestamp X is More than 2 minutes ago":** Data feed timeout

**Sensor-Specific Failures:**
- **"SQM sensor data too old → skip SQM check":** Non-critical, continues operation
- **"Rain sensor data too old → assume no rain":** Non-critical, continues operation  
- **"UPS sensor data too old → assume power OK":** Non-critical, continues operation
- **"BAA1/BCC1 infrared sensor data too old → assume cloudy":** Critical, forces closure

**Weather Conditions:**
- **"Not dark enough":** SQM reading below threshold (when sensor working)
- **"Too cloudy":** Both infrared sensors show warm sky
- **"Started raining":** Rain sensor detecting moisture (when sensor working)
- **"UPS on battery":** Power failure or UPS self-test (when sensor working)

**SQL/Processing Errors:**
- **"You have an error in your SQL syntax":** Usually empty sensor values (now handled)
- **"TypeError: unorderable types: NoneType() >= float()":** Missing sensor data (now handled)

This system provides comprehensive weather monitoring and automated safety decisions for observatory operations, ensuring equipment protection while maximizing observing opportunities.