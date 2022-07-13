from skywinder.housekeeping import ethernet_switch

actual_switch_output = ' show version\n\r\n\rMAC Address      : a8-f7-e0-22-28-b6\n\rSystem Contact   : \n\rSystem Name      : IGS-20040MT\n\rSystem Location  : \n\rSystem Time      : 1970-01-10 Sat 00:00:44+00:00\n\rSystem Uptime    : 9d 00:00:44\n\rTemperature      : 52.0 C - 125.0 F\n\r\n\rActive Image\n\r------------\n\rImage            : managed\n\rVersion          : 1.342c160728\n\rDate             : 2016-07-28T11:52:43+0800\n\r\n\rAlternate Image\n\r---------------\n\rImage            : managed.bk\n\rVersion          : 1.342c150127\n\rDate             : 2015-01-27T19:10:29+0800\n\r\n\rProduct          : PLANET IGS-20040MT Managed Switch\n\rSoftware Version : 1.342c160728\n\rBuild Date       : 2016-07-28T11:52:43+0800\n\r\n\rIGS-20040MT#'
def test_no_data():
    result = ethernet_switch.parse_switch_info("nada")
    assert result is None

def test_valid_data():
    result = ethernet_switch.parse_switch_info(actual_switch_output)
    assert result == 52.0
