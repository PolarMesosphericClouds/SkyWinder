import sys
import os
import Pyro4
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from pmc_turbo.camera.pipeline.indexer import MergedIndex
from pmc_turbo.camera.image_processing import blosc_file
import time
import numpy as np

pg.setConfigOptions(imageAxisOrder='row-major')
# import pgview

root_path = '/'
proxy = Pyro4.Proxy('PYRO:controller@0.0.0.0:50001')
Pyro4.config.SERIALIZER = 'pickle'


class GUIWrapper():
    def __init__(self, proxy=True, autoupdate=False):
        self.app = QtGui.QApplication([])

        if proxy:
            self.proxy = Pyro4.Proxy('PYRO:controller@0.0.0.0:50001')
            initial_status = self.proxy.get_pipeline_status()
            current_focus = initial_status['all_camera_parameters']['EFLensFocusCurrent']
            # min_focus = initial_status['all_camera_parameters']['EFLensFocusMin']
            max_focus = initial_status['all_camera_parameters']['EFLensFocusMax']
            exposure = initial_status['all_camera_parameters']['ExposureTimeAbs']
            fstop = initial_status['all_camera_parameters']['EFLensFStopCurrent']
            min_fstop = initial_status['all_camera_parameters']['EFLensFStopMin']
            max_fstop = initial_status['all_camera_parameters']['EFLensFStopMax']
        else:
            self.proxy = None
            current_focus = '---'
            max_focus = '---'
            exposure = '---'
            fstop = '---'
            min_fstop = '---'
            max_fstop = '---'

        self.autoupdate_interval = 3
        self.window = QtGui.QMainWindow()
        self.window.resize(500, 500)

        self.focus_step = int(float(current_focus) / 50.)
        self.exposure_step = int(float(exposure) / 50.)
        self.focus = int(current_focus)
        self.exposure = float(exposure)
        self.fstop = fstop

        self.status_bar = StatusBar(current_focus, max_focus, exposure, fstop, min_fstop, max_fstop)

        self.window.addDockWidget(QtCore.Qt.TopDockWidgetArea, self.status_bar)

        self.toolbar = MyToolBar(guiwrapper=self)
        self.window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.toolbar)

        self.imv = MyImageView(guiwrapper=self, real_time_values=self.status_bar)
        self.window.setCentralWidget(self.imv)

        if autoupdate:
            self.start_autoupdate_thread()

    def increase_focus_button_press(self):
        focus_step = self.focus + self.focus_step
        try:
            if self.proxy:
                self.proxy.set_focus(focus_step)
            self.focus = focus_step
            print('Increased focus to %d' % self.focus)
            self.status_bar.update_focus(self.focus)
        except Exception as e:
            print(e)

    def decrease_focus_button_press(self):
        focus_step = self.focus - self.focus_step
        try:
            if self.proxy:
                self.proxy.set_focus(focus_step)
            self.focus = focus_step
            print('Decreased focus to %d' % self.focus)
            self.status_bar.update_focus(self.focus)
        except Exception as e:
            print(e)

    def increase_exposure_button_press(self):
        exposure_us = self.exposure + self.exposure_step
        try:
            if self.proxy:
                self.proxy.set_exposure(exposure_us)
            self.exposure = exposure_us
            print('Increased exposure to %d' % self.exposure)
            self.status_bar.update_exposure(self.exposure)
        except Exception as e:
            print(e)

    def decrease_exposure_button_press(self):
        exposure_us = self.exposure - self.exposure_step
        try:
            if self.proxy:
                self.proxy.set_exposure(exposure_us)
            self.exposure = exposure_us
            print('Increased exposure to %d' % self.exposure)
            self.status_bar.update_exposure(self.exposure)
        except Exception as e:
            print(e)

    def restore_default_button_press(self):
        try:
            if self.proxy:
                self.proxy.set_exposure(1000)
            self.exposure = 1000
            print('Exposure set to %d' % self.exposure)
            self.status_bar.update_exposure(self.exposure)
            if self.proxy:
                self.proxy.set_focus(2050)
            self.focus = 2050
            print('Focus set to %d' % self.focus)
            self.status_bar.update_focus(self.focus)
        except Exception as e:
            print(e)

    def change_focus_step(self, focus_step):
        focus_step = int(focus_step)
        self.focus_step = focus_step
        print('Changed focus step to %d' % self.focus_step)

    def change_exposure_step(self, exposure_step):
        exposure_step = int(exposure_step)
        self.exposure_step = exposure_step
        print('Changed exposure step to %d' % self.exposure_step)

    def change_focus(self, focus):
        focus = int(focus)
        try:
            if self.proxy:
                self.proxy.set_focus(focus)
            self.focus = focus
            print('Changed focus to %d' % self.focus)
            self.status_bar.update_focus(self.focus)
        except Exception as e:
            print(e)

    def change_fstop(self, fstop):
        try:
            fstop = float(fstop)
            if self.proxy:
                self.proxy.send_arbitrary_camera_command('EFLensFStopCurrent', fstop)
            initial_status = self.proxy.get_pipeline_status()
            current_fstop = initial_status['all_camera_parameters']['EFLensFStopCurrent']
            self.fstop = current_fstop
            print('Changed fstop to %s' % self.fstop)
            self.status_bar.update_fstop(self.fstop)
        except Exception as e:
            print(e)

    def change_exposure(self, exposure):
        exposure = int(exposure)
        try:
            if self.proxy:
                self.proxy.set_exposure(exposure)
            self.exposure = exposure
            print('Changed exposure to %d' % self.exposure)
            self.status_bar.update_exposure(self.exposure)
        except Exception as e:
            print(e)

    def autoupdate(self):
        while True:
            if self.toolbar.autoupdate_checkbox.isChecked():
                self.imv.update(-1)
            time.sleep(self.autoupdate_interval)

    def start_autoupdate_thread(self):
        self.update_thread = threading.Thread(target=self.autoupdate)
        self.update_thread.daemon = True
        print('autoupdate_started')
        self.update_thread.start()


class MyImageView(pg.ImageView):
    def __init__(self, guiwrapper, real_time_values=None, *args, **kwargs):
        self.root_path = '/'
        print(self.root_path)
        super(MyImageView, self).__init__(*args, **kwargs)
        self.mi = MergedIndex('*', data_dirs=[os.path.join(self.root_path, ('data%d' % k)) for k in range(1, 5)])
        self.last_index = 0
        self.status_bar = real_time_values
        self.guiwrapper = guiwrapper
        self.autolevels = True
        self.autorange = False
        self.absolute_levels = False
        self.update(-1)

    def update(self, index):
        self.mi.update()
        if index == -1:
            index = self.mi.df.index.max()
        try:
            latest = self.mi.df.iloc[index]
        except (IndexError, KeyError):
            print("invalid index", index)
            return
        if index == self.last_index:
            return
        self.last_index = index
        filename = latest['filename']
        filename = os.path.join(self.root_path, filename[1:])
        print(filename)
        if self.status_bar:
            self.status_bar.update_filename(filename)
        img, chunk = blosc_file.load_blosc_image(filename)
        if self.guiwrapper:
            self.autolevels = self.guiwrapper.toolbar.autolevel_checkbox.isChecked()
            self.absolute_levels = self.guiwrapper.toolbar.absolute_level_checkbox.isChecked()
            self.autorange = self.guiwrapper.toolbar.autorange_checkbox.isChecked()

        # m = np.ma.masked_where(img > 16383, img)
        # print m.mask

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
        print(self.guiwrapper)
        self.tab_widget = QtGui.QTabWidget()
        self.setWidget(self.tab_widget)
        self.setup_layout()

    def setup_layout(self):
        increase_focus = QtGui.QPushButton("Increase Focus", self.guiwrapper.window)
        decrease_focus = QtGui.QPushButton("Decrease Focus", self.guiwrapper.window)
        increase_exposure_time = QtGui.QPushButton("Increase Exposure Time", self.guiwrapper.window)
        decrease_exposure_time = QtGui.QPushButton("Decrease Exposure Time", self.guiwrapper.window)
        restore_default = QtGui.QPushButton("Restore Default", self.guiwrapper.window)

        increase_focus.clicked.connect(self.guiwrapper.increase_focus_button_press)
        decrease_focus.clicked.connect(self.guiwrapper.decrease_focus_button_press)
        increase_exposure_time.clicked.connect(self.guiwrapper.increase_exposure_button_press)
        decrease_exposure_time.clicked.connect(self.guiwrapper.decrease_exposure_button_press)
        restore_default.clicked.connect(self.guiwrapper.restore_default_button_press)

        self.focus_step_edit = QtGui.QLineEdit()
        self.focus_step_edit.setValidator(QtGui.QIntValidator())
        self.focus_step_edit.returnPressed.connect(self.change_focus_step)

        self.exposure_step_edit = QtGui.QLineEdit()
        self.exposure_step_edit.setValidator(QtGui.QIntValidator())
        self.exposure_step_edit.returnPressed.connect(self.change_exposure_step)

        focus_step_label = QtGui.QLabel()
        focus_step_label.setText('Focus Step: ')
        exposure_step_label = QtGui.QLabel()
        exposure_step_label.setText('Exposure Step: ')

        self.focus_edit = QtGui.QLineEdit()
        self.focus_edit.setValidator(QtGui.QIntValidator())
        self.focus_edit.returnPressed.connect(self.change_focus)
        self.exposure_edit = QtGui.QLineEdit()
        self.exposure_edit.setValidator(QtGui.QIntValidator())
        self.exposure_edit.returnPressed.connect(self.change_exposure)
        self.fstop_edit = QtGui.QLineEdit()
        self.fstop_edit.setValidator(QtGui.QDoubleValidator())
        self.fstop_edit.returnPressed.connect(self.change_fstop)

        focus_label = QtGui.QLabel()
        focus_label.setText('Set Focus: ')

        exposure_label = QtGui.QLabel()
        exposure_label.setText('Set Exposure: ')

        fstop_label = QtGui.QLabel()
        fstop_label.setText('Set FStop: ')

        autoupdate_label = QtGui.QLabel()
        autoupdate_label.setText('Autoupdate: ')
        autolevel_label = QtGui.QLabel()
        autolevel_label.setText('Autolevel: ')
        self.autoupdate_checkbox = QtGui.QCheckBox()
        self.autoupdate_checkbox.setChecked(True)
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

        basic_tab_widget = QtGui.QWidget()
        basic_tab_layout = QtGui.QGridLayout()
        basic_tab_widget.setLayout(basic_tab_layout)

        basic_tab_layout.addWidget(increase_exposure_time, 0, 0)
        basic_tab_layout.addWidget(decrease_exposure_time, 1, 0)

        basic_tab_layout.addWidget(autoupdate_label, 0, 1)
        basic_tab_layout.addWidget(self.autoupdate_checkbox, 0, 2)
        basic_tab_layout.addWidget(autorange_label, 1, 1)
        basic_tab_layout.addWidget(self.autorange_checkbox, 1, 2)
        basic_tab_layout.addWidget(autolevel_label, 0, 3)
        basic_tab_layout.addWidget(self.autolevel_checkbox, 0, 4)
        basic_tab_layout.addWidget(absolute_level_label, 1, 3)
        basic_tab_layout.addWidget(self.absolute_level_checkbox, 1, 4)

        basic_tab_layout.addWidget(restore_default, 1,5)

        advanced_tab_widget = QtGui.QWidget()
        advanced_tab_layout = QtGui.QGridLayout()
        advanced_tab_widget.setLayout(advanced_tab_layout)
        advanced_tab_layout.addWidget(focus_label, 0, 0)
        advanced_tab_layout.addWidget(self.focus_edit, 0, 1)
        advanced_tab_layout.addWidget(exposure_label, 1, 0)
        advanced_tab_layout.addWidget(self.exposure_edit, 1, 1)
        advanced_tab_layout.addWidget(increase_focus, 0, 2)
        advanced_tab_layout.addWidget(decrease_focus, 1, 2)
        advanced_tab_layout.addWidget(exposure_step_label, 0, 3)
        advanced_tab_layout.addWidget(self.exposure_step_edit, 0, 4)
        advanced_tab_layout.addWidget(focus_step_label, 1, 3)
        advanced_tab_layout.addWidget(self.focus_step_edit, 1, 4)
        advanced_tab_layout.addWidget(fstop_label, 1, 5)
        advanced_tab_layout.addWidget(self.fstop_edit, 1, 6)

        self.tab1 = basic_tab_widget
        self.tab2 = advanced_tab_widget
        self.tab_widget.addTab(self.tab1, "Basic")
        self.tab_widget.addTab(self.tab2, "Advanced")

    def change_focus_step(self):
        self.guiwrapper.change_focus_step(self.focus_step_edit.text())
        print(self.focus_step_edit.text())

    def change_exposure_step(self):
        self.guiwrapper.change_exposure_step(self.exposure_step_edit.text())
        print(self.exposure_step_edit.text())

    def change_focus(self):
        self.guiwrapper.change_focus(self.focus_edit.text())
        print(self.focus_edit.text())

    def change_exposure(self):
        self.guiwrapper.change_exposure(self.exposure_edit.text())
        print(self.exposure_edit.text())

    def change_fstop(self):
        self.guiwrapper.change_fstop(self.fstop_edit.text())
        print(self.fstop_edit.text())


class StatusBar(QtGui.QDockWidget):
    def __init__(self, current_focus, max_focus, exposure, fstop, min_fstop, max_fstop, *args, **kwargs):
        # super(RealTimeValues,self).__init__("Status", *args,**kwargs)
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

        focus_title = QtGui.QLabel()
        layout.addWidget(focus_title, 0, 2)
        focus_title.setText('Focus (max %s):' % max_focus)

        exposure_title = QtGui.QLabel()
        layout.addWidget(exposure_title, 1, 0)
        exposure_title.setText('Exposure (microseconds): ')

        self.focus_value = QtGui.QLabel()
        layout.addWidget(self.focus_value, 0, 3)

        self.exposure_value = QtGui.QLabel()
        layout.addWidget(self.exposure_value, 1, 1)

        fstop_title = QtGui.QLabel()
        layout.addWidget(fstop_title, 1, 2)
        fstop_title.setText('Aperture (%s - %s): ' % (min_fstop, max_fstop))

        self.fstop_value = QtGui.QLabel()
        layout.addWidget(self.fstop_value, 1, 3)
        self.fstop_value.setText('1.24')

        multiwidget.setLayout(layout)
        self.setWidget(multiwidget)

        self.update_focus(current_focus)
        self.update_exposure(exposure)
        self.update_fstop(fstop)

    def update_filename(self, filename):
        filename = (filename.split('/')[-1]).split('f')[0][:-1]
        self.filename_value.setText(str(filename))

    def update_focus(self, focus):
        self.focus_value.setText(str(focus))

    def update_exposure(self, exposure):
        self.exposure_value.setText(str(exposure))

    def update_fstop(self, fstop):
        self.fstop_value.setText(str(fstop))


if __name__ == "__main__":
    gw = GUIWrapper(proxy=True, autoupdate=True)

    gw.window.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
