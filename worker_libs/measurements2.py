#! /usr/bin/python
# coding: utf-8
"""Basic description.

Ver 1.0 19jul2017

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""


"""Imports."""
import logging
from adc import batt_voltage
from datetime import datetime
import suncalc  # calculation of the solar position
from gpio05 import toggle_pwr  # to switch power to various devices
from time import sleep
import flir_ptu_d48e as pt  # control of the pan/tilt head
from ipcam import ipcam
import trippy  # communication with TriOS Ramses sensors

"""Define constants."""
INTERCOAX = 'output6'
TOP_BOX = 'output3'
PAN_TILT = 'output2'
MULTIPLEXER = 'output4'
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
# trios settings
TRIOS_REQUIRE_CHECKBYTE = False
TRIOS_INT_TIME = 0
TRIOS_SLEEP_TIME = 0.5
TRIOS_MAX_TIME = 18



"""Define variables."""
__all__ = ["measurement"]

"""Functions."""

class measurement(object):
    """Class for the measurements."""

    def __init__(self, db):
        """Init."""
        self.db = db
        logging.basicConfig()
        self.log = logging.getLogger('__main__.{}'.format(__name__))
        self.cycleID = 'init'
        self.sun_position = dict()
        self.add_to_db = False # gets set to True as soon as enough info is gathered to store in db (if failed measurement)
        self.init_done = False

    def _get_protocol(self):
        """Gets protocol and checks if it's empty.
        returns True if protocol has been found, False if empty or error.
        """
        try:
            self.protocol = self.db.get_protocol()[1]

        except Exception as e:
            msg = 'Issue while querying db for protocol: {}'.format(e)
            self.log.error(msg, exc_info = True)
            raise Exception(msg)
        return True

    def _set_up_vars(self):
        """ creates dicts for setup parameters, scan information and repeat information.
        Defaults 'valid' to 'n'
        """
        self.meas_setup_params = dict()
        self.meas_scan = {'valid':'n'}
        self.meas_repeat = dict()
    
    def _get_meas_variables(self):
        try:
            self.set_keepout_heading = [0,0]
            self.set_meas_window = [0,24]
            self.station_id = self.db.get_setting('station_id')[1]
            self.set_max_sun_zenith = float(self.db.get_setting('max_sun_zenith')[1])  # minimum sun elevation/max zenith to make measurements
            self.set_meas_window[0] = int(self.db.get_setting('measurements_start_hour')[1])  # hours between which measurements are to be made
            self.set_meas_window[1] = int(self.db.get_setting('measurements_stop_hour')[1])
            self.set_keepout_heading[0] = int(self.db.get_setting('keepout_heading_low')[1])  # defines the lower heading of the keepout zone
            self.set_keepout_heading[1] = int(self.db.get_setting('keepout_heading_high')[1])  # defines the higher heading of the keepout zone
            self.head_true_north_offset = int(self.db.get_setting('head_true_north_offset')[1])  # head heading when at 0
            self.radiance_angle_offset = float(self.db.get_setting('radiance_angle_offset')[1])  # radiance sensor angle to base of head
            self.irradiance_angle_offset = float(self.db.get_setting('irradiance_angle_offset')[1])  # irradiance sensor angle to base of head
            self.meas_setup_params = dict()
            self._get_batt_voltage() # added to self.meas_setup_params
            self.meas_setup_params['gnss_lat'] = float(self.db.get_setting('gnss_lat')[1])  # {:011.7f}
            self.meas_setup_params['gnss_lon'] = float(self.db.get_setting('gnss_lon')[1])
            self.meas_setup_params['gnss_qual'] = int(self.db.get_setting('gnss_qual')[1])
            self.meas_setup_params['gnss_acquired'] = self.db.get_setting('gnss_acquired')[1]
            self.meas_setup_params['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.meas_setup_params['setup_error'] = list()
            # the cycle_id will be the same for all 'scans' in this measurement cycle
            self.meas_setup_params['cycle_id'] = '{}_{:06d}_{}'.format(self.station_id, self.taskid, datetime.now().strftime('%Y%m%d_%H%M%S'))
            

        except Exception as e:
            msg = 'Issue while getting measurement variables from db: {}'.format(e)
            self.log.error(msg,exc_info = True)
            raise Exception(msg)

        return True

    def _get_batt_voltage(self):
        # try to get adc_channel and adc_factor from settings. They might not be in there, if so set to None
        try:
            adc_channel = int(self.db.get_setting('adc_channel')[1])
            adc_factor = int(self.db.get_setting('adc_factor')[1])
        except:
            adc_channel = None
            adc_factor = None

        # get battery voltage (or set 'config error' if config not found)
        try:
            if adc_channel and adc_factor:
                batt_volt = batt_voltage(input_number = adc_channel, factor = adc_factor)
                if batt_volt.check_config():
                    self.meas_setup_params['batt_voltage'] = batt_volt.get_voltage()
                else:
                    self.meas_setup_params['batt_voltage'] = 'config incorrect (ch: {}, factor: {})'.format(adc_channel, adc_factor)
            else:
                # configuration is incorrect. No problem, just store msg
                self.meas_setup_params['batt_voltage'] = 'not configured'
        except Exception as e:
            msg = 'Issue while getting battery voltage (ch: {}, factor: {}): {}'.format(adc_channel, adc_factor, e)
            self.log.warning(msg,exc_info = True)
        finally: 
            # no matter if there's issues during batt measurement, continue
            return True

    def _check_in_timewindow(self):
        """Checks if we're currently inside the defined time window for measurements.
        Returns:
        *** True if:
        - inside of time window
        *** False if:
        - outside of time window
        """
        if self.set_meas_window[0] <= datetime.now().hour < self.set_meas_window[1]:
            # current time is outside the range which is defined in settings. Exit and set task to done.
            return True
        else: 
            return False

    def _check_sun_elevation(self):
        """Checks if sun is currently high enough
        Returns:
        *** True if:
        - sun is high enough
        *** False if:
        - sun is too low
        """
        self._update_sun_position()
        if self.sun_position['elevation'] >= ( 90 - self.set_max_sun_zenith): 
            return True
        else: 
            return False

    def _update_sun_position(self):
        self.sun_position['heading'] = float(suncalc.get_sun_heading(self.meas_setup_params['gnss_lat'], self.meas_setup_params['gnss_lon'], datetime.now()))
        self.sun_position['elevation'] = float(suncalc.get_sun_elevation(self.meas_setup_params['gnss_lat'], self.meas_setup_params['gnss_lon'], datetime.now()))

    def _check_any_outside_keepout(self):
        """
        checks if any measurements are outside the keepout zone (and thus should be done)
        returns:
        *** True if:
        - there are measurements that need to be done
        *** False if:
        - no measurements need to be done
        """
        azimuth_offsets = list()
        self._update_sun_position()

        for i in self.protocol:
            if not i['azimuth'] in azimuth_offsets:
                azimuth_offsets.append(i['azimuth'])

        if any(self._check_out_of_keepout(i) for i in azimuth_offsets):
            return True
        else:
            return False


    def _check_out_of_keepout(self, offset):
        """ Check if target is in between (not including) two headings.

        Zone can include North if heading zone_low > zone_high (ie 340 - 40)
        If zone_low == zone_high, all headings are considered out of the zone.
        """
        target = (self.sun_position['heading'] + offset) % 360
        zone_low = self.set_keepout_heading[0]
        zone_high = self.set_keepout_heading[1]
        if zone_low == zone_high:
            return True

        # check if the target is currently inside the keepout zone
        if zone_low < zone_high and (zone_low < target < zone_high): 
            return False
        if zone_low > zone_high and not (zone_high <= target <= zone_low): 
            return False
        
        return True

    def _power_on(self, outputs):
        if self._power(outputs, 'on'):
            return True
        else:
            return False

    def _power_off(self, outputs):
        if self._power(outputs, 'off'):
            return True
        else:
            return False

    def _power(self, outputs, state):
        if type(outputs) == str:
            outputs = (outputs,)
            
        try:
            for i in outputs:
                ret = toggle_pwr(i, state)
                if not ret == 'OK':
                    raise Exception(ret)
            
        except Exception as e:
            msg = 'Issue while setting {} to state {}: {}'.format(i, state, e)
            self.log.warning(msg,exc_info = True)
            self.meas_setup_params['setup_error'].append(msg)
            raise(e)
        return True

    def _startup_head(self):
        """ sets up head an initializes.
        returns:
        *** True if:
        - all went well
        *** False if:
        - head could not completely be initialized
        """
        self.head = pt.pthead()  # create instance
        self.head_needs_parking = True
        if self.head.setup_socket() and (self.head.initialize() == 'OK'):
            return True
        else:
            msg = 'Issue during startup_head()'
            self.meas_setup_params['setup_error'].append(msg)
            return False

    def _check_and_prep_scan(self, scan):
        """check if correct instrument has been defined, updates sun position and sets up self.meas_scan dict
        returns:
        *** True if:
        - all good
        *** False
        - invalid instrument
        -
        """
        if not scan['instrument'] in ('c','l','e'):
            # incorrect instrument is given
            msg = 'Instrument {} in scan no {} is not a valid instrument choice, continuing with next'.format(scan['instrument'], scan['id'])
            self.log.warning(msg)
            self.meas_scan['scan_error'].append(msg)
            return False

        # set up meas_scan dict
        self.meas_scan = {'valid':'n'}  # create new dict with only 'valid = n'
        self.meas_scan['timestamp'] = datetime.now().strftime(TIME_FORMAT)
        self.meas_scan['prot_sensor'] = scan['instrument']
        self.meas_scan['prot_zenith'] = scan['zenith']
        self.meas_scan['prot_azimuth'] = scan['azimuth']
        self.meas_scan['scan_error'] = []
        self.meas_scan['cycle_scan'] = '{:02d}'.format(scan['id'])
        # get vitals from head
        head_params = self.head.show_parameters()  # request parameters such as voltage and temperatures
        self.meas_scan['head_temp_hpt'] = '{0[temp_head]:4.1f}/{0[temp_pan]:4.1f}/{0[temp_tilt]:4.1f}'.format(head_params)
        self.meas_scan['head_voltage'] = '{:4.1f}'.format(head_params['voltage'])
        # update sun position right before measurement
        self._update_sun_position()
        self.meas_scan['sun_elevation'] = self.sun_position['elevation']
        self.meas_scan['sun_heading'] = self.sun_position['heading']
        self.meas_scan["scan_heading"] = round((self.meas_scan['heading'] + scan['azimuth']) % 360, 2)

        if not self._check_out_of_keepout(scan['azimuth']):
            msg = 'Target heading {[scan_heading]:6.2f} is inside of defined keepout zone ' \
                    '({0[0]} to {0[1]}) with offset {2:03d} and current sun heading {[sun_heading]:6.2f}.'.format(self.set_keepout_heading, scan['azimuth'], **self.meas_scan)
            self.log.debug(msg)
            self.meas_scan['scan_error'].append(msg)
            return False

        if not self._check_zenith_valid(scan):
            msg = 'Target zenith {[scan_zenith]:03d} is not possible with instrument {[instrument]} in current offset configuration'.format(**self.meas_scan)
            self.meas_scan['scan_error'].append(msg)
            self.log.debug(msg)
            return False
        
        return True

    def _check_zenith_valid(self,scan):
        """ Checks if the current scan is within the tilt range of the head (-90 to +30degs from level)
        If valid, it sets self.meas_scan['head_elevation'] to the correct angle to point the instrument to the right zenith angle
        Returns:
        *** True if:
        - requested combination of instrument and zenith is within head reach (also set self.meas_scan['head_elevation'])
        *** False if:
        - out of reach of the head
        """
        if scan['instrument'] == 'c':
            instrument_offset = 0
        if scan['instrument'] == 'l':
            instrument_offset = self.radiance_angle_offset
        if scan['instrument'] == 'e':
            instrument_offset = self.irradiance_angle_offset
        
        # first compensate for instrument offset, reference is nadir (so 180degs is straight up)
        target_zenith = scan['zenith'] - instrument_offset
        # convert to head axis (0 degs is towards horizon, negative below horizon)
        self.meas_scan['head_elevation'] = target_zenith - 90
        # check if this is possible, if so set self.meas_scan['head_elevation'] and return True, else return False
        if -90 <= self.meas_scan['head_elevation'] <= 30:
            return True
        else:
            return False




    def _add_meas_to_db(self):
        """ Combines available information in one dict and stores that in the measurement table
        To avoid overwriting existing dicts (ie. the meas_setup_params), each time start with a blank dict.
        Then update with existing information (which may be empty dicts).
        """

        combined_meas_dict = dict()
        combined_meas_dict.update(self.meas_setup_params)
        combined_meas_dict.update(self.meas_scan)
        combined_meas_dict.update(self.meas_repeat)

        self.db.add_meas(combined_meas_dict)  # store the "results" for reference and troubleshooting

    def _take_picture(self, scan):
        """Prepares IP Cam and takes still frame
        
        Arguments:
            scan {dict}
        Returns:
            True if:
                - Succesfully taken picture
            False if:
                - Issue has occured            
        """
        cam = ipcam()
        ret = cam.grab_frame()
        if ret == 'OK':
            return True
        else:
            self.meas_scan['scan_error'].append(ret)
            return False

    def _measure_ramses(self, scan):
        """Takes measurements as described in scan.
        Takes into account the number of repetitions required.
        adds errors during setup to self.meas_scan['scan_error']
        errors belonging to specific scan are added to self.meas_repeat['rep_error']
        
        Arguments:
            scan {dict}
        Returns:
            True if:
                - Succesfully taken measurement
            False if:
                - Issue has occured
        """
        # clear the self.meas_repeat dict so we don't have data from a previous scan if this fails before starting the first repetition
        self.meas_repeat = dict()

        # set up correct port
        if scan['instrument'].lower() == 'e':
            instrument_port = '/dev/ttyO1'  # irradiance sensor on ttyO1
        elif scan['instrument'].lower() == 'l':
            instrument_port = '/dev/ttyO2'  # radiance sensor on ttyO2
        
        # perform the measurement
        ret = trippy.trios_single(  port = instrument_port, 
                                    int_time = TRIOS_INT_TIME, 
                                    repeat = scan['repeat'], 
                                    require_checkbyte = TRIOS_REQUIRE_CHECKBYTE, 
                                    verbosity = 0, 
                                    sleep = TRIOS_SLEEP_TIME, 
                                    max_time = TRIOS_MAX_TIME)

        # check if init of the instrument went ok
        if ret[0]:  # error during initialization of port or instrument
                    self.meas_scan["scan_error"].append(ret[1])  # store error info
                    return False

        # store measurement data from all repetitions to db
        for rep in range(len(ret[1])):
                    self.meas_scan['valid'] = 'n'
                    self.meas_repeat['rep_unix'] = ret[1][rep][2]
                    self.meas_repeat['scan_rep'] = rep + 1
                    self.meas_repeat['rep_error'] = ret[1][rep][0]
                    self.meas_repeat['rep_serial'] = ret[1][rep][1]
                    self.meas_repeat['data'] = ret[1][rep][3]
                    if ret[1][rep][0] == '': 
                        self.meas_scan['valid'] = 'y'
                    self._add_meas_to_db()
                    # The next measurement could be a camera still. 
                    # If we don't empty the self.meas_repeat dict, it will be saved as part of the camera meas data.
                    self.meas_repeat = dict()  


    def measure(self, taskid = 666):
        """The high level/main function.
        Handles the whole measurement cycle.
        Returns:
        *** True if:
        - succesful
        - empty protocol
        - outside of time window
        - sun too low
        - all measurements inside keepout zone
        *** False if:
        - any other condition where measurement should be tried again
        """

        try:
            self.taskid = taskid
            import pdb
            pdb.set_trace()

            # Check protocol
            self._get_protocol()
            if len(self.protocol)==0:
                self.log.warning('Protocol empty')
                return True

            self._set_up_vars()

            self._get_meas_variables()

            if not (self._check_in_timewindow() and self._check_sun_elevation()):
                # we're outside the measurement hours or sun too low, so no measurement
                return True

            # check to see if there are measurements outside of the keepout zone
            if not self._check_any_outside_keepout():
                # all measurements are inside the keepout zone
                self.log.info('all measurements currently in keepout zone')
                return True
            
            # from here on it's worth to mention this attempt in the db
            self.add_to_db = True

            # time to start up the head, intercoax and ipcam
            if not self._power_on((INTERCOAX, PAN_TILT, TOP_BOX)):
                # issue during switching power, retry later
                return False
            
            # give head time to start up
            # sleep(8)

            # if not self.startup_head():
            #     # finally part of the try/except/finally loop will switch off all outputs
            #     return False

            self.init_done = True

        except:
            return False

        finally:
            if not self.init_done:
                if self.head_needs_parking:
                    self.head.park()
                self._power_off((INTERCOAX, PAN_TILT, MULTIPLEXER, TOP_BOX))
                if self.add_to_db:
                    # something went wrong during the init, but after enough info has been gathered to store in db
                    self._add_meas_to_db()
            
        """ 
        All has now been set up to make measurements.
        """

        try:
            if not self.init_done:
                return False

            for scan in self.protocol:  # iterate over the list of scans, and perform them one by one

                self.log.debug("scan {id:02d}/instr {instrument}/zen {zenith:03d}/azi {azimuth:03d}/rpt {repeat:02d}/wait {wait:02d}".format(**scan))
                if not self._check_and_prep_scan(scan):
                    # scan has invalid instr, is inside of keepout zone or target zenith not reacheable in current config
                    # log anyway to document full measurement cycle
                    self._add_meas_to_db()
                    # proceed to next scan in protocol (first step will be to create empty self.meas_scan dict)
                    continue

                if int(scan['wait']) > 0:  # wait defined in the protocol
                    sleep(int(scan['wait']))

                # position the head
                ret = self.head.move_position(self.meas_scan['scan_heading'], self.meas_scan['head_elevation'])
                if not ret == 'OK':
                    self.meas_scan['scan_error'].append(ret)
                    self._add_meas_to_db()
                    continue

                if scan['instrument'].lower() == 'c':
                    if self._take_picture(scan) and len(self.meas_scan['scan_error']) == 0:
                        self.meas_scan['valid'] = 'y'
                    self._add_meas_to_db()

                if scan['instrument'].lower() in ('l', 'e'):
                    # radiance or irradiance measurement
                    # measurements are stored after each repeated meas is deconstructed, unless something went wrong
                    # in that case make sure the measurement is set to not valid and logged for reference
                    if not self._measure_ramses(scan):
                        # returned from function before last measurement was unsuccesful
                        self.meas_scan['valid'] = 'n'
                        self._add_meas_to_db()

                continue

            return True

        except Exception as e:
            del(e)  # to get rid of warning
            return False
        
        finally:
            self.head.park()
            self._power_off((INTERCOAX, PAN_TILT, MULTIPLEXER, TOP_BOX))