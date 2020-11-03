#! /usr/bin/python
# coding: utf-8
"""Basic description.

Ver 1.0 19jul2017

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""


"""Define constants."""

DEFAULT_CF_LOCATION = '/home/hypermaq/data/credentials'
DEFAULT_CREDENTIALS = ('email_user', 'email_password', 'email_server_port', 
                        'ftp_server', 'ftp_user', 'ftp_password',
                        'cam_user', 'cam_password')

"""Define variables."""
__all__ = ('get_credentials', 'create_empty_credentials')

"""Functions."""

def get_credentials(cf_location = DEFAULT_CF_LOCATION, credentials = DEFAULT_CREDENTIALS, all = False):
    """ Gets FTP/Email/... credentials (as defined by [credentials]) from the file specified by [cf_location].
    Returns dict with requested credentials (empty if not found in file)
    Each line of the file should be in the format "credential_name=value\n"
    Credentials in the file that are not in [credentials] are ignored.
    If file does not exist, a template file [cf_location] is created with the credentials defined in [credentials] but empty values.
    If all: returns dict with all credentials parsed from file.

    Variable abbreviations: c = credential, v = value
    """
    
    ## create dict with credentials that we want and empty values
    credentials_dict = {}
    if not all:
        for c in credentials:
            credentials_dict[c] = ''

    try:
        with open(cf_location,'r') as cf:  # open file for reading
            for line in cf:
                try:
                    c,v = line.split('=')  # read out line per line
                    if c in credentials_dict or all:  # add to dict if credential is required (or all are asked)
                        credentials_dict[c] =v.strip()
                except:  # one of the lines was not in correct format
                    continue

        return credentials_dict

    except IOError:  # file does not exist, create file with blank credentials
        result = create_empty_credentials(cf_location, credentials)
        if result[0]: return(dict())  # cf didn't exist yet, so new was created and empty dict returned
        else: raise Exception(result[1])  # cf didn't exist and couldn't be created


def create_empty_credentials(cf_location = DEFAULT_CF_LOCATION, credentials = DEFAULT_CREDENTIALS):
    """ Creates a template file [cf_location] with the credentials defined in [credentials] but empty values.
    
    Variable abbreviations: c = credential, v = value
    """
    try:
        with open(cf_location, 'w') as cf:
            for c in credentials:
                cf.write('{}=\n'.format(c))
        return(True, )
    except Exception as e:
        return(False, e)

"""Configuration settings."""


"""Main loop"""
if __name__ == '__main__':
    credentials = get_credentials(all=True)
    for c in credentials:
        print('{}={}'.format(c, credentials[c]))


"""Cleanup."""
