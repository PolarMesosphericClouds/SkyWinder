import glob
from pmc_turbo.communication import packet_classes

def check_housekeeping(dir):
    count_dict = {}
    files = glob.glob(dir)
    files.sort()
    for fn in files:
        p = packet_classes.load_gse_packet_from_file(fn)
        #print hex(p.origin), hex(p.sync2_byte)
        sync2_origin = (p.sync2_byte, p.origin)
        if sync2_origin not in list(count_dict.keys()):
            count_dict[sync2_origin] = {'count':1, 'latest': fn}
        else:
            count_dict[sync2_origin]['count'] += 1
            count_dict[sync2_origin]['latest'] = fn
    return count_dict



if __name__ == "__main__":
    import sys
    dir = sys.argv[1]
    d = check_housekeeping(dir)
    for key in list(d.keys()):
        sync2, origin = key
        print('Sync2: %r, Origin: %r' % (hex(sync2), hex(origin)))
        print(d[key])
