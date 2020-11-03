## function to send hex command to active serial connection and parse return buffer
## QV 2018-07-17
## QV 2019-09-10 added packet size option - should be 8 for id packet and 64 for data packet

def serial_command_and_parse(ser, cmd_hex, req_packets, max_time=20, packet_size = None,
                             sleep=0.25, verbosity=0, require_checkbyte=True, return_buffer=False):

    if ser.isOpen():
        import time
        from trippy import trios_parse_buffer, trios_parse_packet, trios_filter

        cmd = bytearray.fromhex(cmd_hex)  # prepare hex command for send by serial
        if verbosity > 1: print('Sending {}'.format(cmd))
        ser.write(cmd)
        
        out, tw, packets = bytes(), sleep, []  # prepare variables, tw is working copy for sleep (counter)

        ## read serial buffer until we have enough packets or run out of time
        while (tw < max_time) & (len(packets) < req_packets):  
            ## read the serial port
            while ser.inWaiting() > 0:
                out += ser.read()  # read to buffer
        
            ## try to parse the current buffer
            tmp_packets = []
            srem = trios_filter(out)  #  trios_filter transforms characters as trios describes
            while(len(srem) > 0):  # srem is bytes from buffer where characters have been replaced
                srem, p = trios_parse_buffer(srem)  # goes through srem, returns first found packet as p, and returns remaining string to srem
                if len(p) > 0:  # trios_pars_buffer returns empty byte is no packet is found
                    pret = trios_parse_packet(p, require_checkbyte=require_checkbyte)  # processes packet and returns dict
                    if len(pret)>0:  # if something goes wrong in trios_parse_packet, it returns empty
                        if packet_size is not None:  # 8 for id, 64 for data
                            if pret['n_databytes'] != packet_size: continue  # SAMIP sometimes sends 9 instead of 8, throw away
                        tmp_packets.append(pret)  # add pret to list
    
            ## if we have enough packets exit the loop
            if len(tmp_packets) == req_packets: 
                packets = tmp_packets  # if number of packets is correct, fill packets 
        
            ## otherwise sleep a bit    
            time.sleep(sleep)
            tw += sleep  # counter

        ## clear the serial buffer in case we exited because of time
        ser.flushInput()

        if return_buffer:
            return(packets, out)
        else:
            return(packets)
