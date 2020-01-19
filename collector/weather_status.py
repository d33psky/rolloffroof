#!/usr/bin/env python3

import configparser
import json
from pathlib import Path
import pymysql as MySQLdb

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


def db_connect(config):
    db = MySQLdb.connect(
        host=config['mysqlDB']['host'],
        port=int(config['mysqlDB']['port']),
        user=config['mysqlDB']['user'],
        passwd=config['mysqlDB']['pass'],
        db=config['mysqlDB']['db'])
    db_cursor = db.cursor()
    return db_cursor


def get_weather_status(db_cursor):
    sql = """
    SELECT open_ok, reasons, create_time
      FROM roof
     WHERE create_time > DATE_SUB(UTC_TIMESTAMP(), INTERVAL 120 second)
  ORDER BY create_time DESC
     LIMIT 1;
    """
    db_cursor.execute(sql)
    db_result_tuple = db_cursor.fetchone()
    try:
        open_ok = True if db_result_tuple[0] == 1 else False
        reasons = db_result_tuple[1]
        create_time = db_result_tuple[2]
    except:
        # TODO
        raise
    return (open_ok, reasons, create_time)


def main():
    config = configparser.ConfigParser()
    config.read(str(Path.home()) + '/' + CONFIG_FILE_IN_HOME)

    db_cursor = db_connect(config)

    (open_ok, reasons, create_time) = get_weather_status(db_cursor)

    create_time_formatted = create_time.isoformat()
    json_string = json.dumps({
        'timestamp_utc': create_time_formatted,
        'roof_status': {
            'open_ok': open_ok,
            'reasons': reasons,
        }
    },
                             indent=4)
    print(json_string)


if __name__ == "__main__":
    main()
