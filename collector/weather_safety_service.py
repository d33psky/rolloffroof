#!/usr/bin/env python3

import configparser
import json
from pathlib import Path
import pymysql.cursors
from flask import Flask

CONFIG_FILE_IN_HOME = ".my.cnf.python"
# example contents :
"""
[mysqlDB]
host = database.domain
port = 3306
user = mysql
pass = mysql
db   = weather
"""

# example output:
"""
{
   "timestamp_utc": "2019-03-16T15:35:05",
   "roof_status": {
       "open_ok": false,
       "reasons": "Still not dark enough, Still too cloudy"
   }
}
"""

FLASK_APP = Flask(__name__)

config = configparser.ConfigParser()
config.read(str(Path.home()) + '/' + CONFIG_FILE_IN_HOME)



def get_weather_status():
    connection = pymysql.connect(
        host=config['mysqlDB']['host'],
        port=int(config['mysqlDB']['port']),
        user=config['mysqlDB']['user'],
        passwd=config['mysqlDB']['pass'],
        db=config['mysqlDB']['db'])
#, cursorclass=pymysql.cursors.DictCursor)
    #    return (None, None, None)
    sql = """
    SELECT open_ok, reasons, create_time
      FROM roof
     WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL 120 second)
  ORDER BY create_time DESC
     LIMIT 1;
    """
    try:
        with connection.cursor() as db_cursor:
            db_cursor.execute(sql)
            db_result_tuple = db_cursor.fetchone()
            if db_result_tuple is not None:
                #        open_ok = True if db_result_tuple[0] == 1 else False
                open_ok = db_result_tuple[0]
                reasons = db_result_tuple[1]
                create_time = db_result_tuple[2]
            else:
                open_ok = None
                reasons = None
                create_time = None
    finally:
        connection.close()
#    open_ok = 1 # TEST TEST TEST
    return (open_ok, reasons, create_time)


@FLASK_APP.route('/weather/safety', methods=['GET'])
def weather_safety():
    """ api call """
    (open_ok, reasons, create_time) = get_weather_status()

    if open_ok is not None:
        create_time_formatted = create_time.isoformat()
        json_string = json.dumps({
            'timestamp_utc': create_time_formatted,
            'roof_status': {
                'open_ok': open_ok,
                'reasons': reasons,
            }
        },
            indent=4)
    else:
        json_string = json.dumps({
            'error': 'Empty DB result',
        })
    return(json_string)


def main():
    FLASK_APP.run(debug=False, host='0.0.0.0')


if __name__ == "__main__":
    main()