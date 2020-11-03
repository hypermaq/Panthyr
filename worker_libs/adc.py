#! /usr/bin/python
# coding: utf-8
"""Basic description.

Ver 1.0 19jul2017

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

More elaborate info
"""


# import

"""Define constants."""


"""Define variables."""


"""Functions."""
class batt_voltage(object):
    """Gets ADC value for input_number and converts to voltage.

    Returns int with voltage, or raw count if no conversion factor is given
    """

    def __init__(self, factor = None, input_number = 5, path = '/sys/bus/iio/devices/iio:device0/', filename = ('in_voltage', '_raw')):
        """initializes object.
        sets conversion factor to factor if it is int, otherwise to None"""
        import logging
        self.log = logging.getLogger("__main__.{}".format(__name__))

        self.filename = filename = filename[0] + str(input_number) + filename[1]
        self.complete_path = path + self.filename
        if isinstance(factor, int):
            self.factor = factor
        else:
            self.factor = None

    def check_config(self):
        """Returns True if all good, otherwise False"""
        from os.path import isfile
        if not isfile(self.complete_path):
            msg = 'File {} does not exist'.format(self.complete_path)
            self.log.error(msg)
            return False
        return True
    
    def get_voltage(self):
        """Returns int with voltage, or raw count if no conversion factor is given
        """
        with open(self.complete_path, 'r') as input:
            counts = input.read().strip()  # read line from file ends with \n
            try: 
                counts = int(counts)
            except:
                self.log.warning('{} returned a non int value: {}'.format(self.complete_path, counts))
                return None
            
            if self.factor:
                volts = round(counts / float(self.factor), 3)  # one of these factors needs to be a float, otherwise Python 2.6 truncates result to int
                return volts
            else:
                return ('raw: {}'.format(counts))
