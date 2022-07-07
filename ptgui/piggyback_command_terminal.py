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

from pmc_turbo.ground import commanding

from pmc_turbo.utils import log
log.setup_stream_handler()

class QIPythonWidget(RichJupyterWidget):
    """ Convenience class for a live IPython console widget. We can replace the standard banner using the customBanner argument"""
    def __init__(self,customBanner=None,*args,**kwargs):
        if customBanner is not None:
            self.banner=customBanner
        super(QIPythonWidget, self).__init__(*args,**kwargs)
        self.kernel_manager = kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel()
        kernel_manager.kernel.gui = 'qt4'
        self.kernel_client = kernel_client = self._kernel_manager.client()
        kernel_client.start_channels()

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()
            guisupport.get_app_qt4().exit()
        self.exit_requested.connect(stop)

    def pushVariables(self,variableDict):
        """ Given a dictionary containing name / value pairs, push those variables to the IPython console widget """
        self.kernel_manager.kernel.shell.push(variableDict)
    def clearTerminal(self):
        """ Clears the terminal """
        self._control.clear()
    def printText(self,text):
        """ Prints some plain text to the console """
        self._append_plain_text(text)
    def executeCommand(self,command):
        """ Execute a command in the frame of the console widget """
        self._execute(command,False)


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
        ipyConsole.pushVariables({"foo":43,"print_process_id":print_process_id, "c":self.cs})
        ipyConsole.pushVariables(dict([(cmd.name,cmd) for cmd in list(self.cs.command_manager._command_dict.values())]))
        ipyConsole.executeCommand("from pmc_turbo.communication.command_table import(DESTINATION_ALL_CAMERAS, "
                                  "DESTINATION_WIDEFIELD_CAMERAS, DESTINATION_NARROWFIELD_CAMERAS, "
                                  "DESTINATION_LIDAR,DESTINATION_SUPER_COMMAND)")

        ipyConsole.printText("The variable 'foo' and the method 'print_process_id()' are available. Use the 'whos' command for information.")

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