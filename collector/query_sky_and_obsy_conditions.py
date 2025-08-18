#!/usr/bin/env python3

import datetime
import json
from pathlib import Path
import requests
import MySQLdb

db = MySQLdb.connect(
    host="lxc-rrd",
    port=3306,
    user='sens',
    passwd='sens',
    db="observatory1")
db_cursor = db.cursor()

def check_db(minutes):
    sql = """
      SELECT  sensors_id
             ,create_time
        FROM sensors
    ORDER BY create_time DESC
       LIMIT 1;
    """
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    try:
        sensors_id  = db_result_tuple[0]
        db_date = db_result_tuple[1]
    except:
        raise
    if db_date < datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes) :
        print("DB last timestamp {db_date} is More than {minutes} minutes ago -> close".format(db_date=db_date, minutes=minutes))
        print("Stop_Imaging (do not wait). Park (wait), Close_Roof")
        quit(1)
    else:
        print("DB last timestamp {db_date} is Less than {minutes} minutes ago -> open".format(db_date=db_date, minutes=minutes))
        return(sensors_id)

def check_sensor_data_age(sensor_column, max_age_minutes, sensor_name):
    """Check if sensor data is recent enough to be considered valid"""
    sql = """
      SELECT create_time
        FROM sensors
       WHERE {sensor_column} IS NOT NULL
    ORDER BY create_time DESC
       LIMIT 1;
    """.format(sensor_column=sensor_column)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    
    if db_result_tuple is None:
        print("{sensor_name} has no data -> assuming sensor failure".format(sensor_name=sensor_name))
        return False
        
    last_data_time = db_result_tuple[0]
    age_minutes = (datetime.datetime.utcnow() - last_data_time).total_seconds() / 60
    
    if age_minutes <= max_age_minutes:
        return True
    else:
        print("{sensor_name} data is {age:.1f} minutes old (max {max_age} allowed) -> assuming sensor failure".format(
            sensor_name=sensor_name, age=age_minutes, max_age=max_age_minutes))
        return False

def check_sqm(sensors_id, sqm_min):
    # Check if SQM data is recent enough (3 minutes tolerance)
    if not check_sensor_data_age('sqm1_sqm', 3, 'SQM'):
        print("SQM sensor data too old -> skip SQM check (observatory can continue)")
        return True  # Non-critical sensor, allow operation
    
    sql = """
      SELECT sqm1_sqm
        FROM sensors
       WHERE sensors_id = {sensors_id}
       LIMIT 1;
    """.format(sensors_id=sensors_id)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        sqm  = db_result_tuple[0]
    except:
        raise
    if sqm is None:
        print("SQM sensor data missing from current record -> skip SQM check")
        return True  # Allow operation without SQM data
    if sqm >= sqm_min:
        print("SQM {sqm} >= minimum {sqm_min} -> open".format(sqm=sqm, sqm_min=sqm_min))
        return(True)
    else:
        print("SQM {sqm} < minimum {sqm_min} -> close".format(sqm=sqm, sqm_min=sqm_min))
        return(False)

def check_sqm_past(sqm_min, seconds, outlier_count_max):
    sql = """
      SELECT COUNT(*)
        FROM sensors
       WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL {seconds} second)
         AND sqm1_sqm < {sqm_min};
    """.format(seconds=seconds, sqm_min=sqm_min)
    #print(sql)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        count  = db_result_tuple[0]
    except:
        raise
    if count <= outlier_count_max:
        print("SQM < minimum {sqm_min} count over the last {seconds} seconds is {count} <= {outlier_count_max} -> open".format(sqm_min=sqm_min, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(True)
    else:
        print("SQM < minimum {sqm_min} count over the last {seconds} seconds is {count} > {outlier_count_max} -> close".format(sqm_min=sqm_min, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(False)

def check_rain(sensors_id, drops_min):
    # Check if rain sensor data is recent enough (2 minutes tolerance)
    if not check_sensor_data_age('rainsensor1_drops', 2, 'Rain sensor'):
        print("Rain sensor data too old -> assume no rain (observatory can continue)")
        return True  # Assume no rain if sensor is down
    
    sql = """
      SELECT rainsensor1_drops
        FROM sensors
       WHERE sensors_id = {sensors_id}
       LIMIT 1;
    """.format(sensors_id=sensors_id)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        drops  = db_result_tuple[0]
    except:
        raise
    if drops is None:
        print("Rain sensor data missing from current record -> assume no rain")
        return True  # Assume no rain if data is missing
    if drops <= drops_min:
        print("Rain drops {drops} <= minimum {drops_min} -> open".format(drops=drops, drops_min=drops_min))
        return(True)
    else:
        print("Rain drops {drops} > minimum {drops_min} -> close".format(drops=drops, drops_min=drops_min))
        return(False)

def check_rain_past(drops_min, seconds, outlier_count_max):
    sql = """
      SELECT COUNT(*)
        FROM sensors
       WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL {seconds} second)
         AND rainsensor1_drops > {drops_min};
    """.format(seconds=seconds, drops_min=drops_min)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        count  = db_result_tuple[0]
    except:
        raise
    if count <= outlier_count_max:
        print("Rain drops <= minimum {drops_min} count over the last {seconds} seconds is {count} <= {outlier_count_max} -> open".format(drops_min=drops_min, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(True)
    else:
        print("Rain drops > minimum {drops_min} count over the last {seconds} seconds is {count} > {outlier_count_max} -> close".format(drops_min=drops_min, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(False)

def check_ups_is_on_mains(sensors_id, min_ups_bcharge):
    # Check if UPS data is recent enough (2 minutes tolerance)
    if not check_sensor_data_age('ups1_status', 2, 'UPS'):
        print("UPS sensor data too old -> assume power OK (observatory can continue)")
        return True  # Assume power is OK if UPS monitoring is down
    
    sql = """
      SELECT ups1_status, ups1_bcharge
        FROM sensors
       WHERE sensors_id = {sensors_id}
       LIMIT 1;
    """.format(sensors_id=sensors_id)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
#    print(db_result_tuple)
    try:
        ups_status  = db_result_tuple[0]
        ups_bcharge = db_result_tuple[1]
    except:
        raise
    if ups_status is None or ups_bcharge is None:
        print("UPS sensor data missing from current record -> assume power OK")
        return True  # Assume power is OK if data is missing
    if ups_status == 1 and ups_bcharge >= min_ups_bcharge:
        print("UPS is powered and battery charge {bcharge} >= {min_ups_bcharge} -> open".format(bcharge=ups_bcharge, min_ups_bcharge=min_ups_bcharge))
        return True
    else:
        if ups_status != 1:
            print("UPS is on battery (and battery charge is {bcharge}) -> close".format(bcharge=ups_bcharge))
        else:
            print("UPS is powered but battery charge {bcharge} < {min_ups_bcharge} -> open".format(bcharge=ups_bcharge, min_ups_bcharge=min_ups_bcharge))
        return False

def check_infrared(sensors_id, sensor, minimum_delta_t):
    # Check if infrared sensor data is recent enough (5 minutes tolerance for critical cloud detection)
    sensor_column = '{}_temperature_sensor'.format(sensor)
    if not check_sensor_data_age(sensor_column, 5, '{} infrared sensor'.format(sensor)):
        print("{sensor} infrared sensor data too old -> assume cloudy (close for safety)".format(sensor=sensor))
        return False  # Cloud sensors are critical - assume cloudy if down
    
    sql = """
      SELECT {sensor}_temperature_sensor
             , {sensor}_temperature_sky
             , {sensor}_temperature_sensor - {sensor}_temperature_sky
        FROM sensors
       WHERE sensors_id = {sensors_id}
       LIMIT 1;
    """.format(sensor=sensor, sensors_id=sensors_id)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        temperature_sensor = db_result_tuple[0]
        temperature_sky    = db_result_tuple[1]
        delta_t            = db_result_tuple[2]
    except:
        raise
    if temperature_sensor is None or temperature_sky is None or delta_t is None:
        print("Sensor {sensor} infrared data missing from current record -> assume cloudy".format(sensor=sensor))
        return False  # Assume cloudy for safety
    if delta_t >= minimum_delta_t:
        print("Sensor {sensor} sky temperature delta ({temperature_sensor} - {temperature_sky} = {delta_t}) >= {minimum_delta_t} -> open".format(sensor=sensor, temperature_sensor=temperature_sensor, temperature_sky=temperature_sky, delta_t=delta_t, minimum_delta_t=minimum_delta_t))
        return(True)
    else:
        print("Sensor {sensor} sky temperature delta ({temperature_sensor} - {temperature_sky} = {delta_t}) < {minimum_delta_t} -> close".format(sensor=sensor, temperature_sensor=temperature_sensor, temperature_sky=temperature_sky, delta_t=delta_t, minimum_delta_t=minimum_delta_t))
        return(False)

def check_infrared_past(sensor, minimum_delta_t, seconds, outlier_count_max):
    sql = """
      SELECT COUNT(*)
        FROM sensors
       WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL {seconds} second)
         AND {sensor}_temperature_sensor - {sensor}_temperature_sky < {minimum_delta_t};
    """.format(sensor=sensor, seconds=seconds, minimum_delta_t=minimum_delta_t)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        count  = db_result_tuple[0]
    except:
        raise
    if count < outlier_count_max:
        print("Sensor {sensor} sky temperature delta < {minimum_delta_t} count over the last {seconds} seconds is {count} <= {outlier_count_max} -> open".format(sensor=sensor, minimum_delta_t=minimum_delta_t, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(True)
    else:
        print("Sensor {sensor} sky temperature delta < {minimum_delta_t} count over the last {seconds} seconds is {count} > {outlier_count_max} -> close".format(sensor=sensor, minimum_delta_t=minimum_delta_t, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(False)

def last_event_long_enough_ago(event, seconds, outlier_count_max):
    sql = """
      SELECT COUNT(*)
        FROM events
       WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL {seconds} second)
         AND event = '{event}';
    """.format(event=event, seconds=seconds)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        count  = db_result_tuple[0]
    except:
        raise
    if count < outlier_count_max:
        print("Event {event} count over the last {seconds} seconds is {count} < {outlier_count_max} -> open".format(event=event, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(True)
    else:
        print("Event {event} count over the last {seconds} seconds is {count} >= {outlier_count_max} -> close".format(event=event, seconds=seconds, count=count, outlier_count_max=outlier_count_max))
        return(False)

def retrieve_previous_open_ok():
    sql = """
      SELECT create_time,open_ok
        FROM roof
    ORDER BY roof_id DESC
       LIMIT 1;
    """
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    last_open_ok = bool(db_result_tuple[1])
    print("Roof open status is {}".format(last_open_ok))
    return(last_open_ok)

#def retrieve_previous_open(sensors_id):
#    sql = """
#      SELECT open
#        FROM roof
#       WHERE sensors_id = {}
#       LIMIT 1;
#    """.format(sensors_id)
#    sql = """
#      SELECT create_time, open_ok
#        FROM roof
#    ORDER BY roof_id DESC
#       LIMIT 1;
#    """
#    db_cursor.execute(sql)
#    db_result_tuple = db_cursor.fetchone()
#    open = db_result_tuple[1]
#    return(bool(open))

def store_roof_status(utcnow, sensors_id, open_ok, reasons):
    sql_keys = []
    sql_values = []
    sql_keys.append("create_time")
    sql_values.append('"' + str(utcnow) + '"')
    sql_keys.append("sensors_id")
    sql_values.append(str(sensors_id))
    sql_keys.append("open_ok")
    sql_values.append(str(open_ok))
    sql_keys.append("reasons")
    sql_values.append('"' + reasons + '"')
    sql = """
INSERT INTO observatory1.roof ({keys})
     VALUES ({values});
    """.format(keys = ','.join(sql_keys),
               values = ','.join(sql_values))
    #print("{}".format(sql.lstrip().rstrip()))
    try:
        db_cursor.execute(sql)
        db.commit()
        #print(db_cursor.rowcount, "record inserted.")
    except:
        db.rollback()
        raise

#def get_roof_status(minutes):
#    sql = """
#      SELECT  open_ok
#             ,create_time
#        FROM roof
#    ORDER BY roof_id DESC
#       LIMIT 1;
#    """
#    db_cursor.execute(sql)
#    db_result_tuple = db_cursor.fetchone()
#    try:
#        last_open_ok = db_result_tuple[0]
#        db_date      = db_result_tuple[1]
#    except:
#        raise
#    if db_date < datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes) :
#        print("DB last timestamp {db_date} is More than {minutes} minutes ago -> close".format(db_date=db_date, minutes=minutes))
#        print("Stop_Imaging (do not wait). Park (wait), Close_Roof")
#        quit(1)
#    else:
#        return(last_open_ok)

def store_event(utcnow, event, reason = None):
    sql_keys = []
    sql_values = []
    sql_keys.append("create_time")
    sql_values.append('"' + str(utcnow) + '"')
    sql_keys.append("event")
    sql_values.append('"' + event + '"')
    if reason:
        sql_keys.append("reason")
        sql_values.append('"' + reason + '"')
    sql = """
INSERT INTO observatory1.events ({keys})
     VALUES ({values});
    """.format(keys = ','.join(sql_keys),
               values = ','.join(sql_values))
    #print("{}".format(sql.lstrip().rstrip()))
    try:
        db_cursor.execute(sql)
        db.commit()
        #print(db_cursor.rowcount, "record inserted.")
    except:
        db.rollback()
        raise

def sendToMattermost(url, message):
    print("Send to mattermost: {}".format(message))
    payload = {}
    payload['text'] = message
    r = requests.post(url, data={'payload': json.dumps(payload, sort_keys=True, indent=4)})
    if r.status_code != 200:
        try:
            r = json.loads(r.text)
        except ValueError:
            r = {'message': r.text, 'status_code': r.status_code}
            raise RuntimeError("{} ({})".format(r['message'], r['status_code']))

def main():
    home = str(Path.home())
    mattermost_url_file = open(home + "/.mattermosturl", 'r')
    url = mattermost_url_file.read().rstrip('\n')
    mattermost_url_file.close()

    sensors_id       = check_db(minutes=2)
#    roof_status      = get_roof_status(minutes=2)
#    if roof_status == 1:
    last_open_ok     = retrieve_previous_open_ok()
    if last_open_ok is True:
#        sqm_min_hysterese = 6
#        sqm_min_hysterese = 5
        sqm_min_hysterese = 1
#        minimum_delta_t_hysterese = 7
#        minimum_delta_t_hysterese = 5
#        minimum_delta_t_hysterese = 4
        minimum_delta_t_hysterese = 3
    else:
        sqm_min_hysterese = 0
        minimum_delta_t_hysterese = 0

#    required_baa_delta_t = 11
#    required_baa_delta_t = 17
    required_baa_delta_t = 30
    required_baa_delta_t = 18
    required_baa_delta_t = 15
    required_baa_delta_t = 13
    required_bcc_delta_t = 20
    required_bcc_delta_t = 14

    sqm_now_ok       = check_sqm(sensors_id, sqm_min=17.5 - sqm_min_hysterese)
#    sqm_now_ok       = check_sqm(sensors_id, sqm_min=16.5 - sqm_min_hysterese)
    rain_now_ok      = check_rain(sensors_id, drops_min=1)
    ups_now_ok1      = check_ups_is_on_mains(sensors_id, 99.0)
    if ups_now_ok1 is False:
        # might be self-test. check previous minute
        ups_now_ok2  = check_ups_is_on_mains(sensors_id - 1, 99.0)

    #infrared1_now_ok = check_infrared(sensors_id, sensor='BAA1', minimum_delta_t=20 - minimum_delta_t_hysterese)
    infrared1_now_ok = check_infrared(sensors_id, sensor='BAA1', minimum_delta_t=required_baa_delta_t - minimum_delta_t_hysterese)
    infrared2_now_ok = check_infrared(sensors_id, sensor='BCC1', minimum_delta_t=required_bcc_delta_t - minimum_delta_t_hysterese)

#    sqm_past_ok       = check_sqm_past(sqm_min=17.5 - sqm_min_hysterese, seconds=3600, outlier_count_max=5)
    sqm_past_ok       = check_sqm_past(sqm_min=16.5 - sqm_min_hysterese, seconds=300, outlier_count_max=5)
    rain_past_ok      = check_rain_past(drops_min=1, seconds=3600, outlier_count_max=2)
    #infrared1_past_ok = check_infrared_past(sensor='BAA1', minimum_delta_t=20 - minimum_delta_t_hysterese, seconds=3600, outlier_count_max=5)
    infrared1_past_ok = check_infrared_past(sensor='BAA1', minimum_delta_t=required_baa_delta_t - minimum_delta_t_hysterese, seconds=3600, outlier_count_max=5)
    infrared2_past_ok = check_infrared_past(sensor='BCC1', minimum_delta_t=required_bcc_delta_t - minimum_delta_t_hysterese, seconds=3600, outlier_count_max=5)

    closing_event_past_ok = last_event_long_enough_ago(event="closing", seconds=3600, outlier_count_max=1)
    #closing_event_past_ok = last_event_long_enough_ago(event="closing", seconds=60, outlier_count_max=1)

    reason_open = []
    reason_close = []
    if sensors_id:
        reason_open.append("DB ok")
    else:
        reason_close.append("DB not ok")

    if sqm_now_ok:
        if sqm_past_ok:
            reason_open.append("Dark long enough")
        else:
            reason_close.append("Not dark long enough")
    else:
        if sqm_past_ok:
            reason_close.append("Not dark enough anymore")
        else:
            reason_close.append("Still not dark enough")

    if rain_now_ok:
        if rain_past_ok:
            reason_open.append("Dry long enough")
        else:
            reason_close.append("Not dry long enough")
    else:
        if rain_past_ok:
            reason_close.append("Started raining")
        else:
            reason_close.append("Still raining")

    if ups_now_ok1:
        reason_open.append("UPS works")
        ups_now_ok = True
    else:
        if ups_now_ok2:
            reason_open.append("UPS selftest or on battery")
            ups_now_ok = True
        else:
            reason_close.append("UPS on battery")
            ups_now_ok = False

    if infrared1_now_ok or infrared2_now_ok:
        if infrared1_past_ok or infrared2_past_ok:
            reason_open.append("Clear long enough")
        else:
            reason_close.append("Not clear long enough")
    else:
        if infrared1_past_ok or infrared2_past_ok:
            reason_close.append("Too cloudy")
        else:
            reason_close.append("Still too cloudy")

    if closing_event_past_ok:
        reason_open.append("Roof has been closed long enough")
    else:
        reason_close.append("Roof was just closed")

    #print(reason_open)
    #print(reason_close)

    if sensors_id and sqm_now_ok and sqm_past_ok and rain_now_ok and rain_past_ok and ups_now_ok and (infrared1_now_ok or infrared2_now_ok) and (infrared1_past_ok or infrared2_past_ok) and closing_event_past_ok:
        open_ok = True
        reasons = "All sensors are go"
        #reasons = "{}".format(', '.join(reason_open))
#        print("roof open ok, {}".format(', '.join(reason_open)))
    else:
        open_ok = False
        reasons = "{}".format(', '.join(reason_close))
#        print("roof open not ok: {}".format(', '.join(reason_close)))

#    print(reasons)

    utcnow = datetime.datetime.utcnow()
#    last_open_ok = retrieve_previous_open_ok()
    event = ''
    roof_change = False
    if last_open_ok is False:
        if open_ok is True:
            roof_change = True
            event = "opening"
        else:
            event = "stays closed"
    else:
        if open_ok is False:
            roof_change = True
            event = "closing"
        else:
            event = "stays open"

    print("Roof {}, {}".format(event, reasons))

    if roof_change is True:
        sendToMattermost(url, event + ", " + reasons)
        store_event(utcnow, event, reasons)

#    last_open_ok = retrieve_previous_open_ok()
#    if last_open_ok != open_ok:
#        sendToMattermost(url, open_ok_str + reasons)

    store_roof_status(utcnow, sensors_id, open_ok, reasons)
    print("")

if __name__ == "__main__":
    main()
