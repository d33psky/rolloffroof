#!/usr/bin/env python3

import sys
import MySQLdb
import datetime
import subprocess

# update skytemperature-BAA.rrd -t BAA_sensor:BAA_sky N:8.06:4.06
#
# tempandhum-observatory.rrd temperature  -> observatory_temperature1
# tempandhum-observatory.rrd humidity     -> observatory_humidity1   
# tempandhum-observatory.rrd dewpoint     -> observatory_dewpoint1   
# tempandhum-outside.rrd temperature      -> outside_temperature1    
# tempandhum-outside.rrd humidity         -> outside_humidity1       
# tempandhum-outside.rrd dewpoint         -> outside_dewpoint1       
# skytemperature-BAA.rrd BAA_sky          -> BAA1_temperature_sky    
# skytemperature-BAA.rrd BAA_sensor       -> BAA1_temperature_sensor 
# skytemperature-BCC.rrd BCC_sky          -> BCC1_temperature_sky    
# skytemperature-BCC.rrd BCC_sensor       -> BCC1_temperature_sensor 
# luminosity.rrd luminosity               -> sqm1_luminosity
# sqm.rrd frequency                       -> sqm1_frequency
# sqm.rrd sqm                             -> sqm1_sqm                
# rainsensor.rrd pulses                   -> rainsensor1_pulses      
# rainsensor.rrd drops                    -> rainsensor1_drops       
# tempandhum-picambucket.rrd temperature  -> allskycam1_temperature  
# tempandhum-picambucket.rrd humidity     -> allskycam1_humidity     
# tempandhum-picambucket.rrd dewpoint     -> allskycam1_dewpoint     
# allskycamstars.rrd         stars        -> allskycam1_stars        
# ups.rrd status                          -> ups1_status             
# ups.rrd linev                           -> ups1_linev              
# ups.rrd loadpct                         -> ups1_loadpct            
# ups.rrd bcharge                         -> ups1_bcharge            
# ups.rrd timeleft                        -> ups1_timeleft           
# ups.rrd itemp                           -> ups1_itemp              
# ups.rrd battv                           -> ups1_battv              
# ups.rrd linefreq                        -> ups1_linefreq           

def printHelpAndExit(exitValue):
    print("feed this thing rrdtool update lines")
    sys.exit(exitValue)

if len(sys.argv) != 6:
    printHelpAndExit(1)

(me,update,db,t,keys_str,values_str)=sys.argv
#print("db {},t {},keys {},values {}".format(db,t,keys_str,values_str))
keys   = keys_str.split(':')
values = values_str.split(':')

utcnow = datetime.datetime.utcnow()

database = MySQLdb.connect(
    host="localhost",
    port=3306,
    user='sens',
    passwd='sens',
    db="observatory1")
db_cursor = database.cursor()

db_mapper = {
    'tempandhum-observatory.rrd': 'observatory',
    'tempandhum-outside.rrd'    : 'outside',
    'skytemperature-BAA.rrd'    : 'BAA1_temperature',
    'skytemperature-BCC.rrd'    : 'BCC1_temperature',
    'luminosity.rrd'            : 'sqm1',
    'sqm.rrd'                   : 'sqm1',
    'rainsensor.rrd'            : 'rainsensor1',
    'tempandhum-picambucket.rrd': 'allskycam1',
    'allskycamstars.rrd'        : 'allskycam1',
    'ups.rrd'                   : 'ups1'
}
field_name_1 = db_mapper.get(db, "Unknown DB")
#print("db {}".format(field_name_1))

key_mapper = {
    'temperature' : 'temperature1',
    'humidity'    : 'humidity1',
    'dewpoint'    : 'dewpoint1',
    'BAA_sky'     : 'sky',
    'BAA_sensor'  : 'sensor',
    'BCC_sky'     : 'sky',
    'BCC_sensor'  : 'sensor',
    'luminosity'  : 'luminosity',
    'frequency'   : 'frequency',
    'sqm'         : 'sqm',
    'pulses'      : 'pulses',
    'drops'       : 'drops',
    'stars'       : 'stars',
    'status'      : 'status',
    'linev'       : 'linev',
    'loadpct'     : 'loadpct',
    'bcharge'     : 'bcharge',
    'timeleft'    : 'timeleft',
    'itemp'       : 'itemp',
    'battv'       : 'battv',
    'linefreq'    : 'linefreq'
}

sql_keys = []
sql_values = []
sql_assignments = []
i = 0
while i < len(keys):
    field_name_2 = key_mapper.get(keys[i], "Unknown KEY")
    sql_keys.append("{}_{}".format(field_name_1, field_name_2))
    sql_values.append("{}".format(values[i+1]))
    #print("{}_{} = {}".format(field_name_1, keys[i], values[i+1]))
    sql_assignments.append("{}_{}={}".format(field_name_1, field_name_2, values[i+1]))
    i += 1

sql = """
  SELECT sensors_id
         ,create_time
    FROM sensors
ORDER BY create_time DESC
   LIMIT 1;
"""
db_cursor.execute(sql)
db_result_tuple = db_cursor.fetchone()
#print(db_result_tuple)
try:
    row_id  = db_result_tuple[0]
    db_date = db_result_tuple[1]
    must_insert = False
except:
    db_date = utcnow
    must_insert = True

if must_insert or db_date < datetime.datetime.utcnow() - datetime.timedelta(minutes=1) :
    print("{} is More than a minute ago -> INSERT".format(db_date))

    print("Hack: but first call ./query_sky_and_obsy_conditions.py")
    subprocess.call("./query_sky_and_obsy_conditions.py")
    print("Hack: done with query_sky_and_obsy_conditions.py, continue")

    sql_keys.append("create_time")
    sql_values.append('"' + str(utcnow) + '"')
    sql = """
INSERT INTO observatory1.sensors ({keys})
     VALUES ({values});
    """.format(keys = ','.join(sql_keys),
               values = ','.join(sql_values))
else:
    #print("{} is Less than a minute ago -> UPDATE".format(db_date))
    sql = """
UPDATE observatory1.sensors
   SET {assignment_list}
 WHERE sensors_id = {sensors_id}
 LIMIT 1;
    """.format(assignment_list = ','.join(sql_assignments),
               sensors_id = row_id)

#print("{}".format(sql.lstrip().rstrip()))
try:
    db_cursor.execute(sql)
    database.commit()
#    print(db_cursor.rowcount, "record inserted.")
except:
    database.rollback()
    raise

