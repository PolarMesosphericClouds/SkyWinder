def get_uptime():
    with open('/proc/uptime') as fh:
        data = fh.read()
        return float(data.split()[0])