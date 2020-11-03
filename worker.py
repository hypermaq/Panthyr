#! /usr/bin/python
# coding: utf-8
"""Main worker.

14feb2018

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

Checks the "queue" table in the db. If tasks are in queue, priority is taken into account and tasks are executed.
"""
from worker_libs import *
import sys  # provides access to arguments
import logging
from dbc import connection
from time import sleep
import gpio05
from subprocess import call  # temp solution to blink led


"""Define constants."""

"""Define variables."""

"""Functions."""

def setup_logging(db):
    import logging.handlers
    # formatting
    fmt="%(levelname)-5s |%(asctime)s |%(module)-9.9s:%(lineno)-03s |%(funcName)-9.9s |%(message)s"  # defines format for log messages
    datefmt='%d/%m/%Y %H:%M:%S'  # defines format for timestamp
    LOG_FILE = '/home/hypermaq/data/panthyr_log.log'
    max_log_size = 5000000
    log_file_backups = 10

    log = logging.getLogger(__name__)  # creates root logger with name of script/module
    log.setLevel(logging.DEBUG)
    log.logThreads = 0  # tell log that it shouldn't gather thread data
    log.logProcesses = 0  # tell log that it shouldn't gather process data
    
    # create, configure and add streamhandler(s)
    h1 = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes = max_log_size, backupCount = log_file_backups)  # handler to stdout for less important messages
    h1.setLevel(logging.DEBUG)
    h1.setFormatter(logging.Formatter(fmt, datefmt))  
    log.addHandler(h1)  # add handler to the logger

    if db.get_setting('email_enabled')[1]:
        level = {'critical': logging.CRITICAL, 
                'error': logging.ERROR, 
                'warning': logging.WARNING, 
                'info': logging.INFO, 
                'debug': logging.DEBUG}
        email_conf = {'recipient':'', 'server_port': '', 'user': '', 'password':'', 'min_level':''}  # lookup dict
        
        for i in email_conf:
            email_conf[i] = db.get_setting("email_" + i)[1]  # get all email configuration from the settings table
        station_id = db.get_setting('station_id')[1]

        h2 = buffered_SMTP_Handler(host = email_conf["server_port"],
                                fromaddress= email_conf["user"],
                                toaddress = email_conf["recipient"],
                                password = email_conf["password"],
                                id = station_id)  # handler for messages that should be emailed
                                # # secure = ())
        h2.setLevel(level[email_conf['min_level']])
        h2.setFormatter(logging.Formatter(fmt, datefmt))
        log.addHandler(h2)

    h3 = db_Handler(db)
    h3.setLevel(logging.DEBUG)
    log.addHandler(h3)

    return log

def blink_led():
    with open('/sys/class/leds/beaglebone:green:usr0/brightness', "w") as target:
        # blink one user led briefly to show user that script is running
        call(["echo", "1"], stdout = target)
        sleep(0.2)
        call(["echo", "0"], stdout = target)

"""Main loop"""

def init():
    db.populate_credentials()  # do this first so that logging has the right credentials
    log = setup_logging(db)  # creates log object
    if len(sys.argv) == 2 and sys.argv[1] == "cron":
        # at least one parameter is provided (parameter 0 is the scriptname itself)
        if db.get_setting("manual")[1] == 1: exit()
        else: log.info("worker started by cron.")
        # If not started by cron, log the start and continue.
    log.info('******************')
    log.info('worker initialized')
    return log

if __name__ == "__main__":
    """First, set up logging and check if this script is started by cron.
    If so, check the "manual" setting. If set (1), we want to use the worker manually, so cron shouldn't start it in the background.
    If not, set up gpio pins
    """
    with connection() as db:
    
        log = init()

        while __name__ == "__main__":
            """This is the main loop, which first checks how many tasks are queued.
            If none are, sleep for ten seconds and start loop again.
            If there are, first handle these tasks.
            """
            try:
                while db.get_number_of_tasks()[1] > 0:
                    task = db.get_next_task()[1]  # returns a tuple (id, priority, action, options, fails), or none
                    ready = db.get_setting('system_set_up')[1]
                    success = False

                    if type(task) == tuple:  # a task was returned
                        log.debug("executing task {0[0]} (priority/fails: {0[1]}/{0[4]}): {0[2]}.".format(task))
                        # Check what kind of task was in the queue and execute accordingly
                        
                        if task[2] == "measure":
                            if not ready:
                                log.warning("Task {} (measure) queued but system is not ready".format(task[0]))
                            else:    
                                if measure(db, task[0]):  # supply the task ID so it can be used as part of the cycle_id
                                    
                                    success = True

                        if task[2] == "vacuum_db":
                            log.info("Task {} (vacuum_db) will now flush and vacuum the database.".format(task[0]))
                            try:
                                if db.vacuum_db()[0]:
                                    success = True
                                    log.info("Task {} (vacuum_db) successfully vacuumed the database.".format(task[0]))
                            except Exception as e:
                                msg = 'Exception: error while vacuuming db: {}'.format(e)
                                log.error(msg, exc_info=1)
                                db.commit()


                        elif task[2] == "set_station_params":  
                            """ran after boot, uses GNSS to: 
                            - set system time 
                            - store lat, lon, magnetic variation and GNSS qualtity to the settings table in the db.
                            """
                            failed = True

                            if set_station_params(db):
                                failed = False
                                system_set_up = True
                            elif task[4] < 2:  # if this is not the third time (fails < 2)
                                failed = True
                            else:  # this is the last attempt at at least setting the system clock
                                log.error('Could not set system clock and location from GNSS, trying to set sytem time from NTP')
                                db.set_setting('gnss_acquired', 0)
                                db.set_setting('gnss_qual', 0)
                                log.critical('Could not get GNSS fix')

                                if not set_clock_ntp(db):
                                    # could not set system clock from NTP either
                                    log.critical('Could not set the system clock from NTP, halting measurements')
                                    try:
                                        log.handlers[1].flush()  # we're not sure if email is enabled
                                    except:
                                        pass
                                else:
                                    failed = False
                                    log.info('system time set from NTP (no GNSS)')

                            if not failed:
                                db.set_setting('system_set_up', 1)
                                ready = True
                                success = True
                            else:  # couldn't set system time, either from GNSS or NTP
                                db.set_setting('system_set_up', 0)

                        elif task[2] == 'backup_ftp':
                            """export new data to new (temporary) sqlite database and upload it to ftp
                            - check last succesfully uploaded measurement and log id
                            - create new database with newer data
                            - upload to ftp and verify upload
                            - delete created database
                            """
                            bf = backup_ftp(db)

                            if bf.do_backup()[0]:
                                success = True

                        elif task[2] == "aim_sun"  and ready:  
                            """points the p/t to the sun, without accounting for instrument offsets (for setup/alignment)
                            # task[3] (option field) should contain an int (-90 to 90) that that gets substracted from the sun elevation. 
                            # Max head tilt is +30 degrees, so for level checking, one might opt to use -90 and 
                            # take the vertical part of the bracket as reference towards the sun zenith."""
                            try:
                                try:
                                    if not -90 <= int(task[3]) <= 90:  # check if offset is valid
                                        raise Exception
                                    else:
                                        elevation_offset = int(task[3])
                                except: 
                                    log.warning("invalid elevation_offset for task {} 'aim_sun': {}".format(task[0], task[3]))
                                    raise Exception

                                if aim_sun(elevation_offset = elevation_offset, db = db):
                                    success = True
                                else: raise Exception
                            except:
                                 pass

                        elif task[2] == "position_head" and ready:
                            # moves the pan/tilt to the position in the options field
                            # format: heading(0 <= heading < 360), elevation(-90 <= elevation <= 30)
                            # if option field is not correct or empty, 0,0 is taken

                            try:
                                heading, elevation = task[3].split(",")
                                if not 0 <= int(heading) < 360:
                                    heading = 0
                                if not -90 <= int(elevation) <=30:
                                    elevation = 0
                            except:
                                heading = 0
                                elevation = 0

                            if position_head(int(heading), int(elevation)):
                                success = True
                        
                        if not ready: sleep(5)  # wait a bit, to give user time to add set_station_params
                        if success:
                            db.set_task_handled(task[0])
                            log.debug("task {} handled succesfully.".format(task[0]))
                        else:
                            db.set_task_handled(task[0], failed = True, fails = int(task[4]))
                            log.debug("task {} handled with errors.".format(task[0]))
                        sleep(1)

                blink_led()

                sleep(9)

            except Exception as e:
                print('Exception: error while running through worker.py: {}'.format(e))
                log.error('Exception: error while running through worker.py: {}'.format(e), exc_info=1)
                db.commit()

            except KeyboardInterrupt:
                print('\b\b////\nKeyboard interrupt received, now safely exiting worker.py\n////')
                # \b\b backs the cursor over the ^C printed to stdout when ctrl + C is pressed, 
                # overwrites it with characters, then prints a newline
                log.info('Shutting down worker script after manual CTRL+C')
                logging.shutdown()
                db.commit()
                exit()