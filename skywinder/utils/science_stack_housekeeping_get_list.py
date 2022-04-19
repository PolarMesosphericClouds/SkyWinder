from pmc_turbo.utils import decode_science_stack_housekeeping
from pmc_turbo.communication import packet_classes
import pandas as pd
import time
import datetime
import glob
import csv

def get_dict_from_housekeeping_dir(dir):
    status_dict = {}
    times = []
    fns = glob.glob(dir)
    fns.sort()
    has_keys = False

    for fn in fns:                                                            
         with open(fn, 'rb') as f:     
            buffer_ = f.read()
         try:
             packet = packet_classes.GSEPacket(buffer=buffer_)
             floats = decode_science_stack_housekeeping.interpret_payload(packet.payload)
             status = decode_science_stack_housekeeping.pack_floats_into_dict(floats)
             if not has_keys:
                for key in list(status.keys()):
                   status_dict[key] = []
                has_keys = True
             for key in status_dict:
                status_dict[key].append(status[key])
             # Assign timestamp
             date, hms = fn.split('/')[-1].split('_')[0:2]
             y, m, d = date.split('-')
             h, min, sec = int(hms[:2]), int(hms[2:4]), int(hms[4:])
             t = datetime.datetime(int(y), int(m), int(d), h, min, sec)
             epoch = time.mktime(t.timetuple())
             times.append(epoch)
         except Exception as e:
             print(e)
    status_dict['epoch'] = times
    return status_dict


def write_csv_from_housekeeping_dir(dir, outfn):
    d = get_dict_from_housekeeping_dir(dir)
    with open(outfn, 'wb') as f:
       writer = csv.writer(f)
       writer.writerow(list(d.keys()))
       writer.writerows(list(zip(*list(d.values()))))


if __name__ == "__main__":
    import sys
    fn = sys.argv[1]
    outfn = sys.argv[2]
    write_csv_from_housekeeping_dir(fn, outfn) 
