import telnetlib
import re
import os
import time
log_dir = '/var/pmclogs/housekeeping/switch'

def get_switch_info(address='pmc-ethernet-switch-0'):
    tn = telnetlib.Telnet(address,timeout=60)
    tn.read_until('Username:')
    tn.write('admin\r')
    tn.read_until('Password:')
    tn.write('admin\r')
    tn.read_until('#')
    tn.write('show version\r')
    result = tn.read_until('#')
#    tn.write('show env power\r')   #this doesn't seem to work over telnet
#    result += tn.read_until('#')
    tn.write('exit\r')
    tn.close()
    return result

def parse_switch_info(info):
    temperature_string = re.findall(' \d+\.\d C',info)
    if temperature_string:
        temperature_string = temperature_string[0]
    try:
        temperature = float(temperature_string[:-1])
    except Exception as e:
        print(temperature_string, e)
        temperature = None
    return temperature

if __name__ == "__main__":
    filename = os.path.join(log_dir,(time.strftime('%Y-%m-%d_%H%M%S.csv')))
    with open(filename,'w') as fh:
        fh.write('epoch,temperature\n')
    last_epoch = 0
    while True:
        if time.time() - last_epoch > 30:
            temperature = None
            epoch = time.time()
            try:
                temperature = parse_switch_info(get_switch_info())
                print(time.ctime(), ' : ', temperature)
            except Exception as e:
                print(e)
            with open(filename,'a') as fh:
                fh.write('%r,%r\n' % (epoch,temperature))
            last_epoch = epoch
        else:
            time.sleep(1)

