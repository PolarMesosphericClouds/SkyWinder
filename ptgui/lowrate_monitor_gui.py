import collections
import logging
import time

from pyqtgraph.Qt import QtCore, QtGui

from pmc_turbo.communication.short_status import (ShortStatusLeader, one_byte_summary_bit_definitions,
                                                  decode_one_byte_summary, ShortStatusCamera)
from pmc_turbo.ground import short_status_format
from pmc_turbo.ground.lowrate_monitor import LowrateMonitorApp

logger = logging.getLogger(__name__)


def set_checkbox_color(checkbox,color):
    checkbox.setStyleSheet("QCheckBox:unchecked {border-color: %s; border-width: 2px; border-style: solid;}QCheckBox:checked {color: %s; border-style: solid; border-width: 1px; border-color: black;}" % (color,color))

class SingleByteSummaryWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(SingleByteSummaryWidget, self).__init__(parent=parent)
        self.labels = collections.OrderedDict([(text, QtGui.QLabel(text)) for text in one_byte_summary_bit_definitions])
        self.top_layout = QtGui.QGridLayout()
        self.setLayout(self.top_layout)
        for k, label in enumerate(self.labels.values()):
            self.top_layout.addWidget(label, k + 1, 0)
        self.checks = [collections.OrderedDict([(text, QtGui.QCheckBox()) for text in one_byte_summary_bit_definitions])
                       for k in range(8)]
        for k in range(8):
            self.top_layout.addWidget(QtGui.QLabel("%d" % k), 0, k + 1)
            for row, check in enumerate(self.checks[k].values()):
                self.top_layout.addWidget(check, row + 1, k + 1)
                check.setEnabled(False)

    def set_values(self, values):
        for camera_id in range(8):
            bit_values = decode_one_byte_summary(values['status_byte_camera_%d' % camera_id])
            for name, bit in list(bit_values.items()):
                if bit:
                    self.checks[camera_id][name].setCheckState(QtCore.Qt.Checked)
                    if name == 'is_leader':
                        set_checkbox_color(self.checks[camera_id][name],'limegreen')
                    else:
                        set_checkbox_color(self.checks[camera_id][name],'black')
                else:
                    self.checks[camera_id][name].setCheckState(QtCore.Qt.Unchecked)
                    if name in ['controller_alive', 'pipeline_alive', 'ptp_synced', 'time_synced', 'writing_images']:
                        set_checkbox_color(self.checks[camera_id][name],'red')



class LowrateMonitorWidget(QtGui.QLabel):
    def __init__(self, lowrate_monitor, message_id, num_columns=3, parent=None, font_size=6):
        super(LowrateMonitorWidget, self).__init__(parent)
        self.font_size = font_size
        self.lowrate_monitor = lowrate_monitor
        self.message_id = message_id
        self.num_columns = num_columns
        self.setFrameStyle(QtGui.QFrame.Box)
        self.update_display()

    def update_display(self):
        # self.lowrate_monitor.update()
        try:
            values, latest_file = self.lowrate_monitor.latest(self.message_id)
        except KeyError:
            logger.debug("No info for %d" % self.message_id)
            return
        if (time.time() - values['timestamp']) < 90:
            logger.debug("data for %d is fresh" % self.message_id)
            result = '<b>'
            end = '</b>'
        else:
            result = ''
            end = ''
        result = result + '<table cellspacing=3>'
        #        result = result + ('<tr><td colspan=%d align="center">%s</td></tr>' % (self.num_columns*2,latest_file))
        end = '</table>' + end
        items = list(values.items())
        while items:
            row = ''.join(
                [('<td>%s</td><td align="right">%s</td>' % format_item(*item)) for item in items[:self.num_columns]])
            row = '<tr>' + row + '</tr>'
            result = result + row
            items = items[self.num_columns:]
        self.setText(result + end)
        font = self.font()
        font.setPointSize(self.font_size)
        self.setFont(font)
        logger.debug("Updated %d" % self.message_id)


def format_item(name, value):
    if name == 'timestamp':
        result = time.strftime("%H:%M:%S", time.localtime(value))
        ago = time.time() - value
        result += '  -%d s' % ago
        if ago > 1200:
            result = '<font color="red">' + result + '</font>'
        return name, result
    if name == 'pressure':
        kpa = (value / 4.8 + 0.04) / 0.004
        return name, ('%.2f' % kpa)
    if name == 'rail_12_mv':
        return '12V rail', ('%.3f' % (value / 1000.))
    if name == 'aperture_times_100':
        return 'aperture', ('%.2f' % (value / 100.))
    if name == 'uptime':
        days, seconds = divmod(value, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        return name, '%dd %02d:%02d:%02s' % (days, hours, minutes, seconds)
    if name == 'frame_rate_times_1000':
        frame_rate = value / 1000.
        interval_ms = 1000. / frame_rate
        return "frame rate", ("%.3f (%.1f ms)" % (frame_rate, interval_ms))
    if name == 'focus_step':
        if value < 900:
            name = '<font color="red">' + name + '</font>'
            value = '<font color="red">%d</font>' % value
    if name == 'watchdog_status':
        if value < 500:
            name = '<font color="red">' + name + '</font>'
            value = '<font color="red">%d</font>' % value
    if name == 'status_byte_lidar':
        if value == 0:
            name = '<font color="red">' + name + '</font>'
            value = '<font color="red">%d</font>' % value
    if value in [127, 255, 32767, 65535, 2 ** 31 - 1, 2 ** 32 - 1]:
        if name in ['last_outstanding_sequence', 'sda_temp']:
            return name, '---'
        name = '<font color="red">' + name + '</font>'
        value = '<font color="red">---</font>'
    else:
        if 'charge_cont' in name:
            if 'voltage' in name:
                value = value * 180 * 2. ** -15
                value = '%.3f' % value
            if 'curr' in name:
                value = value * 80 * 2. ** -15
                value = '%.3f' % value

    return name, value


class LowrateTableWidget(object):
    def __init__(self, lowrate_monitor, parent):
        self.lowrate_monitor = lowrate_monitor
        ssc = ShortStatusCamera()
        self.item_labels = list(ssc.values.keys())  # [format_item(name,1)[0] for name in ssc.values.keys()]
        num_columns = 8
        self.num_rows = len(self.item_labels)
        self.table = QtGui.QTableWidget(self.num_rows, num_columns, parent)
        self.table.setAlternatingRowColors(True)
        for col in range(num_columns):
            name = str(col)
            item = QtGui.QTableWidgetItem(name)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.table.setHorizontalHeaderItem(col, item)
        for row in range(self.num_rows):
            name = short_status_format.get_item_name(self.item_labels[row])
            item = QtGui.QTableWidgetItem(name)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.table.setVerticalHeaderItem(row, item)
        self.table.setStyleSheet("QTableWidget::item {padding: 0px}")
        self.table.resizeRowsToContents()

    def update(self):
        for column in range(8):
            try:
                values, latest_file = self.lowrate_monitor.latest(column)
            except KeyError:
                continue
            for row in range(self.num_rows):
                item = self.table.item(row, column)
                if item is None:
                    item = QtGui.QTableWidgetItem()
                    self.table.setItem(row, column, item)

                name = self.item_labels[row]
                value = list(values.values())[row]

                formatted_value, format_string = short_status_format.format_short_status_camera(name, value)

                item.setText(str(list(values.values())[row]))
                if 'r' in format_string:
                    item.setForeground(QtGui.QBrush(QtGui.QColor('red')))
                elif 'g' in format_string:
                    item.setForeground(QtGui.QBrush(QtGui.QColor('green')))
                elif 'm' in format_string:
                    item.setForeground(QtGui.QBrush(QtGui.QColor('magenta')))
                elif 'b' in format_string:
                    item.setForeground(QtGui.QBrush(QtGui.QColor('blue')))
                else:
                    item.setForeground(QtGui.QBrush(QtGui.QColor('black')))
                item.setText(formatted_value)
        self.table.resizeColumnsToContents()


if __name__ == "__main__":
    from pmc_turbo.utils import log

    log.setup_stream_handler(log.logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log.default_handler)
    app = QtGui.QApplication([])
    geometry = app.desktop().geometry()
    if geometry.height() < 1000:
        font_size = 6
    else:
        font_size = 8
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
    leader = LowrateMonitorWidget(lrm, ShortStatusLeader.LEADER_MESSAGE_ID, parent=widget, font_size=font_size)
    grid_layout.addWidget(leader, 0, 0)
    sbs = SingleByteSummaryWidget()
    grid_layout.addWidget(sbs, 0, 1)
    widgets = [leader]
    tbl = LowrateTableWidget(lrm, parent=widget)
    vertical_layout.addWidget(tbl.table)


    # for row in range(4):
    #     for column in range(2):
    #         if row*2+column < 8:
    #             w = LowrateMonitorWidget(lrm,row*2+column,parent=widget,font_size=font_size)
    #             layout.addWidget(w,row+1,column)
    #             widgets.append(w)
    def update():
        lrm.update()
        tbl.update()
        for w in widgets:
            w.update_display()
        try:
            sbs.set_values(lrm.latest(ShortStatusLeader.LEADER_MESSAGE_ID)[0])
        except KeyError:
            pass


    timer = QtCore.QTimer()
    timer.timeout.connect(update)
    timer.start(2000)
    widget.show()
    app.exec_()
