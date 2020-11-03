#! /usr/bin/python
# coding: utf-8
"""Create backup of new data to temporary database and upload to ftp server.

Ver 1.0 22feb2019

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""
from ftp_lib import FTP_class
from datetime import datetime
import logging
import os
"""Define constants."""


"""Define variables."""


"""Functions."""
log = logging.getLogger("__main__.{}".format(__name__))

class backup_ftp(object):
    """creates backup of new data in measurements and logs tables.

    1. checks last succesful uploaded id's in m&l tables
    2. creates temp database with new data (include datetime in filename)
    3. connects to ftp and uploads file
    4. checks if file is succesfully uploaded (same filename and size)
    5. if succesful, delete temp db and update last updated id's in settings table
    """

    def __init__(self, db):
        """get required ftp settings from settings table"""
        self.db = db
        self.ftp_server = self.db.get_setting('ftp_server')[1]
        self.ftp_user = self.db.get_setting('ftp_user')[1]
        self.ftp_password = self.db.get_setting('ftp_password')[1]
        self.ftp_working_dir = self.db.get_setting('ftp_working_dir')[1]
        self.station_id = self.db.get_setting('station_id')[1]
        self.new_meas = False  # will be set to True if new measurements are found
        self.new_log = False  # will be set to True if new logs are found

    def __check_new_data(self, meas = False, logs = False):
        """Check if there's new data in a table, compared to last id stored in 'id_last_backup_meas/log'. 
        
        Keyword Arguments:
            meas {bool} -- "check if measurements table has new data?" (default: {False})
            logs {bool} -- "check if logs table has new data?" (default: {False})
        
        Returns:
            Tuple: 
                (True, '') if new data
                (False, 'no new data') if no new data
                (False, error message) in case an exception occured
        """

        try:
            if meas:
                try:
                    self.id_last_backup_meas = int(self.db.get_setting('id_last_backup_meas')[1])
                except:
                    self.id_last_backup_meas = 0
                self.id_last_meas = int(self.db.get_last_id('measurements')[1])
                if self.id_last_backup_meas < self.id_last_meas:  # new measurements since last backup?
                    self.new_meas = True

            if logs:
                try:
                    self.id_last_backup_log = int(self.db.get_setting('id_last_backup_log')[1])
                except:
                    self.id_last_backup_log = 0
                self.id_last_log = int(self.db.get_last_id('logs')[1])
                if self.id_last_backup_log < self.id_last_log:  # new logs since last backup?
                    self.new_log = True
            
            if self.new_log or self.new_meas:
                return (True, '')
            else: return (False, 'no new data')
        
        except Exception as e:
            msg = 'error checking for new data: {}'.format(e)
            log.error(msg)

            return (False, msg)

    def __generate_filename(self,dir_name):
        """Generates filename for backup database based on value of self.new_meas and self.new_log.
        
        filename: station_id_export_%Y%m%d_%H%M%S[_meas_(meas_last_backup_id)_(last_meas_id)][_logs_(log_last_backup_id)_(last_log_id)].db

        Arguments:
            dir_name {string} -- path to store new db in
        
        Returns:
            string -- complete path+filename+ext
        """

        filename = '{}_export_{}'.format(self.station_id, datetime.utcnow().strftime("%Y%m%d_%H%M%S"))  # base filename
        if self.new_meas:
            filename += '_meas_{}_{}'.format(self.id_last_backup_meas, self.id_last_meas)
        if self.new_log:
            filename += '_logs_{}_{}'.format(self.id_last_backup_log, self.id_last_log)

        filename += '.db'
        filename = os.path.join(dir_name, filename)

        return filename
        
    def __generate_export_list(self):
        """Creates list of lists describing what rows from what tables need to be backed up.
        
        Returns:
            list: 
                list containing a list [table, first id to backup, last id to backup] for each table that needs backup
        """

        export_list = []
        if self.new_meas:
            export_list += [['measurements', self.id_last_backup_meas + 1, self.id_last_meas]]
        if self.new_log:
            export_list += [['logs', self.id_last_backup_log + 1, self.id_last_log]]

        return export_list

    def do_backup(self, meas = True, logs = True, path = '/home/hypermaq/data/exports'):
        """Creates the backup db and uploads it to the FTP server.
        
        1. Checks for new data in chosen tables.
        2. Creates export filename and list
        3. Creates backup db
        4. Uploads to ftp and compares file sizes disk/ftp
        5. Deletes file from (local) disk
        
        Keyword Arguments:
            meas {bool} -- backup measurements? (default: {True})
            logs {bool} -- backup logs? (default: {True})
            path {str}  -- path to store backup db (default: {'/home/hypermaq/data/exports'})
        
        Returns:
            Tuple: 
                (True, '') if succesful
                (True, 'no new data for requested tables')
                (False, err) if not succesful
        """

        self.__check_new_data(meas = meas, logs = logs)
        if not self.new_meas and not self.new_log:  # no new data to backup
            return(True, 'no new data for requested tables')

        try:
            filename = self.__generate_filename(path)
            export_list = self.__generate_export_list()
            log.debug('filename for export: {}, list for export: {}'.format(filename, export_list))

            # file_created, msg = self.db.export_data(filename, export_list)  # export to db
            temp_res = self.db.export_data(filename, export_list)  # export to db
            file_created, msg = temp_res
            if not file_created:
                raise Exception('error during db export: {}'.format(msg))

            """ Upload to FTP """
            f = FTP_class(self.ftp_server, timeout= 20)
            result, msg = f.login(self.ftp_user, self.ftp_password)  # connect to ftp
            if not result:
                raise Exception('error during ftp login: {}'.format(msg))

            result, msg = f.cwd(self.ftp_working_dir)
            if not result:
                raise Exception('error during ftp cwd to {}: {}'.format(self.ftp_working_dir, msg))

            result, msg = f.upload_file(filename)
            if not result:
                raise Exception('error during ftp upload to {}: {}'.format(self.ftp_working_dir, msg))

            """ Compare file sizes of uploaded and original"""
            size_disk = int(os.path.getsize(filename))
            size_ftp = f.size(os.path.basename(filename))
            if not size_ftp[0]:
                raise Exception('error while checking ftp file size: {}'.format(size_ftp[1]))
            log.debug('filesize_disk: {}, size_ftp: {}'.format(size_disk, size_ftp[1]))
            if not size_disk == size_ftp[1]:  # different file size for original and uploaded file
                raise Exception('Size uploaded file ({}B) differs from original ({}B) for file {}'.format(size_ftp[1], size_disk, filename))

            """ clean up: remove backup db file and update settings with last backed up id's"""
            os.remove(filename)  # all went well, so delete file
            if self.new_meas:
                self.db.set_setting('id_last_backup_meas', self.id_last_meas)
                self.new_meas = False
            if self.new_log:
                self.db.set_setting('id_last_backup_log', self.id_last_log)
                self.new_log = False

            return (True, '')

        except Exception as e:
            if file_created:
                os.remove(filename)  # delete file
            log.error(e)
            return (False, e)