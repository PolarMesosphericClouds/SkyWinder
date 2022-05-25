from skywinder.utils.uptime import get_uptime

def test_uptime():
    assert get_uptime() > 0
