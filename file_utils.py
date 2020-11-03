#! /usr/bin/python
# coding: utf-8
"""Some file utilities.

Ver 1.0 19feb2019

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?
"""

import pwd
import grp
import os


"""Define variables."""


"""Functions."""
def change_own_perm(filepath, user = -1, group = -1, permission = -1):
    """Changes ownership (user/group) and permissions for filepath.
    
    [permission] should be in octal format (0oXXX)
    returns True if succeeded, exception if failed
    """
    try:
        if not os.path.isfile(filepath):
            raise Exception('file {} doesn\'t exist'.format(filepath))
        gid = -1 if group == -1 else grp.getgrnam(group).gr_gid
        uid = -1 if user == -1 else pwd.getpwnam(user).pw_uid

        if not (uid == -1 and gid == -1):  # uid or gid needs to be changed
            os.chown(filepath, uid, gid)  # change ownership

        if permission >= 0: 
            os.chmod(filepath, permission)  # change permissions on file

        return True
    except Exception as e:
        return e



"""Configuration settings."""


"""Main loop"""


"""Cleanup."""
