## QV 2018-05-23
## parses a data packet from the TriOS
##
## last modifications QV 2018-05-29: added module id from information frame, parsing of SAM modules
##                    QV 2018-05-30: added verbosity, and COM module identification
##                    QV 2018-05-31: added IPS and SAMIP to COM module identification (not a 100% sure)
##                                   added Python 2 compatibility
##                    QV 2018-06-07: added require_checkbyte keyword

def trios_parse_packet(p, verbosity=0, require_checkbyte=True):
    import struct, sys

    ## make empty return packet
    packet = {}
    
    ## convert bytes to integers
    if sys.version_info[0] == 2:
        data = [ord(i) for i in p]
    else:
        data = [i for i in p]

    ## check if starting hash is present
    #if data[0] != int.from_bytes(b'#', sys.byteorder):
    if data[0] != ord(b'#'):
        if verbosity > 0: print('Starting hash is not present.')
        return()

    ## check the checkbyte
    packet['checkbyte'] = data[-1]
    if packet['checkbyte'] != 1:
        if verbosity > 0: print('Checkbyte is not 1: {}'.format(packet['checkbyte']))
        if require_checkbyte: return()

    ## get header bytes
    packet['hash'] = data[0]
    packet['identity1'] = data[1]
    packet['identity2'] = data[2]
    packet['module_id'] = data[3]
    packet['framebyte'] = data[4]
    packet['timeflag1'] = data[5]
    packet['timeflag2'] = data[6]
    packet['reserved1'] = data[5]
    packet['reserved2'] = data[6]
            
    ## data frame
    ## number of 16 bit UINT values
    len_data = 2**((packet['identity1'] & 224)>>5)
    ## number of databytes
    packet['n_databytes'] = 2*len_data
    
    ## get data bytes
    packet['databytes'] = p[7:7+packet['n_databytes']]

    ## reformat to 16 bit UINT data
    packet['data']=struct.unpack('<'+'H'*len_data, packet['databytes'])

    packet['frame_type'] = 'data'

    ## to do!
    if packet['framebyte'] == 255:
        packet['frame_type'] = 'information'
        packet['serial_lo'] = data[7]
        packet['serial_hi'] = data[8]
        packet['firmware_lo'] = data[9]
        packet['firmware_hi'] = data[10]
        packet['reserved3'] = data[11]
        packet['query_data'] = data[12:-1]

        ## unpack the serial number
        if sys.version_info[0] == 2:
            packet['serial_uint16'] = struct.unpack('<'+'H', p[7:9])[0]
            packet['serial'] = hex(packet['serial_uint16'])[2:]
        else:
            packet['serial_uint16'] = struct.unpack('<'+'H', bytes((packet['serial_lo'],packet['serial_hi'])))[0]
            packet['serial'] = hex(packet['serial_uint16'])[2:]
        
        #tmp = (packet['serial_uint16'] - (packet['serial_uint16'] & sum([2**i for i in range(11,16)])) )
        #print(format(tmp, '16b').replace(' ','0'))
        #hex(tmp)
        
        packet['module_type'] = 'Unknown'  # placeholder
        snhi = sum([2**i for i in range(11,16)]) ## these are module type identifiers
        # serial number hi index

        flu_modules = [(0,0,0,1,0)]
        flu_modules_uint = [sum([iv*2**(15-i) for i,iv in enumerate(module)]) for module in flu_modules]

        sam_modules = [(1,0,0,0,0), (1,0,0,0,1),(1,0,0,1,0), (1,0,0,1,1)]
        sam_modules_uint = [sum([iv*2**(15-i) for i,iv in enumerate(module)]) for module in sam_modules]

        ## 0 1 0 0 1 is probably IPS
        ## 0 1 0 1 0 is probably SAMIP
        com_modules = [(0,1,0,0,0), (0,1,0,0,1),(0,1,0,1,0), (0,1,0,1,1)]
        com_modules_uint = [sum([iv*2**(15-i) for i,iv in enumerate(module)]) for module in com_modules]

        ips_modules = [(0,1,0,0,1)]
        ips_modules_uint = [sum([iv*2**(15-i) for i,iv in enumerate(module)]) for module in ips_modules]
        
        samip_modules = [(0,1,0,1,0)]
        samip_modules_uint = [sum([iv*2**(15-i) for i,iv in enumerate(module)]) for module in samip_modules]

        if packet['serial_uint16'] & snhi in sam_modules_uint:
            packet['module_type'] = 'SAM'
            #print(packet['serial_uint16'] - (packet['serial_uint16'] & snhi))
            #print(hex(packet['serial_uint16'] - (packet['serial_uint16'] & snhi)))
        elif packet['serial_uint16'] & snhi in com_modules_uint:
            packet['module_type'] = 'COM'
            if packet['serial_uint16'] & snhi in ips_modules_uint:
                packet['module_type'] = 'IPS'
            if packet['serial_uint16'] & snhi in samip_modules_uint:
                packet['module_type'] = 'SAMIP'
        elif packet['serial_uint16'] & snhi in flu_modules_uint:
            packet['module_type'] = 'FLU'

        else:
            if verbosity > 0: print('Unknown module connected: {}'.format(packet['serial']))
    elif packet['framebyte'] == 254:
        packet['frame_type'] = 'error'
       

    if verbosity > 0: print('{} frame'.format(packet['frame_type']))

    return(packet)
