import glob
import os, sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np

pg.setConfigOptions(imageAxisOrder='row-major')
from pmc_turbo.camera.image_processing import blosc_file



class GUIWrapper():
    def __init__(self, proxy=True, autoupdate=False):
        self.app = QtGui.QApplication([])

        self.window = QtGui.QMainWindow()
        self.window.resize(800, 800)

        self.toolbar = MyToolBar(guiwrapper=self)
        self.window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.toolbar)

        self.status_bar = StatusBar()
        self.window.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.status_bar)

        self.imv = MyImageView(guiwrapper=self)
        self.window.setCentralWidget(self.imv)


class MyImageView(pg.ImageView):
    def __init__(self, guiwrapper, *args, **kwargs):
        super(MyImageView, self).__init__(*args, **kwargs)
        self.guiwrapper = guiwrapper
        self.last_index = 0
        self.autolevels = False
        self.autorange = False
        self.absolute_levels = False
        self.filenames = []

    def update_directory(self, directory):
        self.filenames = glob.glob(directory)
        self.filenames.sort()
        self.guiwrapper.status_bar.update_max_index(len(self.filenames))
        self.guiwrapper.status_bar.update_directory(directory)
        self.update(0)

    def update(self, index):
        if index == -1:
            index = len(self.filenames)
        self.guiwrapper.status_bar.update_index(index)
        filename = self.filenames[index]
        self.last_index = index
        print(filename)
        self.guiwrapper.status_bar.update_filename(filename)
        img, chunk = blosc_file.load_blosc_image(filename)
        self.autolevels = self.guiwrapper.toolbar.autolevel_checkbox.isChecked()
        self.absolute_levels = self.guiwrapper.toolbar.absolute_level_checkbox.isChecked()
        self.autorange = self.guiwrapper.toolbar.autorange_checkbox.isChecked()

        self.setImage(img, autoLevels=self.autolevels, autoRange=self.autorange)
        if self.absolute_levels:
            self.setLevels(0, 16384)

    def keyPressEvent(self, ev):
        if ev.key() == QtCore.Qt.Key_N:
            self.update(self.last_index + 1)
            ev.accept()
        elif ev.key() == QtCore.Qt.Key_P:
            self.update(self.last_index - 1)
            ev.accept()
        elif ev.key() == QtCore.Qt.Key_L:
            self.update(-1)
            ev.accept()

        super(MyImageView, self).keyPressEvent(ev)


class MyToolBar(QtGui.QDockWidget):
    def __init__(self, guiwrapper, *args, **kwargs):
        super(MyToolBar, self).__init__(*args, **kwargs)
        self.guiwrapper = guiwrapper
        self.setWindowTitle("Controls")
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self.setFeatures(QtGui.QDockWidget.DockWidgetVerticalTitleBar)
        self.my_widget = QtGui.QWidget()
        self.setup_layout()
        self.setWidget(self.my_widget)

    def setup_layout(self):
        self.index_edit = QtGui.QLineEdit()
        self.index_edit.setValidator(QtGui.QIntValidator())
        self.index_edit.returnPressed.connect(self.change_index)
        index_edit_label = QtGui.QLabel()
        index_edit_label.setText('Index: ')

        self.directory_edit = QtGui.QLineEdit()
        self.directory_edit.returnPressed.connect(self.change_directory)
        directory_edit_label = QtGui.QLabel()
        directory_edit_label.setText('Directory: ')

        autolevel_label = QtGui.QLabel()
        autolevel_label.setText('Autolevel: ')
        self.autolevel_checkbox = QtGui.QCheckBox()
        self.autolevel_checkbox.setChecked(True)
        self.absolute_level_checkbox = QtGui.QCheckBox()
        self.absolute_level_checkbox.setChecked(False)
        absolute_level_label = QtGui.QLabel()
        absolute_level_label.setText('Absolute level: ')
        autorange_label = QtGui.QLabel()
        autorange_label.setText('Autorange: ')
        self.autorange_checkbox = QtGui.QCheckBox()
        self.autorange_checkbox.setChecked(True)

        # self.autolevel_checkbox.stateChanged.connect(
        #    lambda: self.guiwrapper.autolevel_button_state(self.autolevel_checkbox))
        # Alternate way to do this.

        basic_tab_layout = QtGui.QGridLayout()
        self.my_widget.setLayout(basic_tab_layout)

        basic_tab_layout.addWidget(directory_edit_label, 0, 0)
        basic_tab_layout.addWidget(self.directory_edit, 0, 1)

        basic_tab_layout.addWidget(index_edit_label, 1, 0)
        basic_tab_layout.addWidget(self.index_edit, 1, 1)

        basic_tab_layout.addWidget(autorange_label, 0, 2)
        basic_tab_layout.addWidget(self.autorange_checkbox, 0, 3)
        basic_tab_layout.addWidget(autolevel_label, 1, 2)
        basic_tab_layout.addWidget(self.autolevel_checkbox, 1, 3)
        basic_tab_layout.addWidget(absolute_level_label, 1, 5)
        basic_tab_layout.addWidget(self.absolute_level_checkbox, 1, 6)

    def change_index(self):
        self.guiwrapper.imv.update(int(self.index_edit.text()))
        print(self.index_edit.text())

    def change_directory(self):
        self.guiwrapper.imv.update_directory(str(self.directory_edit.text()))


class StatusBar(QtGui.QDockWidget):
    def __init__(self, *args, **kwargs):
        super(StatusBar, self).__init__(*args, **kwargs)
        self.setWindowTitle("Status")
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self.setFeatures(QtGui.QDockWidget.DockWidgetVerticalTitleBar)
        multiwidget = QtGui.QWidget()
        layout = QtGui.QGridLayout()

        filename_title = QtGui.QLabel()
        layout.addWidget(filename_title, 0, 0)
        filename_title.setText('Filename:')

        self.filename_value = QtGui.QLabel()
        layout.addWidget(self.filename_value, 0, 1)
        self.filename_value.setText('---')

        directory_title = QtGui.QLabel()
        layout.addWidget(directory_title, 0, 2)
        directory_title.setText('Current Directory: ')

        self.directory_value = QtGui.QLabel()
        layout.addWidget(self.directory_value, 0, 3)

        index_title = QtGui.QLabel()
        layout.addWidget(index_title, 1, 0)
        index_title.setText('Current Index: ')

        self.index_value = QtGui.QLabel()
        layout.addWidget(self.index_value, 1, 1)

        max_index_title = QtGui.QLabel()
        layout.addWidget(max_index_title, 1, 2)
        max_index_title.setText('Max Index: ')

        self.max_index_value = QtGui.QLabel()
        layout.addWidget(self.max_index_value, 1, 3)

        multiwidget.setLayout(layout)
        self.setWidget(multiwidget)

    def update_filename(self, filename):
        filename = (filename.split('/')[-1]).split('f')[0][:-1]
        self.filename_value.setText(str(filename))

    def update_directory(self, directory):
        self.directory_value.setText(str(directory))

    def update_index(self, index):
        self.index_value.setText(str(index))

    def update_max_index(self, max_index):
        self.max_index_value.setText(str(max_index))


if __name__ == "__main__":
    gw = GUIWrapper(proxy=True, autoupdate=True)

    gw.window.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
