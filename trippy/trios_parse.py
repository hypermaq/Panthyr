## QV 2018-05-23
## simple function to parse a full trios serial buffer

## last modifications: 2018-05-29 (QV) removed the reversing of the data
##                     2018-05-30 (QV) changed from extracting data to adding the parsed packets to a list
##                     2018-05-31 (QV) added None check
##                     2018-06-07 (QV) added check for length of pret, added require_checkbyte keyword
def trios_parse(sbuff, require_checkbyte=True):
    from trippy import trios_filter, trios_parse_buffer, trios_parse_packet

    ## empty data list
    packets = []

    if sbuff is None:
        return(packets)

    ## filter out the replaced control bytes
    srem = trios_filter(sbuff)

    ## run through the packets in the buffer
    i=0
    while(len(srem) > 0):
        srem, p = trios_parse_buffer(srem)
        if len(p) > 0:
            pret = trios_parse_packet(p, require_checkbyte=require_checkbyte)
            if len(pret)>0:
                packets.append(pret)
                i+=1
   
    return(packets)
