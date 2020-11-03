#!/usr/bin/python
import subprocess
import sys  # to get argument
from email_warning import email_warning

DEFAULT_THRESHOLD = 300
DEFAULT_DEVICE = '/dev/mmcblk1p1'

def check_free_diskspace(device = '/dev/mmcblk1p1'):
    inp = subprocess.Popen(['df','-h', '-BM'], stdout = subprocess.PIPE)  
    # get output from 'df -h' 
    # (-h to get human readable format in MB)
    # -BM to format in MegaByte (power of 1024)
    outp = inp.communicate()[0].strip().split("\n")  # on each line remove the leading/trailing whitespaces and newline chars
    for l in outp[1:]:  # remove first line (with headers)
        fields = l.split()
        if fields[0] == device:  # If this is the correct device
            return(int(fields[-3][:-1]))  # return the int part of the 'free space' field

def check_enough_space(free):
    if free < threshold:
        return False
    else:
        return True

if __name__ == '__main__':
    try:
        arg = sys.argv[1:]
        
        if len(arg) == 0:
            print('No threshold value given, using the default value ({}M)'.format(DEFAULT_THRESHOLD))
            threshold = DEFAULT_THRESHOLD
        if len(arg) > 1:
            raise Exception('Too many parameters')
        if len(arg) == 1:
            threshold = int(sys.argv[1])

        free_space = check_free_diskspace(DEFAULT_DEVICE)

        msg = '{}MB free on {}, minimum is {}'.format(free_space, DEFAULT_DEVICE, threshold)

        if free_space < threshold:
            msg = 'Warning: ' + msg
            import logging
            logging.basicConfig()
            email_warning('Free space low', msg)

          
        print('{}MB free on {}, minimum is {}'.format(free_space, DEFAULT_DEVICE, threshold))

    except Exception as e:
        print(e)