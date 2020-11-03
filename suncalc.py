#! /usr/bin/python
# coding=utf-8  # needed for degrees sign (ASCII 0176)
"""Calculate solar position (heading, inclination) for given geolocation and time (in UTC).

Ver 1 (06jul2017)
"""

from Pysolar import solar
import datetime
import logging


log = logging.getLogger("__main__.{}".format(__name__))

def check_position_format(x):
    """Check if the format of longitude/latitude is correct for use with Pysolar."""
    if isinstance(x, (int, long, float)):  # Check if position is an integer/long/float
        return True
    else:
        return False


def check_time_format(x):
    """Check if the format of timestamp is correct for use with Pysolar."""
    if isinstance(x, datetime.datetime):
        return True
    else:
        return False


def get_sun_heading(x, y, z):
    """Calculate the sun heading using pysolar.

    Arguments: x= latitude (format xxx.yyyyyy, type int), y= longitude (format xxx.yyyyyy, type int), z= time (format datetime.datetime)
    Pysolar returns azimuth South referenced, with positive values towards East. We need compass heading, 0-360 degrees.
    Returns compass heading as int (0-360).
    """

    if check_position_format(x) and check_position_format(y) and check_time_format(z):
        sun_hdg_s_ref = solar.GetAzimuth(x, y, z)  # Get the azimuth, South ref, pos towards East
        if -360 <= sun_hdg_s_ref <= -180:  # Convert azimuth to compass heading
            return (-sun_hdg_s_ref - 180)
        elif -180 < sun_hdg_s_ref <= 180:
            return 180 - sun_hdg_s_ref
        elif 180 < sun_hdg_s_ref <= 360:
            return 540 - sun_hdg_s_ref
    else:
        msg = "Incorrect parameters given to get_sun_heading function"
        log.error(msg)
        return "ERROR " + msg


def get_sun_elevation(x, y, z):
    """Calculate the sun elevation using pysolar.

    Arguments: x= latitude (format xxx.yyyyyy), y= longitude (format xxx.yyyyyy), z= time (format datetime.datetime)
    Pysolar returns positive elevation for position above the horizon
    """
    if check_position_format(x) and check_position_format(y) and check_time_format(z):
        return solar.GetAltitude(x, y, z)
    else:
        msg = "Incorrect parameters given to get_sun_heading function"
        log.error(msg)
        return "ERROR " + msg


"""Main function."""
if __name__ == "__main__":
    location_latitude = -14.94478
    location_longitude = 6.67969
    sun_heading = get_sun_heading(location_latitude, location_longitude, datetime.datetime.now())
    sun_elevation = get_sun_elevation(location_latitude, location_longitude, datetime.datetime.now())
    print("Heading: {}°".format(sun_heading))
    print("Elevation: {}°".format(sun_elevation))