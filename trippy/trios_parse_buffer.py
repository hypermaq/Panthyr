## QV 2018-05-23
## gets the first data packet from the serial buffer
## last modifications QV 2018-05-31: added Python 2 support

def trios_parse_buffer(sbuff):
    import sys

    if len(sbuff) <= 1:
        return(b'',b'')
        
    ## this is especially for the first packet
    ## first character of the packet is a hash
    start_byte = sbuff.find(b'#')
    
    ## trim preceding stuff 
    ## typically \x13\x11 for the first packet
    sbuff = sbuff[start_byte:]
    
    ## return if buffer is now empty
    ## in case of just the 19 17 frame received
    if len(sbuff) <= 1:
        return(b'',b'')

    ## number of UINT16 values in the current packet
    ## this is done by bitshifting "device id 1" right by 5 places
    ## turning bits 7,6,5 in 2,1,0
    if sys.version_info[0] == 2:
        data_len = 2**((ord(sbuff[1]) & 224)>>5)
    else:
        data_len = 2**((sbuff[1] & 224)>>5)
    n_databytes = 2*data_len ## 1 UINT16 = 2 bytes

    ## packet length = 8 bytes and databytes
    packet_length = 8+n_databytes
    
    ## serial buffer is not long enough
    if len(sbuff) < packet_length:
        return(b'',b'')
    
    ## include the start char
    start = 0

    ## extract the packet from the buffer
    p = sbuff[start:packet_length]  # take packet out of buffer

    ## and return the data remaining in buffer
    srem = sbuff[packet_length:]  # strip buffer from working copy
    return(srem, p)
