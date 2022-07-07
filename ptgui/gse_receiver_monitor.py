import collections
import time

import sys

import pmc_turbo
import Pyro4, Pyro4.errors, Pyro4.util
from pyqtgraph.Qt import QtCore, QtGui


class Model(QtCore.QAbstractTableModel):
    def __init__(self):
        super(Model, self).__init__()
        self.files = collections.OrderedDict()
        self.gse_manager = Pyro4.Proxy("PYRO:gserm@localhost:55000")
        self.update()

    def update(self):
        try:
            file_statuses = self.gse_manager.get_file_status()
        except Pyro4.errors.CommunicationError as e:
            print(''.join(Pyro4.util.getPyroTraceback()))
            raise
        for link_name, file_status in list(file_statuses.items()):
            for file_id, status in list(file_status.items()):
                new_row = False
                if file_id in self.files:
                    this_file = self.files[file_id]
                    if (((len(status['packets_received']) == status['packets_expected'])
                        and ((time.time() - status['recent_timestamp']) > 120)) or
                            (time.time()-status['recent_timestamp']) > 900):
                        index = list(self.files.keys()).index(file_id)
                        self.beginRemoveRows(QtCore.QModelIndex(), index, index)
                        print("removing", index, file_id)
                        del self.files[file_id]
                        self.endRemoveRows()
                        continue
                    if status['recent_timestamp'] == this_file['recent_timestamp']:
                        continue
                else:
                    if ((len(status['packets_received']) == status['packets_expected'])
                        and (time.time() - status['recent_timestamp']) > 10):
                        continue
                    new_row = True
                status['link'] = link_name
                packet = status['first_packet']
                packets_received = len(status['packets_received'])
                status['total_packets_received'] = packets_received
                status['bytes_per_second'] = 0
                status['time_remaining'] = 0
                if status['first_timestamp'] != status['recent_timestamp']:
                    bytes_per_packet = packet.total_packet_length
                    status['bytes_per_second'] = bytes_per_packet * (packets_received-1) / (
                        status['recent_timestamp'] - status['first_timestamp'])
                    if status['bytes_per_second'] != 0:
                        status['time_remaining'] = (bytes_per_packet * (status['packets_expected'] - packets_received) /
                                               status['bytes_per_second'])

                if new_row:
                    self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
                self.files[file_id] = status
                if new_row:
                    self.endInsertRows()
                index = list(self.files.keys()).index(file_id)
                self.dataChanged.emit(self.createIndex(index, 0), self.createIndex(index + 1, self.columnCount()))

    def headerData(self, p_int, Qt_Orientation, int_role=None):
        if Qt_Orientation == QtCore.Qt.Vertical:
            return super(Model, self).headerData(p_int, Qt_Orientation, int_role)
        if int_role == QtCore.Qt.DisplayRole:
            return ['file_id', 'link', 'start', 'latest', 'total packets', 'received', 'bytes/s', 'remaining'][p_int]

    def rowCount(self, QModelIndex_parent=None):
        return len(self.files)

    def columnCount(self, QModelIndex_parent=None):
        return 8

    def data(self, QModelIndex, int_role=None):
        file_id = list(self.files.keys())[QModelIndex.row()]
        if QModelIndex.column() == 0:
            result = file_id
        else:
            columns = dict(list(zip(list(range(8)), ['', 'link', 'first_timestamp', 'recent_timestamp', 'packets_expected',
                                          'total_packets_received',
                                          'bytes_per_second', 'time_remaining'])))
            result = self.files[file_id][columns[QModelIndex.column()]]
        if (int_role is None) or (int_role == QtCore.Qt.InitialSortOrderRole):
            return result
        if int_role == QtCore.Qt.DisplayRole:
            if QModelIndex.column() == 0:
                return file_id

            if QModelIndex.column() in [2, 3]:
                return time.strftime("%H:%M:%S", time.localtime(result))
            return result
        if int_role == QtCore.Qt.ToolTipRole:
            if QModelIndex.column() in [2, 3]:
                return ('%.1f minutes ago' % ((time.time() - result) / 60.))
        if int_role == QtCore.Qt.FontRole:
            if QModelIndex.column() == 1:
                if self.files[file_id]['link'] == 'gse_sip':
                    f = QtGui.QFont()
                    f.setBold(True)
                    return f
            status = self.files[file_id]
            if QModelIndex.column() == 5:
                if status['total_packets_received'] != status['packets_expected']:
                    f = QtGui.QFont()
                    f.setBold(True)
                    return f
        if int_role == QtCore.Qt.ForegroundRole:
            status = self.files[file_id]
            if status['total_packets_received'] == status['packets_expected']:
                return QtGui.QBrush(QtCore.Qt.gray)

        return None


class SortingModel(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, p_int, QModelIndex):
        return True

    def lessThan(self, QModelIndex, QModelIndex_1):
        left = self.sourceModel().data(QModelIndex)
        right = self.sourceModel().data(QModelIndex_1)
        return left < right


if __name__ == "__main__":
    app = QtGui.QApplication([])
    win = QtGui.QMainWindow()
    win.setWindowTitle("Receiver Monitor")
    win.resize(800, 400)
    table_view = QtGui.QTableView()
    model = Model()
    sorting_model = SortingModel()
    sorting_model.setSourceModel(model)
    table_view.setModel(sorting_model)
    table_view.setAlternatingRowColors(True)
    table_view.setSortingEnabled(True)
    table_view.sortByColumn(0, QtCore.Qt.DescendingOrder)
    win.setCentralWidget(table_view)
    timer = QtCore.QTimer()
    timer.timeout.connect(model.update)
    timer.start(500)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
