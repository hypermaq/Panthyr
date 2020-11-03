#! /usr/bin/python
# coding: utf-8
"""Uses GPIO pins and FETS to toggle power to appliances.

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

v0.5 has pin mapping for the new power board
! If P8_43 is pulled low (through pull down resistor), the bbb does not boot...

Uses the following I/O pins:
|  PIN    |  GPIO  |  Line    |  Output   |  Device    |
------------------------------------------------------  
|  P9_27  |    115   |  Vcc1+2  |  Output1  |  NC                       |  05V
|  P9_41  |     20   |  Vcc1+2  |  Output2  |  P/T SSR                  |  05V
|  P8_39  |    76    |  Vcc3+4  |  Output3  |  TOP box                  |  12V
|  P8_45  |    70    |  Vcc3+4  |  Output4  |  Multiplex board          |  12V
|  P8_35  |     8    |  Vcc5+6  |  Output5  |  GNSS                     |  24V
|  P8_33  |     9    |  Vcc5+6  |  Output6  |  Intercoax converter      |  24V
|  P8_40  |    77    |          |  RS485    |  ~RE (*)                  |
|  P8_42  |    75    |          |  RS485    |  DE                       |
(*) RS 485 RE is active low

"""

import sys  # access to arguments
import getopt  # tool to parse arguments
from subprocess import call 
from subprocess import check_output
import logging
from time import sleep

"""Define constants."""
#  lookup dictionaries for GPIO pins and states
GPIO_outputs = {"output1": "115", "output2": "20", "output3": "76", "output4": "70", "output5": "8", "output6":'9', "_rs485re": "77", "rs485de": "75"}
GPIO_states = {"on": "1", "off": "0"}
__all__ = ["setup_pins", "toggle_pwr", "check_pins"]


"""Functions."""

log = logging.getLogger("__main__.{}".format(__name__))

def setup_pins():
    """Set pins from [GPIO_outputs] as output, disables internal pull-up and sets all except _rs485re LOW."""

    for pin in GPIO_outputs:
        path = "/sys/class/gpio/gpio{}/direction".format(GPIO_outputs[pin])

        sleep(0.4)  # if no sleep between two writes to /sys/class/gpio/unexport, we get random "echo: write error: Invalid argument" errors
        # log.info('setting unexport for {}({})'.format(pin, (GPIO_outputs[pin])))
        with open("/sys/class/gpio/unexport","w") as target:  # we want to redirect the echo output to /sys/class/gpio/unexport
            call(["echo", GPIO_outputs[pin]], stdout=target)

        # log.info('setting export for {}({})'.format(pin, (GPIO_outputs[pin])))
        with open("/sys/class/gpio/export","w") as target:  # we want to redirect the echo output to /sys/class/gpio/export
            call(["echo", GPIO_outputs[pin]], stdout=target)
        
        # log.info('setting state for {}({})'.format(pin, (GPIO_outputs[pin])))
        with open(path, "w") as target:
            if not pin == "_rs485re":
                call(["echo", "low"], stdout = target)  # "low" to direction combines setting as output and setting low
            else:
                call(["echo", "high"], stdout = target)  # rs485re is active low
 

def toggle_pwr(output, state):
    """Toggles the IO pins high or low.

    Output1  |  P/T head|
    Output2  |  GNSS    |
    Output3  |  Ramses  |
    Output4  |  Insys 4G|
    Output5  |  IP Cam  |
    _rs485re |  RE      |
    rs485de  |  DE      |
    
    state = on/off
    """
    if output not in GPIO_outputs:
        return "ERROR (TOGGLE_PWR): output '{}' not a valid output (should be 'outputx')".format(str(output))
    if state not in GPIO_states:
        return "ERROR (TOGGLE_PWR): state '{}' not a valid state (should be 'on' or 'off')".format(str(state))

    try:
        path = "/sys/class/gpio/gpio{}/value".format(GPIO_outputs[output])
        argument = GPIO_states[state]
        
        with open(path, "w") as target:
            call(["echo", argument], stdout=target)
        return "OK"

    except Exception as e:
        msg = "Could not set '{}' ({}) to state '{}' ({})\n {}".format(output, GPIO_outputs[output], state, GPIO_states[state], e)
        log.warning(msg)
        return ("ERROR" + msg)


def check_pins():
    """Returns dictionary with states of pins in [GPIO_outputs]."""
    status = dict()
    for pin in GPIO_outputs:
        path = "/sys/class/gpio/gpio{}/value".format(GPIO_outputs[pin])
        status[pin] = check_output(["cat", path]).strip()  # strip newline and CR from reply
    return status


"""Main loop"""
# everything below is for testing
if __name__ == "__main__":
    try:
        opts, arg = getopt.getopt(sys.argv[1:], "", ["setup", "output1=", "output2=", "output3=", "output4=", "output5=", "output6="])  # returns a list with each option,argument combination
        if len(opts) == 0:  # no valid arguments have been provided
            raise Exception
        
        for option, argument in opts:  # first check if any of the options is --setup, if so: setup and exit
            if option[2:] == "setup":
                setup_pins()
                exit()
            elif argument in ("on", "off"):
                toggle_pwr(option[2:], argument)
            else:
                raise Exception            

    except Exception as e:  # no or invalid arguments have been provided at the command line.
        print("""gpio.py
     Exception: {}

     Usage: 
        To setup: sudo gpio.py --setup

        To control pins:
            sudo gpio.py --outputX=Y 
            where x is 1-5 and Y is on or off
            Example: sudo gpio.py --output1=on --output2=off
        
        Current status:
     """.format(e))
        lookup = {'1':'on', '0':'off'}
        for i,j in check_pins().items():
            print("{} | {}".format(i,lookup[j]))