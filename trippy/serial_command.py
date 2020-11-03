## function to send hex command to active serial connection
## QV 2018-05-30

def serial_command(ser, cmd_hex, sleep=0.25, verbosity=0):
    #print(ser)
    if ser.isOpen():
        import time

        cmd = bytearray.fromhex(cmd_hex)
        if verbosity > 0: print('Sending {}'.format(cmd))
        ser.write(cmd)
        
        out = bytes()

        # wait before reading output
        time.sleep(sleep)
        ib = 0
                    
        ## ser.inWaiting is the number of bytes waiting
        while ser.inWaiting() > 0:
            ib+=1
            smsg = ser.read(1)
            if verbosity > 2: print('Received byte {}: {}'.format(ib, str(smsg)))
            out += smsg
        if verbosity > 1: print('Received {}'.format(out))
        if verbosity > 0: print('length: {} bytes'.format(len(out)))
        return(out)
    
