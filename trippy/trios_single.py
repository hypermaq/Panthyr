## trios_single
## identifies SAM module on given serial port and makes a single measurement
## QV 2018-05-30
## last modifications QV 2018-05-31 changed query i2c address to 80, and use 2 command measuring mode
##                                  new packet concatenation in case of samip unit (skip information packets, skip IP data packets)
##                                  new auto integration wait time int_time and int_max options
##                    QV 2018-06-04 new error handling, returns [True, error_message] if unable to connect or find instrument
##                                  new repeat measurement option, where for each measurement time and data is logged:
##                                  [error_message, device, time, [data]], error_message is empty if all is well
##                                  changed data concatenation, so it always returns 256 elements, and the missing packet is replaced by zeros
##                    QV 2018-06-07 fixed packet tracking bug for SAMIP 5050, split off concat_data
##                    QV 2018-07-17 new serial_command_and_parse subroutine for live parsing of data stream, removed sleeping options
##                    QV 2019-09-10 added data packet size (8 and 64 bits) for different commands to work with live monitoring (SAMIP fix)
##                    QV 2019-09-11 added number of saturated pixel in the trippy auto int option (int_time=-1) since it could go wrong if measurements are started too fast

def trios_single(port, baudrate=9600, parity='N', stopbits=1, bytesize=8, xonxoff=False, timeout=0.01, 
                 int_time = 0, int_max = 12, ips_channel=0, 
                 repeat = 1, verbosity=0, return_buffer=False, require_checkbyte=True, sleep = 0.1, max_time = 16):

    import serial, time, sys
    from trippy import serial_command_and_parse, concat_data
    error = False
    # sleep, max_time = sleep, max_time

    try:
        ##
        if int(int_time) not in range(-1, 13):
            raise Exception('Invalid int_time option given: {}'.format(int_time))
        if int(ips_channel) not in range(0,5):
            raise Exception('Invalid ips_channel option given: {}'.format(ips_channel))

        ## format IPS box channel and integration time in hex
        ips_char = hex(int(ips_channel*2)).replace('x','')  # Output ID for IPS box, 0 if straight connection to sensor
        int_char = hex(int(int_time)).replace('x','')#.upper()  
        int_max = abs(int_max)

        ## get number of repeat measurements
        repeat = max(1, int(repeat))

        ## make connection to serial port
        try: 
            ser = serial.Serial(port=port,
                baudrate=baudrate,
                parity=parity,
                stopbits=stopbits,
                bytesize=bytesize,
                xonxoff=xonxoff, 
                timeout=timeout)
        except:
            e = sys.exc_info()
            raise Exception('Could not connect to port {}'.format(port))

        try:
            ## connect to the serial port
            if ser.isOpen():
                if verbosity > 1: print('Connected to {}'.format(port))
                ## query sam # 80 instead of 30
                try:
                    cmd_hex = '23 {} 00 80 B0 00 00 01'.format(ips_char)  # command to query serial number
                    
                    ## new command and parse
                    req_packets = 1  # expect 1 packet
                    packet_size = 8  # containing 8 bits
                    packets = serial_command_and_parse(ser, cmd_hex, req_packets, packet_size=packet_size, 
                                                       sleep=sleep, max_time=max_time, require_checkbyte=require_checkbyte)
                    if len(packets) > 0:
                        dev = '{}_{}'.format(packets[0]['module_type'], packets[0]['serial'])
                        if verbosity > 1: print('Found {} on {}'.format(dev, port))
                    else:
                        raise Exception('No identifier packet received')
                except:
                    e = sys.exc_info()
                    raise Exception('Could not determine sensor id: {}'.format(e[1].__str__()))
        except:
            e = sys.exc_info()
            raise Exception('Could not connect to sensor: {}'.format(e[1].__str__()))

        data_list = []
        for rm in range(repeat):
            ## perform sam measurement with integration time (00 = auto)
            try:
                if int_time >= 0:  # trios modus (0 is auto, >0 is fixed)
                    utime = time.time()
                    #cmd_hex = '23 {} 00 80 A8 00 {} 01'.format(ips_char, int_char)
                    cmd_hex = " ".join(["23 {} 00 30 78 05 {} 01".format(ips_char, int_char),\
                                        "23 {} 00 80 A8 00 81 01".format(ips_char)])  # command for measurement

                    ## new command and parse
                    if verbosity > 1: print('(sample {}) Using {} integration ({} ms)'.format(rm+1, int_char, 'auto' if int_time == 0 else 2**(1+int_time)))
                    req_packets = 8  # buffer is 8 packets
                    packet_size = 64  # 64 data bytes per packet
                    # sleep, max_time = 1, 5
                    packets, out = serial_command_and_parse(ser, cmd_hex, req_packets, packet_size=packet_size,
                                                       sleep=sleep, max_time=max_time, require_checkbyte=require_checkbyte, return_buffer=True, verbosity = verbosity)
                         
                else:  # trippy integration time system
                    int_it = 1  # number of iterations
                    while int_it <= int_max:
                        utime = time.time()
                        int_char = hex(int(int_it)).replace('x','')
                        cmd_hex = " ".join(["23 {} 00 30 78 05 {} 01".format(ips_char, int_char),\
                                                "23 {} 00 80 A8 00 81 01".format(ips_char)])

                        ## new command and parse
                        if verbosity > 1: print('(sample {}) Using {} integration ({} ms)'.format(rm+1, int_char, 2**(1+int_it)))
                        req_packets = 8
                        packet_size = 64
                        # sleep, max_time = 1, 5
                        packets_int, out_int = serial_command_and_parse(ser, cmd_hex, req_packets, packet_size=packet_size,
                                                               sleep=sleep, max_time=max_time, require_checkbyte=require_checkbyte, return_buffer=True, verbosity = verbosity)

                        ## check for saturation
                        sat_pix = []
                        for p in packets_int:  # packets int
                            sat_pix += [v >= 65535 for v in p['data']]  #  creates list with True/False for each value
                        sat_pix_id = [iv for iv, v in enumerate(sat_pix) if v]  # sat_pix contains list of the values that are True
                        #sat = any([any([v >= 65535 for v in p['data']]) for p in packets_int])
                        sat = len(sat_pix_id) > 0
                        if sat:
                            if verbosity > 2: print('Reached saturation for int_time {}'.format(int_it))
                            if verbosity > 3: print('Reached saturation for {} pixels'.format(len(sat_pix_id)))
                            int_it+=int_max
                        else:
                            packets = [p for p in packets_int]
                            out = [o for o in out_int]
                        int_it+=1

                        ## test if we are at max integration time
                        if (not sat) & (int_it > int_max):
                            if verbosity > 2: print('Reached max int_time {}'.format(int_max))

            except:
                e = sys.exc_info()
                raise Exception('Could not complete measurement cycle: {}'.format(e[1].__str__()))

            ## concat data from packets
            try:
                data = concat_data(packets)
                tmp = [d == 0 for d in data]
                if all(tmp): raise Exception('Not enough packets received')
                if any(tmp): raise Exception('Incomplete data frames')
                if return_buffer:
                    data_list.append(['', dev, utime, data, out, packets])
                else:
                    data_list.append(['', dev, utime, data])
            except:
                e = sys.exc_info()
                data_list.append([e[1].__str__(), dev, utime, data])
        ser.close()
    except:
        error = True
        e = sys.exc_info()
        error_msg = e[1].__str__()
        ser = None
        if verbosity > 0: print(error_msg)
    
    if error:
        return([error, error_msg])
    else:
        return([error, data_list])
