## QV 2018-05-23
## based on TriOS documentation, replaces the filtered out control characters (indicated by @)
## @f -> 11
## @g -> 12
## @e -> 23
## @d -> 40
## does not work in the reverse way for sending commands to TriOS
## last modifications QV 2018-05-31 added test for Python 2 and changed bytes to bytesarray for Python 2

def trios_filter(sbuff, loop=True):
    import sys

    if sys.version_info[0] == 2: loop=False

    if loop:
        i = 0
        filtered = []
        while i < len(sbuff):
            b = int(sbuff[i])
            if (sbuff[i:i+2] == b'@f'):
                b = int.from_bytes(bytes.fromhex('11'), sys.byteorder)
                i+=1

            if (sbuff[i:i+2] == b'@g'):
                b = int.from_bytes(bytes.fromhex('13'), sys.byteorder)
                i+=1

            if (sbuff[i:i+2] == b'@e'):
                b = int.from_bytes(bytes.fromhex('23'), sys.byteorder)
                i+=1

            if (sbuff[i:i+2] == b'@d'):
                b = int.from_bytes(bytes.fromhex('40'), sys.byteorder)
                i+=1


            filtered.append(b)
            i+=1
        return(bytes(filtered))
    else:
        filtered=sbuff.replace(b'@f', bytearray.fromhex('11'))
        filtered=filtered.replace(b'@g', bytearray.fromhex('13'))
        filtered=filtered.replace(b'@e', bytearray.fromhex('23'))
        filtered=filtered.replace(b'@d', bytearray.fromhex('40'))
    return(filtered)
