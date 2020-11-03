# coding: utf-8
#! /usr/bin/python
"""Basic description.

Ver 1.0 19jul2017

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""
import logging
import datetime
from time import sleep

from gpio05 import toggle_pwr  # to switch power to various devices
import flir_ptu_d48e as pt  # control of the pan/tilt head
import suncalc  # calculation of the solar position
from ipcam import ipcam
import trippy  # communication with TriOS Ramses sensors
from check import check_reply
from adc import batt_voltage

"""Variables"""
__all__ = ["measure"]
log = logging.getLogger("__main__.{}".format(__name__))

"""Functions."""
def check_in_keepout(target, zone_low, zone_high):
    """ Check if target is in between (not including) two headings.

    Zone can include North if heading zone_low < zone_high (ie 340 - 40)
    If zone_low = zone_high, all headings are considered out of the zone.
    """
    target = target % 360
    if zone_low < zone_high and (zone_low < target < zone_high): return True
    if zone_low > zone_high and not (zone_high <= target <= zone_low): return True
    return False


def measure(db = None, taskid = 0):
    """Makes a measurement (if necessary) and stores data in db.

    1. gets settings and protocol from db
    2. checks if current time is within measurement window and if current sun zenith is below maximum
    3. initializes head
    4. loops over protocol, scan by scan
        a. If needed, wait x seconds
        b. gets calc.heading and calc.elevation
        c. calculates head elevation, depending on protocol offsets and sensor angles
        d. points p/t
        e. makes measurement
        f. stores data to db
    5. parks head

    Protocol return fields: [0] instrument, [1] zenith, [2] azimuth offset, [3] repeat, [4] wait

    If something fails before point 3, nothing gets written to the measurement table.
    Returns True if measurement is done correctly (or with errors, but it shouldn't be redone), False if the measurement task should remain open.
    """
    meas_setup = dict()  # will store all measurement results
    meas_setup["setup_error"] = []  # create a list  inside the dictionary that will contain (possible) error messages
    meas_setup["valid"] = "n"  # will get set to n if any serious errors occur, or y if everything goes ok
    
    #----------------------------------------------------------------------------
    # 1. gets settings and protocol from db
    #----------------------------------------------------------------------------
    prot = db.get_protocol()[1]  # Returns a dict with numbers (starting at one) as keys, and tuples (instrument, zenith, azimuth offset, repeat, wait) as values. One key = one scan.

    if len(prot) == 0:  # if no scans are defined in the protocol, we don't need to do anything and task can be set to "done"'
        log.warning('Empty protocol, no measurements defined')
        return True

    station_id = db.get_setting("station_id")[1]
    set_max_sun_zenith = float(db.get_setting("max_sun_zenith")[1])  # minimum sun elevation/max zenith to make measurements
    set_meas_start_hour = int(db.get_setting("measurements_start_hour")[1])  # hours between which measurements are to be made
    set_meas_stop_hour = int(db.get_setting("measurements_stop_hour")[1])
    set_keepout_heading_low = int(db.get_setting("keepout_heading_low")[1])  # defines the lower heading of the keepout zone
    set_keepout_heading_high = int(db.get_setting("keepout_heading_high")[1])  # defines the higher heading of the keepout zone
    meas_setup["gnss_lat"] = float(db.get_setting("gnss_lat")[1])  # {:011.7f}
    meas_setup["gnss_lon"] = float(db.get_setting("gnss_lon")[1])
    meas_setup["gnss_qual"] = int(db.get_setting("gnss_qual")[1])
    meas_setup["gnss_acquired"] = db.get_setting("gnss_acquired")[1]
    meas_setup["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # the cycle_id will be the same for all "scans" in this measurement cycle
    meas_setup["cycle_id"] = "{}_{:06d}_{}".format(station_id, taskid, datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))

    head_true_north_offset = int(db.get_setting("head_true_north_offset")[1])  # head heading when at 0
    radiance_angle_offset = float(db.get_setting("radiance_angle_offset")[1])  # radiance sensor angle to base of head
    irradiance_angle_offset = float(db.get_setting("irradiance_angle_offset")[1])  # irradiance sensor angle to base of head

    # try to get adc_channel and adc_factor from settings. They might not be in there, if so set to None
    try:
        adc_channel = int(db.get_setting('adc_channel')[1])
        adc_factor = int(db.get_setting('adc_factor')[1])
    except:
        adc_channel = None
        adc_factor = None
    

    # get battery voltage (or set 'config error' if not possible)
    if adc_channel:
        batt_volt = batt_voltage(input_number = adc_channel, factor = adc_factor)
        if batt_volt.check_config():
            meas_setup['batt_voltage'] = batt_volt.get_voltage()
        else:
            meas_setup['batt_voltage'] = 'config incorrect'
    else:
        meas_setup['batt_voltage'] = 'not configured'


    #----------------------------------------------------------------------------
    # 2. check if current time is within measurement window and if current sun zenith is below maximum
    #----------------------------------------------------------------------------
    if not set_meas_start_hour <= datetime.datetime.now().hour < set_meas_stop_hour:
        # current time is outside the range which is defined in settings. Exit and set task to done.
        return True

    sun_elevation = float(suncalc.get_sun_elevation(meas_setup["gnss_lat"], meas_setup["gnss_lon"], datetime.datetime.now()))
    if not sun_elevation >= ( 90 - set_max_sun_zenith): 
        return True

    #----------------------------------------------------------------------------
    # 3. initialize head
    #----------------------------------------------------------------------------
    try:
        toggle_pwr("output3", "on")  # apply power to top box, IP cam needs some time to boot
        toggle_pwr("output6", "on")  # apply power to Intercoax converter to IP cam can set up link

        toggle_pwr("output2", "on")  # switch head power on
        sleep(8)  # give the head time to start up (required!), ethernet takes a bit more time to come up compared to serial port
        head = pt.pthead()  # create instance
        reply = head.setup_socket()  # setup the serial comms port
        if not check_reply(reply, "worker.measure (head.setup_socket) "):  # comms is not correctly initialized
            toggle_pwr("output2", "off")  # switch head power off
            meas_setup["setup_error"].append(reply)
            db.add_meas(meas_setup)
            return False
    
        reply = head.initialize()
        if not check_reply(reply, "worker.measure (head.initialize) "):  # problems during initialization
            toggle_pwr("output2", "off")  # switch head power off
            meas_setup["setup_error"].append(reply)
            db.add_meas(meas_setup)
            return False

        toggle_pwr("output4", "on")  # apply power to multiplexer board

        #----------------------------------------------------------------------------
        # 4. loops over protocol, scan by scan
        #----------------------------------------------------------------------------
        for i in range (1, len(prot) + 1):  # iterate over the list of scans, and perform them one by one
            log.debug("scan/instr/zen/azi/rpt/wait {0}/{1[0]}/{1[1]}/{1[2]}/{1[3]}/{1[4]} ".format(i, prot[i]))
            #----------------------------------------------------------------------------
            # 4a. If needed, wait x seconds.
            #----------------------------------------------------------------------------
            if not str(prot[i][0]).lower() in ("c", "l", "e"):  # incorrect instrument is given
                continue  # proceed to next scan in protocol

            if int(prot[i][4]) > 0:  # position 4 is the "wait" setting for this scan
                sleep(int(prot[i][4]))
            
            #----------------------------------------------------------------------------
            # 4b. get sun_heading and sun_elevation
            #----------------------------------------------------------------------------
            meas_scan = dict()
            meas_scan.update(meas_setup)
            head_params = head.show_parameters()  # request parameters such as voltage and temperatures
            sun_elevation = float(suncalc.get_sun_elevation(meas_setup["gnss_lat"], meas_setup["gnss_lon"], datetime.datetime.now()))
            sun_heading = float(suncalc.get_sun_heading(meas_setup["gnss_lat"], meas_setup["gnss_lon"], datetime.datetime.now()))

            meas_scan_add = [("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), 
            ("prot_sensor", prot[i][0]), ("prot_zenith", prot[i][1]), ("prot_azimuth", prot[i][2]), 
            ("scan_error", []), ("cycle_scan", "{:02d}".format(i)),
            ("head_temp_hpt", "{0[temp_head]:4.1f}/{0[temp_pan]:4.1f}/{0[temp_tilt]:4.1f}".format(head_params)),
            ("head_voltage", "{:4.1f}".format(head_params["voltage"])),
            ("sun_elevation", "{:5.2f}".format(sun_elevation)), ("sun_heading", "{:6.2f}".format(sun_heading))]
            # List of parameters that are already known and can be added to meas_scan

            for s,v in meas_scan_add: 
                meas_scan[s] = v 

            if prot[i][0].lower() == "c":
                #----------------------------------------------------------------------------
                # 5b. calculate head heading and elevation, depending on protocol offsets and sensor angles
                # 5c. point p/t
                # 5d. make measurement
                #----------------------------------------------------------------------------

                # first convert elevation for PTU-D48 (-90 to +30, reference = horizontal)                
                if 0 <= int(prot[i][1]) <= 180:
                    meas_elevation = int(prot[i][1]) - 90  # convert to PTU-D48 reference angle
                    tilt_converted = meas_elevation - radiance_angle_offset  # include sensor offset
                else:
                    meas_scan["scan_error"].append("invalid elevation in protocol")
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue

                target = (sun_heading + prot[i][2]) % 360
                if check_in_keepout(target, set_keepout_heading_low, set_keepout_heading_high):
                    meas_scan["scan_error"].append("Target heading {:6.2f} is inside of defined keepout zone " \
                    "({} to {}) with offset {} and current sun heading {:6.2f}.".format(((sun_heading + prot[i][2]) % 360), 
                                                                                            set_keepout_heading_low, 
                                                                                            set_keepout_heading_high, 
                                                                                            prot[i][2], 
                                                                                            sun_heading))
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue

                meas_scan["scan_heading"] = round(target, 2)
                head_heading_calculated = (target - head_true_north_offset) % 360

                reply = head.move_position(head_heading_calculated, tilt_converted)
                if not check_reply(reply, "worker.measure (head.move_position)"):
                    meas_scan["scan_error"].append(reply)  # add reply to the list of errors                
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue  # next scan in protocol

                cam = ipcam()
                reply = cam.grab_frame()
                del cam

                if not check_reply(reply, "worker.measure (ipcam.grabframe)"):
                    meas_scan["scan_error"].append("IP cam: {}".format(reply))
                else:
                    meas_scan["valid"] = "y"
                db.add_meas(meas_scan)
                continue  # go to next scan

            elif prot[i][0].lower() in "(l, e)":  # (ir)radiance measurement
                #----------------------------------------------------------------------------
                # 4c. calculates head elevation, depending on protocol offset and sensor angle
                #----------------------------------------------------------------------------
                if prot[i][0].lower() == "e": 
                    port = "/dev/ttyO1"  # irradiance sensor on ttyO1
                    checkbyte = False  # needed to solve issue with current version of trippy
                else: 
                    port = "/dev/ttyO2"  # radiance sensor on ttyO2
                    checkbyte = False  # needed to solve issue with current version of trippy

                # meas_scan["head_heading_calculated"] is calculated from the sun heading, the offset from prot[i]2 and head offset
                meas_scan["scan_heading"] = round((sun_heading + prot[i][2]) % 360, 2)
                if check_in_keepout(meas_scan["scan_heading"], set_keepout_heading_low, set_keepout_heading_high):
                    meas_scan["scan_error"].append("Target heading {:6.2f} is inside of defined keepout zone " \
                    "({} to {}) with offset {} and current sun heading {:6.2f}.".format(((sun_heading + prot[i][2]) % 360), set_keepout_heading_low, set_keepout_heading_high, prot[i][2], sun_heading))
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue
                head_heading_calculated = (sun_heading + prot[i][2] - head_true_north_offset) % 360             

                # convert elevation for PTU-D48 (-90 to +30, reference = horizontal)                
                if 0 <= int(prot[i][1]) <= 180:
                    meas_elevation = int(prot[i][1]) - 90  # convert to PTU-D48 reference angle
                    if prot[i][0].lower() == "e": tilt_converted = meas_elevation - irradiance_angle_offset  # include sensor offset
                    else: tilt_converted = meas_elevation - radiance_angle_offset  # include sensor offset
                else:
                    meas_scan["scan_error"].append("invalid elevation in protocol")
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue
                    
                #----------------------------------------------------------------------------
                # 4d. point p/t
                #----------------------------------------------------------------------------            
                reply = head.move_position(head_heading_calculated, tilt_converted)
                if not check_reply(reply, "worker.measure (head.move_position)"):
                    meas_scan["scan_error"].append(reply)
                    db.add_meas(meas_scan)  # store the "results" for reference and troubleshooting
                    continue 
            
                #----------------------------------------------------------------------------    
                # 4e. makes measurement
                #----------------------------------------------------------------------------    
                ret = trippy.trios_single(port, int_time = 0, repeat = prot[i][3], require_checkbyte = checkbyte, verbosity = 0, sleep = 0.5, max_time = 18)
                if ret[0]:  # error during initialization of port or instrument
                    meas_scan["scan_error"].append(ret[1])  # store error info
                    db.add_meas(meas_scan)
                    continue

                #----------------------------------------------------------------------------    
                # 4f. stores measurement data from all repetitions to db
                #----------------------------------------------------------------------------    
                for rep in range(len(ret[1])):
                    meas_repeat = dict()
                    meas_repeat.update(meas_scan)
                    meas_repeat["rep_unix"] = ret[1][rep][2]
                    meas_repeat["scan_rep"] = rep + 1
                    meas_repeat["rep_error"] = ret[1][rep][0]
                    meas_repeat["rep_serial"] = ret[1][rep][1]
                    meas_repeat["data"] = ret[1][rep][3]
                    if ret[1][rep][0] == "": meas_repeat["valid"] = "y"
                    db.add_meas(meas_repeat)

        toggle_pwr("output3", "off")  # cut power to Top box
        toggle_pwr("output4", "off")  # cut power to Multiplexer
        toggle_pwr("output6", "off")  # cut power to Intercoax


        #----------------------------------------------------------------------------
        # 5. park head and cut power to cam
        #----------------------------------------------------------------------------
        reply = head.park()
        check_reply(reply, "worker.measure (head.park)")  # if there's an issue during parking, put it in the log
        toggle_pwr("output2", "off")  # switch head power off

        return True  # finished measurement cycle

    finally:
        toggle_pwr("output2", "off")  # switch head power off
        toggle_pwr("output3", "off")  # cut power to Top box
        toggle_pwr("output4", "off")  # cut power to Multiplexer
        toggle_pwr("output6", "off")  # cut power to Intercoax