"""
This file is intended to be run manually with nosetests
"""
from subprocess import check_output
import socket

def test_sudo_no_password():
    try:
        result = check_output('sudo -n -l | grep NOPASSWD',shell=True)
        if result.find('NOPASSWD') >=0:
            return
    except Exception:
        pass
    assert False

def test_hostname():
    ip = socket.gethostbyname(socket.gethostname())
    assert ip.startswith('192.168.1')

def test_hosts():
    hosts = [('pmc-camera-%d' % k) for k in range(8)]
    hosts += [('pmc-charge-controller-%d' %k) for k in range(2)]
    hosts += [('pmc-serial-%d' %k) for k in range(2)]
    for host in hosts:
        ip = socket.gethostbyname(host)
        assert ip.startswith('192.168.1')



