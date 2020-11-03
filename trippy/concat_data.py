## concat data
## concats data from TriOS packets
## split from trios_single QV 2018-06-07
##
## last modifications:
## combines all packets to one data string

def concat_data(packets):
    data = [0]*256
    if len(packets) >= 8:
        cur_frame = 7 ## first frame we need
        for i,p in enumerate(packets):
            if cur_frame < 0: continue ## stop when we have all 8 frames
            if p['framebyte'] != cur_frame: continue ## continue if the packet frame is not the one we currently need
            j = 7-cur_frame
            data[0+j*32:(j+1)*32]=p['data']
            cur_frame-=1
    return(data)
