#!/usr/bin/env python3

import sys
import MySQLdb
import datetime
import json
import requests
from pathlib import Path

database = MySQLdb.connect(
    host="lxc-rrd",
    port=3306,
    user='sens',
    passwd='sens',
    db="observatory1")
db_cursor = database.cursor()

def check_db(minutes):
    sql = """
      SELECT sensors_id
             ,create_time
        FROM sensors
    ORDER BY create_time DESC
       LIMIT 1;
    """
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    try:
        row_id  = db_result_tuple[0]
        db_date = db_result_tuple[1]
    except:
        raise
    if db_date < datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes) :
        print("DB last timestamp {db_date} is More than {minutes} minutes ago -> close".format(db_date=db_date, minutes=minutes))
        print("Stop_Imaging (do not wait). Park (wait), Close_Roof")
        quit(1)
    else:
        print("DB last timestamp {db_date} is Less than {minutes} minutes ago -> open".format(db_date=db_date, minutes=minutes))
        return(row_id)

def check_sqm(sensors_id, sqm_min):
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

def check_ups(sensors_id):
    sql = """
      SELECT ups1_status
        FROM sensors
       WHERE sensors_id = {sensors_id}
       LIMIT 1;
    """.format(sensors_id=sensors_id)
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    #print(db_result_tuple)
    try:
        ups_status  = db_result_tuple[0]
    except:
        raise
    if ups_status == 1:
        print("UPS is powered -> open")
        return(True)
    else:
        print("UPS is on battery -> close")
        return(False)

def check_infrared(sensors_id, sensor, minimum_delta_t):
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

def retrieve_previous_open_ok():
    sql = """
      SELECT create_time,open_ok
        FROM roof
    ORDER BY roof_id DESC
       LIMIT 1;
    """
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    last_open_ok = db_result_tuple[1]
    return(last_open_ok)

def sendToMattermost(url, message):
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
    sqm_now_ok       = check_sqm(sensors_id, sqm_min=17.5)
    rain_now_ok      = check_rain(sensors_id, drops_min=1)
    ups_now_ok       = check_ups(sensors_id)
    infrared1_now_ok = check_infrared(sensors_id, sensor='BAA1', minimum_delta_t=20)
    infrared2_now_ok = check_infrared(sensors_id, sensor='BCC1', minimum_delta_t=20)

    sqm_past_ok       = check_sqm_past(sqm_min=17.5, seconds=3600, outlier_count_max=5)
    rain_past_ok      = check_rain_past(drops_min=1, seconds=3600, outlier_count_max=2)
    infrared1_past_ok = check_infrared_past(sensor='BAA1', minimum_delta_t=20, seconds=3600, outlier_count_max=5)
    infrared2_past_ok = check_infrared_past(sensor='BCC1', minimum_delta_t=20, seconds=3600, outlier_count_max=5)

    reason_open = []
    reason_close = []
    if sensors_id:
        reason_open.append("DB works")
    else:
        reason_close.append("DB not updated")

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
            reason_close.append("Still too much rain")
    else:
        if rain_past_ok:
            reason_close.append("Started raining")
        else:
            reason_close.append("Still raining")

    if ups_now_ok:
        reason_open.append("UPS works")
    else:
        reason_close.append("UPS on battery")
    
    if infrared1_now_ok or infrared2_now_ok:
        if infrared1_past_ok or infrared2_past_ok:
            reason_open.append("Clear sky long enough")
        else:
            reason_close.append("Not clear long enough")
    else:
        if infrared1_past_ok or infrared2_past_ok:
            reason_close.append("Too cloudy")
        else:
            reason_close.append("Still too cloudy")

    #print(reason_open)
    #print(reason_close)

    if sensors_id and sqm_now_ok and sqm_past_ok and rain_now_ok and rain_past_ok and ups_now_ok and (infrared1_now_ok or infrared2_now_ok) and (infrared1_past_ok or infrared2_past_ok):
        open_ok = True
        open_ok_str = "OK to open: "
        reasons = "gogogo"
        #reasons = "{}".format(', '.join(reason_open))
#        print("roof open ok, {}".format(', '.join(reason_open)))
    else:
        open_ok = False
        open_ok_str = "Must close: "
        reasons = "{}".format(', '.join(reason_close))
#        print("roof open not ok: {}".format(', '.join(reason_close)))

    print(reasons)
    last_open_ok = retrieve_previous_open_ok()
    if bool(last_open_ok) != open_ok:
        sendToMattermost(url, open_ok_str + reasons)

    utcnow = datetime.datetime.utcnow()
    sql_keys = []
    sql_values = []
    sql_keys.append("create_time")
    sql_values.append('"' + str(utcnow) + '"')
    sql_keys.append("open_ok")
    sql_values.append(str(open_ok))
    sql_keys.append("reasons")
    sql_values.append('"' + reasons + '"')
    sql = """
INSERT INTO observatory1.roof ({keys})
     VALUES ({values});
    """.format(keys = ','.join(sql_keys),
               values = ','.join(sql_values))
    print("{}".format(sql.lstrip().rstrip()))
    try:
        db_cursor.execute(sql)
        database.commit()
        print(db_cursor.rowcount, "record inserted.")
    except:
        database.rollback()
        raise

if __name__ == "__main__":
    main()

