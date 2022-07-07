from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import random
import logging

from pmc_turbo.communication.short_status import (ShortStatusLeader, one_byte_summary_bit_definitions,
                                                  decode_one_byte_summary, ShortStatusCamera)
from pmc_turbo.ground.lowrate_monitor import LowrateMonitorApp

logger = logging.getLogger(__name__)


class LowrateMonitorWidget(QtGui.QLabel):
    def __init__(self, lowrate_monitor, message_id, parent=None):
        super(LowrateMonitorWidget, self).__init__(parent)
        self.lowrate_monitor = lowrate_monitor
        self.message_id = message_id
        self.update_display()

    def update_display(self):
        # self.lowrate_monitor.update()
        try:
            values, latest_file = self.lowrate_monitor.latest(self.message_id)
        except KeyError:
            logger.debug("No info for %d" % self.message_id)
            return
        items = list(values.items())
        while items:
            print(items)
        logger.debug("Updated %d" % self.message_id)


class SimplePlotter(object):
    def __init__(self, lowrate_monitor, parent):
        self.lowrate_monitor = lowrate_monitor
        ssc = ShortStatusCamera()
        self.item_labels = list(ssc.values.keys())  # [format_item(name,1)[0] for name in ssc.values.keys()]
        num_columns = 8
        self.num_rows = len(self.item_labels)
        self.plot = pg.plot()
        self.curve = self.plot.plot()
        self.data = [0]

    def update(self):
        # for column in range(8):
        #     try:
        #         values, latest_file = self.lowrate_monitor.latest(column)
        #         print column, values
        #         self.data.append(random.random())
        #         self.curve.setData(self.data)
        #     except KeyError:
        #         continue
        try:

            values, latest_file = self.lowrate_monitor.latest(2)
            print(values)
            self.data.append(values['dcdc_wall_temp'])
            self.curve.setData(self.data)
        except KeyError:
            pass


if __name__ == "__main__":
    from pmc_turbo.utils import log

    log.setup_stream_handler(log.logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log.default_handler)
    app = QtGui.QApplication([])
    widget = QtGui.QWidget()
    widget.setWindowTitle("Low Rate Monitor")
    grid_layout = QtGui.QGridLayout()
    vertical_layout = QtGui.QVBoxLayout()
    gb = QtGui.QGroupBox()
    gb.setLayout(grid_layout)
    widget.setLayout(vertical_layout)
    vertical_layout.addWidget(gb)
    lrm_app = LowrateMonitorApp()
    lrm_app.initialize()
    lrm = lrm_app.lowrate_monitor
    sp = SimplePlotter(lrm, parent=widget)
    vertical_layout.addWidget(sp.plot)


    def update():
        lrm.update()
        sp.update()


    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(2000)
    widget.show()
    app.exec_()
