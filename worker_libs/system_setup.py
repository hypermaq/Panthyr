#! /usr/bin/python
# coding: utf-8
"""Basic description.

Ver 1.0 19jul2017

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""

"""Imports"""
import logging
from dbc import connection
from gpio05 import toggle_pwr  # to switch power to various devices
import datetime
from time import sleep
import flir_ptu_d48e as pt  # control of the pan/tilt head
import suncalc  # calculation of the solar position
import subprocess  # used to set system time
import gnss  # provides GNSS/GPS functions
from check import check_reply

"""Variables"""
__all__ = ["set_system_time", "set_clock_gnss", "set_station_params", "aim_sun", "position_head", "set_clock_ntp"]

"""Functions."""

log = logging.getLogger("__main__.{}".format(__name__))

    
def set_system_time(datetime):
    """Sets the Linux clock/date.

    Argument should be a datetime object.
    Returns True is success, False if failed.
    """
    try:
        subprocess.check_output(["sudo", "date", "-s", str(datetime)])  # check_output supresses stdout, but exceptions should be handled (subprocess.CalledProcessError)
        # All arguments are passed as individual string items in a list
        return True
    except subprocess.CalledProcessError as e:
        db = connection()
        log.error("Error setting system time: {}".format(e))
        db.add_log("Error while setting the system time to: {}. Error: {}".format(datetime, e), "worker.set_system_time", "warning")
        return False

def set_clock_ntp(db):
    from ntplib import NTPClient
    ntpc = NTPClient()
    try: 
        r = ntpc.request('europe.pool.ntp.org')
        datetime_obj = datetime.datetime.fromtimestamp(r.tx_time)
    except:
        return False
    if set_system_time(datetime_obj):
        db.add_log("System clock from NTP: {}".format(datetime_obj), "worker.set_clock_ntp", "info")
        return True
    else: 
        return False


def set_clock_gnss():
    toggle_pwr("output5", "on")  # switch GNSS power on
    try:
        if gnss.setup_port():
            gpsdata = gnss.get_nmea(45)  # 45s to give it some extra time to get a fix
    except Exception, e:
        log.error("Error while initializing port for GNSS: {}".format(e))
        db.add_log("Error initializing port for GNSS: {}".format(e), "worker.set_clock_gnss", "warning")

    toggle_pwr("output5", "off")  # switch GNSS power off

    if type(gpsdata) == dict:
        if set_system_time(gpsdata["utc"]):
            db.add_log("System clock from GNSS: {}".format(gpsdata["utc"]), "worker.set_clock_gnss", "info")
            return True
        else: 
            db.add_log("Could not set system clock from GNSS (cannot set date)", "worker.set_clock_gnss", "warning")
            return False
    else:
        db.add_log("Could not set system clock from GNSS (no dict)", "worker.set_clock_gnss", "warning")
        return False


def set_station_params(db):
    """ Sets system time, and stores gnss data to db.

    Gets time, location, magnetic variation and fix data from gnss.
    Sets the system time.
    Stores "gnss_lat", "gnss_lon", "gnss_acquired", "gnss_qual", "gnss_mag_var" to database
    """
    set_error = False
    to_log = 'Data from GNSS: '
    
    try:
        toggle_pwr("output5", "on")  # switch GNSS power on
        try:
            if gnss.setup_port():
                gpsdata = gnss.get_nmea()
            else:
                raise Exception("Is port already open?")
        except Exception, e:
            log.error("Error while initializing port for GNSS: {}".format(e))
            raise Exception("Error initializing port for GNSS: {}".format(e))
        finally:
            toggle_pwr("output5", "off")  # switch GNSS power off
        
        if not gpsdata:
            raise Exception("Setting station params received no GNSS data")

        if not type(gpsdata) == dict:
            message = "Setting station params received wrong GNSS data: {} (type = {})".format(gpsdata, type(gpsdata))
            log.error(message) 
            raise Exception(message)

        gpsdata["lat"] = "{:011.8f}".format(gpsdata["lat"])  # remove unneeded precision
        gpsdata["lon"] = "{:012.8f}".format(gpsdata["lon"])  # remove unneeded precision
        
        # dict to translate from name in the db to gpsdata dict index:
        settings = [("gnss_lat", "lat"), ("gnss_lon", "lon"), ("gnss_acquired", "utc"), ("gnss_qual", "qual"), ("gnss_mag_var", "mag_var")]
        for s,v in settings:
            reply = db.set_setting(s, gpsdata[v])[0]  # save to database
            to_log += ('{}: {},'.format(s, gpsdata[v]))
            if not reply:   # not sure what happens here, as dbc.set_setting() returns (True,None), but reply[0] does not seem to work?
                set_error = True
            
        
        if set_system_time(gpsdata["utc"]):
            db.add_log("System clock set from GNSS: {}".format(gpsdata["utc"]), "worker.set_station_params", "info")
        else: 
            set_error = True
            raise Exception("Error setting system clock from GNSS at boot {}".format(gpsdata["utc"]))
        


    except Exception, e:
        toggle_pwr("output5", "off")  # switch GNSS power off
        log.warning("{}".format(e), exc_info = True)
        log.warning('Last GNSS info (if any): {}'.format(to_log))
        set_error = True

    if set_error: return False
    else: 
        log.info(to_log)
        return True

def aim_sun(db, elevation_offset = 0):
    """Aims head to the sun, for alignment and check."""

    # first get necessary info from db.
    gnss_lat = float(db.get_setting("gnss_lat")[1])
    gnss_lon = float(db.get_setting("gnss_lon")[1])
    head_true_north_offset = int(db.get_setting("head_true_north_offset")[1])  # head heading when at 0'

    # prepare head
    toggle_pwr("output2", "on")  # switch head power on
    sleep(8)  # give head time to start up (needed!)
    head = pt.pthead()
    reply = head.setup_socket()  # setup the serial comms port
    if not check_reply(reply, "worker.aim_sun (head.setup_port)"):  # comms is not correctly initialized
        toggle_pwr("output2", "off")  # switch head power off
        return False
 
    reply = head.initialize()
    if not check_reply(reply, "worker.aim_head (head.initialize)"):  # problems during initialization
        toggle_pwr("output2", "off")  # switch head power off
        return False

    sun_elevation = float(suncalc.get_sun_elevation(gnss_lat, gnss_lon, datetime.datetime.now()))
    sun_heading = float(suncalc.get_sun_heading(gnss_lat, gnss_lon, datetime.datetime.now()))

    head_heading_calculated = (sun_heading - head_true_north_offset) % 360
    sun_elevation_calculated = sun_elevation + elevation_offset

    reply = head.move_position(head_heading_calculated,sun_elevation_calculated)
    if not check_reply(reply, "worker.aim_head (head.move_position)"):
        toggle_pwr("output2", "off")  # switch head power off
        return False

    return True

def position_head(heading, elevation):
    """Move the head to heading and elevation"""
     # prepare head
    toggle_pwr("output2", "on")  # switch head power on
    sleep(8)  # give head time to start up (needed!)
    head = pt.pthead()
    reply = head.setup_socket()  # setup the serial comms port
    if not check_reply(reply, "worker.position_head (head.setup_port)"):  # comms is not correctly initialized
        toggle_pwr("output2", "off")  # switch head power off
        return False
 
    reply = head.initialize()
    if not check_reply(reply, "worker.position_head (head.initialize)"):  # problems during initialization
        toggle_pwr("output2", "off")  # switch head power off
        return False

    reply = head.move_position(heading, elevation)
    if not check_reply(reply, "worker.position_head (head.move_position)"):
        toggle_pwr("output2", "off")  # switch head power off
        return False
    
    return True