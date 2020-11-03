#! /usr/bin/python
# coding: utf-8
## QV 2019-09-17
## checks ip and uploads file to ftp if changed (or always if override)

def panthyr_check_ip(local_dir = '/home/hypermaq/data', ## local dir to store ip file
             station= 'test', ## station name
             sub=True, ## use subprocess, otherwise urllib
             override=False, ## update anyway, even if ip hasn't changed
             verbosity=0,
             ## FTP credentials
             ftp_server = None,
             ftp_user = None,
             ftp_password = None):

    import ftplib, os
    from credentials import get_credentials

    ## get previous ip
    previous_ip = 'unknown'
    local_file = '{}/{}.ip'.format(local_dir,station)
    if os.path.exists(local_file):
        with open(local_file, 'r') as f: previous_ip = f.read().strip()
    if verbosity > 1: print('Previous ip for {}: {}'.format(station, previous_ip))

    ## find current ip
    try:
        if sub:
            import subprocess
            current_ip = subprocess.check_output(['curl','http://ipinfo.io/ip','-s']).strip()
        else:
            import urllib.request
            page = urllib.request.urlopen('http://ipinfo.io/ip')
            current_ip = page.read().strip()
    except:
        print('No connection')
        return(False)
    
    current_ip = current_ip.decode('utf-8')
    if verbosity > 1: print('Current ip for {}: {}'.format(station, current_ip))

    if any(i == None for i in (ftp_user, ftp_password, ftp_server)):
        cred =get_credentials(credentials=('ftp_user', 'ftp_password', 'ftp_server'))
        ftp_user = cred['ftp_user']
        ftp_password = cred['ftp_password']
        ftp_server = cred['ftp_server']

    ## if we have new ip, write and upload
    if (current_ip != previous_ip) | (override):
        with open(local_file, 'w') as f: 
            f.write(current_ip)

        ## start FTP session
        session = ftplib.FTP(ftp_server, ftp_user, ftp_password)

        ## change to ip directory
        ## make dir in case it got removed
        ## could be made recursive if there are multiple levels
        remote_dir = 'station_ips'
        try:
            session.cwd(remote_dir)
        except:
            session.mkd(remote_dir)
            session.cwd(remote_dir)

        ## upload file and close ftp
        remote_filename = '{}.ip'.format(station)
        with open(local_file,'rb') as file:
            session.storbinary('STOR {}'.format(remote_filename), file)
        session.quit()
        if verbosity > 0: print('Uploaded new ip for {} to FTP: {}'.format(station, current_ip))

    return(current_ip)

if __name__ == '__main__':
    import sys
    ## station name (last argument to script, or set here to string)
    station = None
    if len(sys.argv) != 2:
        print('This script should be called with the station name as argument')
        exit()
    if station is None:
        station = sys.argv[-1]

    ## local directory to store {station}.ip file
    local_dir = None
    if local_dir is None:
        import os
        local_dir = os.environ['HOME']
    current_ip = panthyr_check_ip(station=station, verbosity=0, override=True, sub=True)
