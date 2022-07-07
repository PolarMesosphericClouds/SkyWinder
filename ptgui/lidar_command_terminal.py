import os

import sys

os.environ['QT_API'] = 'pyqt'
import sip
sip.setapi("QString", 2)
sip.setapi("QVariant", 2)
from PyQt5.QtGui  import *
from PyQt5.QtWidgets import *
# Import the console machinery from ipython
from qtconsole.rich_jupyter_widget import RichJupyterWidget
#from qtconsole.rich_ipython_widget import RichIPythonWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.lib import guisupport

from .command_terminal_demo import QIPythonWidget
from pmc_turbo.ground import commanding
from pmc_turbo.communication.command_table import DESTINATION_LIDAR

from pmc_turbo.utils import log
log.setup_stream_handler()


class ExampleWidget(QWidget):
    """ Main GUI Widget including a button and IPython Console widget inside vertical layout """
    def __init__(self, command_sender_app, parent=None):
        super(ExampleWidget, self).__init__(parent)
        self.setWindowTitle("Command Terminal")
        layout = QVBoxLayout(self)
        self.button = QPushButton('Another widget')
        self.command_sender_app = command_sender_app
        self.cs = self.command_sender_app.command_sender
        ipyConsole = QIPythonWidget(customBanner="Welcome to the embedded ipython console\n")
        layout.addWidget(self.button)
        layout.addWidget(ipyConsole)
        # This allows the variable foo and method print_process_id to be accessed from the ipython console
        def lidar(command):
            return self.cs.send(self.cs.command_manager.send_lidar_command(command=command),destination=DESTINATION_LIDAR)
        ipyConsole.pushVariables({"c":self.cs,"lidar":lidar})
        ipyConsole.pushVariables(dict([(cmd.name,cmd) for cmd in list(self.cs.command_manager._command_dict.values())]))
        ipyConsole.executeCommand("from pmc_turbo.communication.command_table import(DESTINATION_ALL_CAMERAS, "
                                  "DESTINATION_WIDEFIELD_CAMERAS, DESTINATION_NARROWFIELD_CAMERAS, "
                                  "DESTINATION_LIDAR,DESTINATION_SUPER_COMMAND)")

#        ipyConsole.printText("The variable 'foo' and the method 'print_process_id()' are available. Use the 'whos' command for information.")

def print_process_id():
    print('Process ID is:', os.getpid())

def main():
    app  = QApplication([])
    command_sender = commanding.CommandSenderApp()
    command_sender.initialize()
    widget = ExampleWidget(command_sender)
    widget.show()
    app.exec_()

if __name__ == '__main__':
    main()