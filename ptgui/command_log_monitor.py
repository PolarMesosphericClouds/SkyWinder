import glob
import json
import logging
import os

import time

import sys
from pyqtgraph.Qt import QtCore,QtGui

from traitlets.config import Application
from traitlets import Unicode,List,Enum
import pmc_turbo.utils.configuration

from pmc_turbo.ground.command_history import CommandHistory
from pmc_turbo.ground.lowrate_monitor import LowrateMonitor
from pmc_turbo.communication.short_status import ShortStatusLeader
from pmc_turbo.communication.command_table import destination_to_string
from pmc_turbo.communication.packet_classes import gse_acknowledgment_codes
from pmc_turbo.camera.pipeline.indexer import MergedIndex
from pmc_turbo.communication.file_format_classes import load_and_decode_file, JSONFile,CompressedJSONFile,GeneralFile,ShellCommandFile,CompressedGeneralFile

logging.basicConfig()
logger=logging.getLogger(__name__)

def get_column(row,index):
    return str(row[index])
def get_destination_column(row,index):
    return destination_to_string(row[index])
def get_timestamp_column(row,index):
    return time.strftime("%H:%M:%S", time.localtime(row[index]))
def get_command_file_column(row,index):
    return os.path.split(row[index])[1]
def get_arguments_column(row,index):
    args = row[index]
    if list(args.keys()) and (list(args.keys())[0] == 'list_argument'):
        return str(args['list_argument'])
    return '\n'.join([('%s : %r' % (name, value)) for (name,value) in list(args.items())])


columns = [('timestamp', get_timestamp_column, 0),
           ('sequence\nnumber', get_column, 1),
           ('destination', get_destination_column, 3),
           ('status', None, None),
           ('received', None, None),
           ('command', get_column, 8),
           ('arguments', get_arguments_column, 9),
           ('response', None, None),
           ('link id', get_column, 4),
           ('command file', get_command_file_column,7),
           ('commands\nin packet', get_column, 2)]
column_names = [name for (name,_,_) in columns]

def get_send_status(row):
    ack = row[5]
    success = row[6]
    if success:
        return "sent ok"
    try:
        return gse_acknowledgment_codes[ack]
    except KeyError:
        return "unknown: %d" % ack


class CommandTableModel(QtCore.QAbstractTableModel):
    def __init__(self, config):
        super(CommandTableModel, self).__init__()
        self.command_history = CommandHistory(config=config)
        self.command_history.set_directory()
        self.lowrate_monitor = LowrateMonitor(config=config)
        self.received_files = MergedIndex('*/*',data_dirs = [self.command_history.root_data_path], index_filename='requested_file_index.csv')
        self.received_files.update()
        self.total_rows = 0
        self.update()
        self._viewers = []

    def update(self):
        self.lowrate_monitor.update(100,lowrate_file_suffix='FE') # restrict to leader status for efficiency
        self.received_files.update()
        new_rows = self.command_history.update()

        new_row_count = self.command_history.history.shape[0]
        if new_rows:
            old_row_count = new_row_count - new_rows
            self.beginInsertRows(QtCore.QModelIndex(), old_row_count, new_row_count-1)
            self.total_rows = new_row_count
            self.endInsertRows()
            self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(new_row_count, self.columnCount()))

    def headerData(self, p_int, Qt_Orientation, int_role=None):
        if Qt_Orientation == QtCore.Qt.Vertical:
            return super(CommandTableModel, self).headerData(p_int, Qt_Orientation, int_role)
        if int_role == QtCore.Qt.DisplayRole:
            return column_names[p_int]

    def rowCount(self, QModelIndex_parent=None):
        return self.total_rows

    def columnCount(self, QModelIndex_parent=None):
        return len(column_names)

    def check_command_received(self, sequence_number):
        leader_statuses = [self.lowrate_monitor.lowrate_data[fn] for fn in self.lowrate_monitor.by_message_id.get(ShortStatusLeader.LEADER_MESSAGE_ID,[])]
        failed_sequence_numbers = set([status.get('last_failed_sequence',-1) for status in leader_statuses])
        if sequence_number in failed_sequence_numbers:
            return 'recvd, ERRORED'
        explicit_sequence_numbers = set([status.get('last_command_sequence',-1) for status in leader_statuses])
        explicit_sequence_numbers.union(set([status.get('highest_command_sequence',-1) for status in leader_statuses]))
        if sequence_number in explicit_sequence_numbers:
            return 'recvd'
        missing_sequence_numbers = set([status.get('last_outstanding_sequence',-1) for status in leader_statuses])
        if sequence_number in missing_sequence_numbers:
            return "LOST"
        return "??"

    def get_response(self,row):
        args = row[9]
        try:
            request_id = args['request_id']
        except KeyError:
            return None
        try:
            rows = self.received_files.df[self.received_files.df.request_id == request_id]
            if len(rows) == 0:
                return None
            #print "found", len(rows)
            for k,row in rows.iterrows():
                return row.filename
        except AttributeError:
            return None

    def cell_click(self,QModelIndex):
        print("cell click", QModelIndex.row(),QModelIndex.column())
        if QModelIndex.column() == 7:
            value = self.data(QModelIndex,int_role=QtCore.Qt.DisplayRole)
            print(value)
            if type(value) is str:
                print("file",os.path.exists(value),value)
                filename = glob.glob(value.replace('files','payloads')+'.*')[0]
                print(filename)
                file_class = load_and_decode_file(value)
                print(file_class._preferred_extension)
                if file_class._preferred_extension != '.jpg':

                    dialog = QtGui.QDialog(self.parent(),flags=QtCore.Qt.Window)
                    widget = QtGui.QTextEdit()
                    if file_class._preferred_extension == '.json':
                        text = json.dumps(json.loads(file_class.payload), separators=(',', ': '), indent=4, sort_keys=True)
                    else:
                        text = file_class.payload
                    widget.setText(text)
                    layout = QtGui.QVBoxLayout()
                    layout.addWidget(widget)
                    dialog.setLayout(layout)
                    dialog.setWindowTitle("%d: %s" % (file_class.request_id,filename))


                    dialog.show()
                    self._viewers.append(dialog)

                if filename.endswith('jpg'):
                    os.system("eom %s &" % filename)
#                file_class = load_and_decode_file(value)


    def data(self, QModelIndex, int_role=None):
        try:
            row = self.command_history.history.iloc[QModelIndex.row()]
        except IndexError:
            return
        column = QModelIndex.column()
        if column == 0 and ((int_role is None) or (int_role == QtCore.Qt.InitialSortOrderRole)):
            return row[column]
        if (int_role == QtCore.Qt.DisplayRole) or (int_role is None) or (int_role == QtCore.Qt.InitialSortOrderRole):
            name,function,df_column = columns[column]
            if function:
                return function(row,df_column)
            if column_names[column] == 'received':
                return self.check_command_received(row[1])
            if column_names[column] == 'status':
                return get_send_status(row)
            if column_names[column] == 'response':
                return self.get_response(row)
        if int_role == QtCore.Qt.ToolTipRole:
            if column in [0]:
                return ('%.1f minutes ago' % ((time.time() - row[column]) / 60.))
        # if int_role == QtCore.Qt.FontRole:
        #     if QModelIndex.column() == 1:
        #         if self.files[file_id]['link'] == 'gse_sip':
        #             f = QtGui.QFont()
        #             f.setBold(True)
        #             return f
        #     status = self.files[file_id]
        #     if QModelIndex.column() == 5:
        #         if status['total_packets_received'] != status['packets_expected']:
        #             f = QtGui.QFont()
        #             f.setBold(True)
        #             return f
        # if int_role == QtCore.Qt.ForegroundRole:
        #     status = self.files[file_id]
        #     if status['total_packets_received'] == status['packets_expected']:
        #         return QtGui.QBrush(QtCore.Qt.gray)

        return None

class CommandTableApp(Application):
    config_file = Unicode('', help="Load this config file").tag(config=True)
    config_dir = Unicode(pmc_turbo.utils.configuration.default_ground_config_dir, help="Config file directory").tag(config=True)
    write_default_config = Unicode('', help="Write template config file to this location").tag(config=True)
    classes = List([CommandTableModel])
    mode = Enum(['full', 'piggyback'],default_value='full', help="configuration shortcut to setup for piggyback or full system").tag(config=True)
    aliases = dict(generate_config='CommandTableApp.write_default_config',
                   config_file='CommandTableApp.config_file',
                   mode='CommandTableApp.mode')

    def initialize(self, argv=None):
        actual_argv = argv
        if argv is None:
            actual_argv = sys.argv
        print("initializing CommandTable with arguments:",actual_argv)
        self.parse_command_line(argv)
        if self.write_default_config:
            with open(self.write_default_config, 'w') as fh:
                fh.write(self.generate_config_file())
                self.exit()
        if self.config_file:
            print("**** Ignoring any --mode option ****")
        else:
            if self.mode == 'full':
                print("Using full configuration mode")
                self.config_file = 'default_ground_config.py'
            elif self.mode == 'piggyback':
                print("Using piggyback configuration mode")
                self.config_file = 'piggyback_ground_config.py'
            else:
                raise RuntimeError("Unexpected usage: either specify --config_file or use a valid --mode option")
        print('loading config: ', self.config_dir, self.config_file)
        self.load_config_file(self.config_file, path=self.config_dir)

        print(self.config)
        self.command_table_model = CommandTableModel(config=self.config)

class SortingModel(QtCore.QSortFilterProxyModel):
    def filterAcceptsRow(self, p_int, QModelIndex):
        return True

    def lessThan(self, QModelIndex, QModelIndex_1):
        left = self.sourceModel().data(QModelIndex)
        right = self.sourceModel().data(QModelIndex_1)
        return left < right

    def cell_click(self,QModelIndex):
        mapped_index = self.mapToSource(QModelIndex)
        #print "mapped",QModelIndex.row(),QModelIndex.column(),"to",mapped_index.row(),mapped_index.column()
        self.sourceModel().cell_click(mapped_index)

class MyMainWindow(QtGui.QMainWindow):
    def closeEvent(self, QCloseEvent):
        viewers = self.centralWidget().model().sourceModel()._viewers
        for viewer in viewers:
            viewer.close()
        QtGui.QMainWindow.closeEvent(self,QCloseEvent)

if __name__ == "__main__":
    from IPython import embed
#    from pmc_turbo.utils import log
#    import sys
#    log.setup_stream_handler(log.logging.DEBUG)

    app = QtGui.QApplication([])
    win = MyMainWindow()
    win.setWindowTitle("Command Log Monitor")
    win.resize(1200,800)
    table_view = QtGui.QTableView()

    model_app = CommandTableApp()
    model_app.initialize()
    model = model_app.command_table_model

    model.update()
    sorting_model = SortingModel()
    sorting_model.setSourceModel(model)
    table_view.setModel(sorting_model)
    table_view.setAlternatingRowColors(True)
    table_view.setSortingEnabled(True)
    table_view.sortByColumn(0, QtCore.Qt.DescendingOrder)
    table_view.clicked.connect(sorting_model.cell_click)
    win.setCentralWidget(table_view)
    timer = QtCore.QTimer()
    timer.timeout.connect(model.update)
    timer.start(2000)
    win.show()
#    embed()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
