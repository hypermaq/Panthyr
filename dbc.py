#! /usr/bin/python
# coding: utf-8
"""Database connection.

Creates the db and tables, handles tasks in the queue, stores settings, logs and measurement data.
08feb2018

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?
"""

import sqlite3  # Because ... Well...
import logging
import os
from datetime import datetime
from subprocess import call  # to do the actual export

__metaclass__ = type  # new-style classes

"""Define constants."""
database_location = "/home/hypermaq/data/hypermaq.db"
valid_tables = ("protocol", "settings", "measurements", "queue", "logs")
log = logging.getLogger("__main__.{}".format(__name__))


"""Define variables."""

"""Functions."""

class connection(sqlite3.Connection):
    def __init__(self, database = database_location, **kwargs):
        super(connection, self).__init__(database = database, **kwargs)
        self.__c = self.cursor()  # cursor object
    
    def __commit_db(self):
        self.commit()

    def __close_db(self):
        self.close()

    def populate_credentials(self, cf_location = '/home/hypermaq/data/credentials', credentials = ('email_user', 'email_password', 'email_server_port', 'ftp_server', 'ftp_user', 'ftp_password')):
        """ Populates FTP/Email/... credentials (as defined by [credentials]) in the database from the file specified by [cf_location].
        Each line of the file should be in the format "credential_name=value\n"
        Credentials in the file that are not in [credentials] are ignored.
        If any of the [credentials] are not in the [cf_location], they are left blank
        If file does not exist, a template file [cf_location] is created with the credentials defined in [credentials] but empty values.
        
        Variable abbreviations: c = credential, v = value
        """
        from credentials import get_credentials
        try:
            parsed_credentials = get_credentials(cf_location = cf_location, credentials = credentials, all = True)
        
            assert type(parsed_credentials) == dict, 'no valid credentials retrieved from file'

            for c in credentials:
                self.set_setting(c, parsed_credentials[c])

        except AssertionError:
            log.error('No valid credentials retrieved from file')
        
        except Exception as e:
            log.error(e)

    def get_setting(self, setting):
        '''Returns the value of a setting in the 'settings' database.'''
        try:
            self.__c.execute("SELECT value FROM settings WHERE setting = ?", (setting,))
            reply = self.__c.fetchone()[0]

            try:  # check if the value is an integer, if so return it as int
                return(True, int(reply))
            except:
                return(True, reply)

        except TypeError as e:
            err_str = 'Error while getting setting for {}, is setting in db? {}'.format(setting, e)
            log.error(err_str)
            return(False, 'ERROR (GET_SETTING): ' + err_str)

        except Exception as e:
            err_str = 'Error while getting setting for {}: {}'.format(setting, e)
            log.error(err_str)
            return(False, 'ERROR (GET_SETTING): ' + err_str)

    def set_setting(self, setting, value):
        '''Adds or changes settings in the the 'settings' table.'''
        try:
            self.__c.execute("insert or ignore into settings(setting) VALUES(?)", (setting,))  # creates a new setting (row) if it doesn't exist, else does nothing
            self.__c.execute("update settings set value = ? where setting = ?", (value, setting))
            self.__commit_db()

        except Exception as e:
            err_str = 'Error while setting setting for {}: {}'.format(setting, e)
            log.error(err_str)
            return(False, 'ERROR (SET_SETTING): ' + err_str)
        return(True, None)

    def add_to_queue(self, action, priority = "2", options = ""):
        """Adds measurement entry into the measurements table.

        Takes argument action to define the type of task. Optional arguments are options to specify additional parameters and priority (default 2)
        Valid "actions": "measure", "set_clock_gnss", "zero".
        """
        try:
            self.execute("insert into queue(priority, action, options) values (? ,? ,?)", (priority, action, options))
            self.__commit_db()
        except Exception as e:
            err_str = 'Error while adding task ({},{},{}) to queue table: {}'.format(action, priority, options, e)
            log.error(err_str)
            return (False, 'ERROR (ADD_TO_QUEUE): ' + err_str)
        return (True, None )

    def get_next_task(self, **kwargs):
        """Checks the db for tasks.

        Queries the "queue" table in the database_location db for tasks where done = "0".
        Db is first queried for tasks with priority "1", then priority "2".
        Sorting is done by id (thus order of creation).
        Returns the next job (if any) as a tuple (id, priority, action, options).

        Priority col values: 1 = high priority (manually queued, ...), 2 = normal priority
        Done col values: 1 = done, 0 = to be done
        """
        self.__c.execute("select id, priority, action, options, fails from queue where done == 0 and priority == 1 and fails < 3 order by id limit 1")
        reply = self.__c.fetchone()
        if type(reply) == tuple:
            return (True, reply)
        else:  # no items with priority 1 are waiting, so check for tasks with priority 2
            self.__c.execute("select id, priority, action, options, fails from queue where done == 0 and priority == 2 and fails < 3 order by id limit 1")
            return (True, self.__c.fetchone())

    def get_all_tasks(self):
        '''Queries the db for all tasks.

        Queries the 'queue' table in the database_location db for tasks where done = '0'.
        Sorting is done first done by priority, then by id (thus order of creation).
        Returns jobs as a tuple of tuples (id, priority, action, options).
        '''
        self.__c.execute('select priority, id, action, options from queue where done == 0 order by priority asc, id asc')
        reply = self.__c.fetchall()

        return (True, reply)

    def get_number_of_tasks(self, done=0):
        '''Checks the db for tasks and returns how many are to be done.

        Queries the 'queue' table in the database_location db for the number of tasks where done = '0', regardless of priority.
        Returns this number to the calling function.
        Passing 1 as parameter returns the number of tasks that are already marked as done.
        '''
        try:
            self.__c.execute('select count() from queue where done == ? and fails < 3', (str(done)))
            reply = self.__c.fetchone()  # returns a tuple, we only need the first item
            return (True, int(reply[0]))  # returns the first item of the returned tuple

        except Exception as e:
            err_str = 'Error while getting the number of tasks: {}'.format(e)
            log.error(err_str)
            return(False, 'ERROR (GET_NUMBER_OF_TASKS): ' + err_str)

    def get_protocol(self):
        
        '''Returns a list of of dicts, one for each measurement
        dict keys: id, instrument, zenith, azimuth, repeat, wait
        '''
        to_return = list()
        i = 1  # counter for number of scans in the protocol

        try:
            self.__c.execute('SELECT instrument, zenith, azimuth, repeat, wait from protocol ORDER BY number')

            response = self.__c.fetchall()
                # Returns a list (1 item for each row) of tuples (each element representing one column)

            for s in response:
                to_return.append(({'id':i,'instrument':s[0].lower(), 'zenith':s[1], 'azimuth':s[2], 'repeat':s[3], 'wait':s[4]}))
                i += 1

            return (True, to_return)

        except Exception as e:
            err_str = 'Error while getting protocol: {}'.format(e)
            log.error(err_str)
            return(False, 'ERROR (GET_PROTOCOL): ' + err_str)

    def add_log(self, logtext, source = "none", level="info"):
        """Adds logtext into the logs table.

        Arguments: source = calling module, logtext = str.
        """
        try:
            self.execute("insert into logs(level, source, log) values (?, ?, ?)", (level, source, logtext))
            self.__commit_db()
        except Exception as e:
            err_str = 'Error while adding log to db: {}'.format(e)
            log.error(err_str)
            return(False, 'ERROR (ADD_LOG): ' + err_str)
        return (True, None)

    def add_meas(self, meas_dict):
        '''Stores the measurement results in the database.
        meas_dict is expected to be a dictionary containing any combination of the following keys:
            'timestamp', 
            'valid', 
            'setup_error', 
            'cycle_id', 
            'gnss_acquired', 
            'gnss_qual', 
            'gnss_lat', 
            'gnss_lon', 
            'batt_voltage',
            'head_voltage',
            'head_temp_hpt', 
            'cycle_scan', 
            'prot_sensor',
            'prot_zenith', 
            'prot_azimuth', 
            'sun_heading', 
            'sun_elevation',
            'scan_heading'
            'scan_error', 
            'scan_rep', 
            'rep_error', 
            'rep_unix', 
            'rep_serial'
            'data' (containing a list of 255 values)
        '''
        if not type(meas_dict) == dict:
            err_str = 'Error while adding measurement: no dictionary provided'
            log.warning(err_str)
            return(False, 'ERROR (ADD_MEAS): ' + err_str)

        logged_items = ['timestamp', 'valid', 'setup_error', 'cycle_id', 'gnss_acquired', 
                    'gnss_qual', 'gnss_lat', 'gnss_lon', 'batt_voltage', 'head_voltage',
                    'head_temp_hpt', 'cycle_scan', 'prot_sensor',
                    'prot_zenith', 'prot_azimuth', 'sun_heading', 'sun_elevation', 'scan_heading', 
                    'scan_error', 'scan_rep', 'rep_error', 'rep_unix', 'rep_serial']
        d = dict()

        for i in logged_items:
            if i in meas_dict:  # check if it is in the provided dict
                if i in ('scan_error', 'setup_error'):  # these are lists to accomodate multiple errors
                    d[i] = ' | '.join(meas_dict[i])  # so join them into a string
                else: 
                    d[i] = meas_dict[i]  # store the value from the provided dict
            else:
                d[i] = ''

        try:  # add measurement data
            for i in range(1, len(meas_dict['data']) + 1):
                d['val_{:03d}'.format(i)] = meas_dict['data'][i-1]
        except KeyError:  # there's no 'data' key in the dict
            pass

        # create parts of sqLite command:
        columns = ''
        values = []
        placeholders = ''
        for i in d:
            columns += '{}, '.format(i)
            values.append(d[i])
            placeholders += '?, '

        try:
            self.execute('insert into measurements({}) values ({})'.format(columns[:-2], placeholders[:-2]), values)
            self.__commit_db()

        except Exception as e:
            err_str = 'Error while adding measurement to db: {}'.format(e)
            log.error(err_str)
            return(False, 'ERROR (ADD_MEAS): ' + err_str)

        return (True, None)

    def set_task_handled(self, id=-1, failed = False, fails = 0):
        '''Marks a task in the queue table as done (or adds to the fail counter).

        Takes the task id as argument. 
        Optional argument failed = True adds one to fails and updates task fails in db
        '''
        if type(id) != int or id < 0:  # check if a valid id is passed
            log.warning('No valid queue ID provided ({})'.format(id))
            return(False, 'ERROR (SET_TASK_HANDLED): No valid queue ID provided ({})'.format(id))

        try:
            # try to set the task to done
            if failed: 
                self.__c.execute("update queue set fails = ? where id == ?", (fails + 1, id))
            else:
                self.__c.execute("update queue set done = '1' where id == ?", (id,))
            self.__commit_db()
            return (True, None)

        except Exception as e:
            err_str = 'Error while setting task with ID({}) to handled. Error: {}'.format(id, e)
            log.error(err_str)
            return (False, 'ERROR (SET_TASK_HANDLED): ' + err_str)

    def get_last_id(self, table):
        '''Returns the last id in [table].'''
        try:
            self.__c.execute("SELECT MAX(id) FROM {}".format(table))
            return (True, int(self.__c.fetchone()[0]))

        except Exception as e:
            err_str = 'Error while getting last_id for {}: {}'.format(table, e)
            log.error(err_str)
            return(False, 'ERROR (GET_LAST_ID): ' + err_str)

    def export_data(self, target_db_name, table_ids):
        '''Creates new db named 'target_db_name' containing selected records from selected tables.

        'target_db_name' should be a full path (eg /home/hypermaq/data/export_db2.db)
        Table_ids should be a list with a list for each [table, start_id, stop_id]
        Leave start_id, stop_id empty for export from first record/to last record
        Ex: [['measurements', 200, 300], ['logs',,200], ['protocol', 10,]] will export measurement id 200 to 300, logs up to id 200, protocol starting at 10
        '''
        try:
            assert type(table_ids) == list, 'tables_ids should be a list of [table,start_id,stop_id] items'
            if len(table_ids) == 0: raise Exception('no target tables have been asked')
            
            dir_name = os.path.dirname(target_db_name)
            if not os.path.isdir(dir_name):
                os.makedirs(dir_name)
            
            result = self.__prepare_target_db(target_db_name, table_ids)
            if not result[0]:
                raise Exception(result[1])
            
            self.execute('ATTACH DATABASE ? AS target_db', (target_db_name,))  # attach the target database to our main db
            for line in table_ids:
                assert len(line) == 3, 'not enough fields, tables_ids should be a list of [table,start_id,stop_id] items'
                table, start_id, stop_id = line  # unpack list
                
                command = 'INSERT INTO {} SELECT * FROM {}'.format('target_db.' + table, table)  # base command for the export
                # need to use '{}'.format(...) instead of ? substitution since that can only be used for variables, not table names
                substitution = ()

                if start_id or stop_id:  # not all ids need to be exported
                    command += ' WHERE id '
                    if start_id and stop_id:
                        command += 'BETWEEN ? AND ?'
                        substitution += (start_id, stop_id -1)
                    elif start_id:
                        command += '> ?'
                        substitution += (start_id -1,)
                    elif stop_id:
                        command += '< ?'
                        substitution += (stop_id,)

                self.execute(command,substitution)
                self.execute("DETACH DATABASE 'target_db'")

                return (True, None)

        except AssertionError as e:
            self.execute("DETACH DATABASE 'target_db'")
            return(False, 'AssertionError: ' + str(e))
        except Exception as e:
            self.execute("DETACH DATABASE 'target_db'")
            return(False, e)

    def __prepare_target_db(self, target_db_name, list_of_lists):
        '''returns a list of the tables that are requested, filtering duplicates.'''
        try:
            tables_dict = dict()
            for i in list_of_lists:
                tables_dict[i[0]] = 1
            tables = list(tables_dict.keys())

            result = create_db(db_file=target_db_name, id=tables, populate_settings=False)
            if result[0]:
                return(True, None)
            else:
                return(False, result[1])

        except Exception as e:
            return(False, e)

    def vacuum_db(self):
        '''Tries to vacuum the database, then close and reopen.'''
        try:
            self.__commit_db()
            self.execute("VACUUM")
            return(True, None)

        except Exception as e:
            err_str = 'Error while vacuuming db: {}'.format(e)
            log.error(err_str)
            return(False, err_str)

def create_db(db_file = database_location, id=('all',), populate_settings=True):
    """Creates the database tables or db if it doesn't exist.

    id is a tuple containing the different tables "logs", "queue", "measurements", "protocol", "settings" or "all"
    db_file should be the full path
    Available datatypes: text, integer, real, blob, NULL
    Options:  "not null", "primary key", "autoincrement", "default '' ", "collate {nocase|binary|reverse}" (how sorting is done)
    After colums: unique(combination), check xxx
    Populate_settings will fill the settings table with default settings
    """
    if any(table not in valid_tables and not table == 'all' for table in id):  # there's an invalid table requested
        msg = "one of the provided tables is invalid. id should be a tuple. Valid: {} or 'all'".format(valid_tables)
        log.warning(msg)
        return(False, "ERROR (CREATE_DB) "+ msg)

    try:
        db = sqlite3.connect(db_file)
        with db:    # using context manager to automatically commit or roll back changes.
                    # when using the context manager, the execute function of the db should be used instead of the cursor
            if any(x in ('logs', 'all') for x in id):  # logs table
                db.execute("create table logs(id integer primary key autoincrement, " + 
                "timestamp date default (datetime('now', 'utc')), " + 
                "level text collate nocase, " + 
                "source text not null collate nocase, " + 
                "log text default null collate nocase)")

            if any(x in ('queue', 'all') for x in id):  # queue table
                db.execute("create table queue(id integer primary key autoincrement, " +
                "done integer not null default 0 collate nocase, " +
                "priority integer not null default 2, " +
                "fails integer NOT NULL DEFAULT 0, " +
                "timestamp date default (datetime('now', 'utc')), " +
                "action text not null collate nocase, " +
                "options text default null collate nocase)")

            if any(x in ('measurements', 'all') for x in id):  # measurement table
                base_command = ("create table measurements(id integer primary key autoincrement, " +
                "timestamp date default (datetime('now', 'utc')), " +
                "valid text default 'n' collate nocase, " +
                "setup_error text collate nocase, " +
                "cycle_id text, " +
                "gnss_acquired date,"
                "gnss_qual integer, " +
                "gnss_lat real, " +
                "gnss_lon real, " +
                "batt_voltage," +
                "head_voltage real, " +
                "head_temp_hpt text, " +
                "cycle_scan integer, " +
                "prot_sensor text, " +
                "prot_zenith integer, " +
                "prot_azimuth integer," +
                "sun_heading real, " +
                "sun_elevation real, " +
                "scan_heading real, " +
                "scan_error text, " +
                "scan_rep integer, " +
                "rep_error text, " +
                "rep_unix real, " +
                "rep_serial text, ")
                for i in range(1,257): 
                    base_command+= "val_{:03d} integer, ".format(i)  # add the 256 value columns
                complete_command = base_command[:-2] + ")"  # remove the comma and space at the end, replace by closing brackets
                db.execute(complete_command)

            if any(x in ('protocol', 'all') for x in id):  # protocol table
                db.execute("create table protocol(id integer primary key autoincrement, " +
                "number integer not null unique, " +
                "instrument text not null collate nocase, " +
                "zenith integer not null, " +
                "azimuth integer not null, " +
                "repeat integer not null default 1, " +
                "wait integer not null default 0)")

            if any(x in ('settings', 'all') for x in id):  # settings table
                db.execute("create table settings(setting text primary key not null collate nocase, " +
                "value text collate nocase)")
                if populate_settings:  # don't set default settings if this is a db for exporting data
                    default_settings = (
                        ('station_id', "MSO"),
                        ('manual', 1), 
                        ('measurements_start_hour', 6), 
                        ('measurements_stop_hour', 19), 
                        ('max_sun_zenith', 90), 
                        ('email_enabled', 1), 
                        ('email_recipient', ''), 
                        ('email_server_port', ''), 
                        ('email_user', ''), 
                        ('email_password', ''),
                        ('email_min_level', 'warning'),
                        ('ftp_server', ''),
                        ('ftp_user', ''),
                        ('ftp_password', ''),
                        ('ftp_working_dir', 'hypermaq'),
                        ('head_true_north_offset',180), 
                        ('radiance_angle_offset',20), 
                        ('irradiance_angle_offset',60), 
                        ('keepout_heading_low', 0),
                        ('keepout_heading_high', 0),
                        ('gnss_acquired', 'none'), 
                        ('gnss_lat', 51.2), 
                        ('gnss_lon', 2.9), 
                        ('gnss_qual', 0), 
                        ('gnss_mag_var', 0),
                        ('id_last_backup_meas', 0),
                        ('id_last_backup_log', 0),
                        ('system_set_up', 0)
                        )
                    db.executemany("insert into settings(setting,value) values (?, ?)", (default_settings))

            if 'all' in id:
                from file_utils import change_own_perm
                change_own_perm(db_file, user = 'hypermaq', group = 'hypermaq', permission = 0o666)

            return (True, None)

    except sqlite3.DatabaseError as e:
        err_str = 'sqlite3 error while creating db {}: {}'.format(id, e)
        log.error(err_str)
        return(False, 'ERROR (CREATE_DB): ' + err_str)

    except Exception as e:
        err_str = 'sqlite3 error while creating db {}: {}'.format(id, e)
        log.error(err_str)
        return(False, 'ERROR (CREATE_DB) ' + err_str)

def export_table_csv(table = 'measurements', date = False):
    '''Exports the [table] to comma-separated-value file .

    Takes an optional [date] argument, to export only data for that date. [date] should be in yyyymmdd format.

    If [table] refers to a table that doesn't have a timestamp column:
        - date argument is ignored.
        - filename is 'export_current_{tablename}_{date today}'

    If [table] has a timestamp column:
        - if no date is provided, data for today is exported
        - filename is 'export_day_{tablename}_{date}'

    If the target file already exists, a new filename is generated.
    returns (True, path + filename) if successful, (False, error message) if there's an error.'''

    tables_with_timestamp = ('measurements', 'queue', 'logs')
    data_path = os.path.join('/', 'home', 'hypermaq', 'data')
    extention = '.csv'
    sqlite3_full_path = '/usr/bin/sqlite3'
    sqlite3_option1 = '-header'
    sqlite3_option2 = '-csv'
    table = table.lower()

    try:
        if not (table in valid_tables):
            raise Exception('Invalid target table for export: {} (should be one of {}'.format(table, valid_tables))

        if table in (tables_with_timestamp):
            if date:  # a date was supplied as argument
                try:
                    target = datetime.strptime(date, '%Y%m%d')
                except ValueError:  # format of supplied date argument isn't correct
                    raise Exception('Invalid date provided: "{}" (should be YYYY-MM-DD)'.format(date))
            else:  # no date argument supplied
                target = datetime.now()

            filename_base = 'export_day_{tablename}_{date}'.format(tablename = table, date = target.strftime('%Y%m%d'))
            sqlite_query = 'select * from {} where date(timestamp) = "{}";'.format(table, target.strftime('%Y%m%d'))  # prepare the sqlite query

        else:  # table without timestamp column
            filename_base = 'export_current_{tablename}_{date}'.format(tablename = table, current_timestamp = target.strftime('%Y%m%d'))
            sqlite_query = 'select * from {};'.format(table)  # prepare the sqlite query

        # check if the filename is unique
        i = 1
        filename = filename_base  # try the simpelest filename, in its base form
        while os.path.isfile(os.path.join(data_path, (filename + extention))):  # a file with that name already exists
            filename = '{}_{:02d}'.format(filename_base, i)  # if filename already exists, add _xx at the end, starting at number 01 
            i += 1  # and increment until filename is unique

        complete_filename = os.path.join(data_path, (filename + extention))

        with open(complete_filename, 'w') as outputfile:  # context manager handles file closing in case of problems
            call([sqlite3_full_path, sqlite3_option1, sqlite3_option2, database_location, sqlite_query], stdout = outputfile)

    except Exception as e:
        return (False, e)


"""Main loop"""
if __name__ == "__main__":
    print("This module does nothing on its own, exiting now...")