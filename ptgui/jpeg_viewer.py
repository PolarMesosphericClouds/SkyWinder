import glob
import os, sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import time
import argparse

from pmc_turbo.camera.pipeline.indexer import MergedIndex
from pmc_turbo.communication.file_format_classes import load_and_decode_file, JPEGFile, DEFAULT_REQUEST_ID
from pmc_turbo.camera.pycamera import dtypes


def get_roi_coordinates(roi_pos, roi_size, scale_by, row_offset, column_offset, portrait_mode):
    if portrait_mode:
        x_idx = 1
        y_idx = 0
    else:
        x_idx = 0
        y_idx = 1
    xmin = np.floor(roi_pos[x_idx] / scale_by) + column_offset
    xmax = np.ceil((roi_pos[x_idx] + roi_size[x_idx]) / scale_by) + column_offset
    ymin = np.floor(roi_pos[y_idx] / scale_by) + row_offset
    ymax = np.ceil((roi_pos[y_idx] + roi_size[y_idx]) / scale_by) + row_offset
    return xmin, xmax, ymin, ymax


class MyImageView(pg.ImageView):
    def __init__(self, camera_id, autoupdate, infobar, commandbar, window, portrait_mode, data_dir, *args,
                 **kwargs):
        # GroundConfiguration.__init__(**kwargs)
        super(MyImageView, self).__init__(*args, **kwargs)
        print('MyImageView started with camera id: %s, autoupdate %d, portrait mode %d' % (
            str(camera_id), autoupdate, portrait_mode))
        self.window = window
        self.run_autoupdate = False
        self.portrait_mode = portrait_mode
        self.camera_id = camera_id
        self.mi = MergedIndex('*', data_dirs=[data_dir], index_filename='file_index.csv', sort_on=None)
        self.last_index = 0
        self.scale_by = 1
        self.prev_shape = None
        self.hist = self.getHistogramWidget()

        self.selection_roi = pg.RectROI((0, 0), size=(20, 20), scaleSnap=True, translateSnap=True)
        self.selection_roi.sigRegionChangeFinished.connect(self.roi_update)

        self.addItem(self.selection_roi)

        self.infobar = infobar
        self.commandbar = commandbar

        self.update(-1)

        self.autoupdate_interval = 1
        if autoupdate:
            self.infobar.autoupdate_checkbox.setChecked(True)
            # Mark autoupdate box checked.

    def roi_update(self):
        xmin, xmax, ymin, ymax = get_roi_coordinates(self.selection_roi.pos(), self.selection_roi.size(), self.scale_by,
                                                     self.row_offset, self.column_offset, self.portrait_mode)
        if self.portrait_mode:
            x_idx = 1
            y_idx = 0
        else:
            x_idx = 0
            y_idx = 1
        self.infobar.roi_widget.roi_x.set_value('%.0f:%.0f' % (
            self.selection_roi.pos()[x_idx], self.selection_roi.pos()[x_idx] + self.selection_roi.size()[x_idx]))
        self.infobar.roi_widget.roi_y.set_value('%.0f:%.0f' % (
            self.selection_roi.pos()[y_idx], self.selection_roi.pos()[y_idx] + self.selection_roi.size()[y_idx]))
        self.infobar.roi_widget.roi_column_offset.set_value('%.0f' % xmin)
        self.infobar.roi_widget.roi_row_offset.set_value('%.0f' % ymin)
        self.infobar.roi_widget.roi_num_columns.set_value('%.0f' % (xmax - xmin))
        self.infobar.roi_widget.roi_num_rows.set_value('%.0f' % (ymax - ymin))
        self.commandbar.set_text(
            'request_specific_images(timestamp=%f, row_offset=%d, column_offset=%d, num_rows=%d, num_columns=%d, num_images=1, scale_by=1, quality=75, step=-1)'
            % (self.timestamp, ymin, xmin, (ymax - ymin), (xmax - xmin)))
        self.commandbar.dynamic_command.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

    def update(self, index=-1):
        self.mi.update()
        if self.camera_id:
            df = self.mi.df[self.mi.df.camera_id == self.camera_id]
        else:
            df = self.mi.df
        df = df[df.file_type == JPEGFile.file_type].reset_index(drop=True)
        if index == -1:
            index = df.index.max()
        if index > df.index.max():
            print('Index larger than max index; going to max index instead.')
            index = df.index.max()
        try:
            latest = df.iloc[df.index.get_loc(index, method='pad')]
            print(list(latest.keys()))
        except (IndexError, KeyError) as e:
            print("invalid index", index, e)
            return
        if index == self.last_index:
            return
        self.last_index = index
        filename = latest['filename']
        # Trust that we have the correct directory structure
        channel, files_fn, image_fn = filename.split('/')[-3:]
        filename = os.path.join(data_dir, channel, files_fn, image_fn)
        self.window.setWindowTitle(filename)
        print(filename)
        file_size = os.path.getsize(filename)
        image_file = load_and_decode_file(filename)
        self.infobar.update(image_file, latest, file_size, index, df.index.max())
        self.timestamp = image_file.frame_timestamp_ns / 1e9
        self.scale_by = image_file.scale_by
        self.row_offset = image_file.row_offset
        self.column_offset = image_file.column_offset
        image_data = image_file.image_array() / image_file.pixel_scale + image_file.pixel_offset
        self.setImage(image_data, autoLevels=self.infobar.autolevel_checkbox.isChecked(),
                      autoRange=self.infobar.autorange_checkbox.isChecked())

        if (self.selection_roi.pos()[0] < 0) or (self.selection_roi.pos()[1] < 0):
            self.selection_roi.setPos((0, 0))

        xmax = self.selection_roi.pos()[0] + self.selection_roi.size()[0]
        ymax = self.selection_roi.pos()[1] + self.selection_roi.size()[1]

        if not self.portrait_mode:
            xlim = image_data.shape[1]
            ylim = image_data.shape[0]
        else:
            xlim = image_data.shape[0]
            ylim = image_data.shape[1]

        if image_data.shape != self.prev_shape:
            self.selection_roi.setSize([10, 10])
            self.selection_roi.setPos([0, 0, ])
            self.prev_shape = image_data.shape
        else:
            if xmax > xlim:
                self.selection_roi.setSize(
                    [xlim - self.selection_roi.pos()[0], self.selection_roi.size()[1]])

            if ymax > ylim:
                self.selection_roi.setSize(
                    [self.selection_roi.size()[0], ylim - self.selection_roi.pos()[1]])
        self.roi_update()

        max_y = np.max(self.hist.plot.getData()[1])
        x = [image_file.percentile_0,
             image_file.percentile_1,
             image_file.percentile_10,
             image_file.percentile_20,
             image_file.percentile_30,
             image_file.percentile_40,
             image_file.percentile_50,
             image_file.percentile_60,
             image_file.percentile_70,
             image_file.percentile_80,
             image_file.percentile_90,
             image_file.percentile_99,
             image_file.percentile_100]
        # y1 = [max_y]* len(x)
        y = np.zeros(len(x))
        self.hist.plot.scatter.setData(x, y, symbol=('o'), brush='r')
        self.hist.plot.scatter.show()

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

            # super(MyImageView, self).keyPressEvent(ev)

    def mouseMoved(self, evt):
        vb = self.getView()
        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        if self.imageItem.sceneBoundingRect().contains(pos):
            mousePoint = vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())
            self.infobar.x.setText('%.0f' % mousePoint.x())
            self.infobar.y.setText('%.0f' % mousePoint.y())

    def update_from_index_edit(self):
        idx = int(self.infobar.go_to_index_edit.text())
        self.update(idx)

    def run_auto_update(self):
        if self.infobar.autoupdate_checkbox.isChecked():
            self.update(-1)


class GroupWidget(QtGui.QWidget):
    def __init__(self, fontsize, labels, *args, **kwargs):
        super(GroupWidget, self).__init__(*args, **kwargs)
        self.layout = QtGui.QGridLayout()
        for i, label in enumerate(labels):
            item = MyItem(fontsize, label)
            setattr(self, str(label), item)
            self.layout.addWidget(item.label, i, 0)
            self.layout.addWidget(item.value, i, 1)
        self.setLayout(self.layout)


class MyItem():
    def __init__(self, fontsize, label):
        self.value = QtGui.QLabel('---')
        self.label = QtGui.QLabel(str(label))
        font = self.value.font()
        font.setPointSize(fontsize)
        self.value.setFont(font)
        self.value.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.label.setFont(font)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_tooltip(self, value):
        self.value.setToolTip(value)


class InfoBar(QtGui.QDockWidget):
    def __init__(self, fontsize, titlebar, *args, **kwargs):
        super(InfoBar, self).__init__(*args, **kwargs)
        self.image_viewer = None
        self.titlebar = titlebar
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self.setTitleBarWidget(QtGui.QWidget(None))
        mywidget = QtGui.QWidget()
        self.vlayout = QtGui.QVBoxLayout()

        time_labels = ['frame_stamp', 'write_stamp', 'first_stamp', 'last_stamp', ]
        # 'file_write_stamp']
        self.time_widget = GroupWidget(fontsize, time_labels)

        camera_labels = ['file_id', 'camera_id', 'frame_id', 'frame_status', 'focus_step',
                         'aperture_stop', 'exposure_us', 'file_index', 'acquisition_count',
                         'gain_db', 'focal_length_mm', 'lens_error']
        self.camera_widget = GroupWidget(fontsize, camera_labels)

        image_labels = ['row_offset', 'column_offset', 'num_rows', 'num_columns',
                        'scale_by',
                        'pixel_offset', 'pixel_scale', 'quality', 'file_size',
                        'request_id', 'percentile']
        self.image_widget = GroupWidget(fontsize, image_labels)

        roi_labels = ['roi_x', 'roi_y', 'roi_row_offset', 'roi_column_offset', 'roi_num_rows',
                      'roi_num_columns']
        self.roi_widget = GroupWidget(fontsize, roi_labels)

        index_labels = ['ground_index', 'total_index', 'go_to_index', 'autoupdate', 'autorange', 'autolevel']
        self.index_widget = GroupWidget(fontsize, index_labels)

        self.go_to_index_edit = QtGui.QLineEdit()
        self.go_to_index_edit.setValidator(QtGui.QIntValidator())
        f = self.go_to_index_edit.font()
        f.setPointSize(fontsize)
        self.go_to_index_edit.setFont(f)
        self.go_to_index_edit.setFixedWidth(25)
        self.go_to_index_edit.setFixedHeight(13)
        self.go_to_index_edit.returnPressed.connect(self.update_from_index_edit)
        self.index_widget.layout.addWidget(self.go_to_index_edit, 2, 1)

        self.autoupdate_checkbox = QtGui.QCheckBox()

        self.autorange_checkbox = QtGui.QCheckBox()
        self.autorange_checkbox.setChecked(True)
        self.autolevel_checkbox = QtGui.QCheckBox()
        self.autolevel_checkbox.setChecked(True)
        self.index_widget.layout.addWidget(self.autoupdate_checkbox, 3, 1)
        self.index_widget.layout.addWidget(self.autorange_checkbox, 4, 1)
        self.index_widget.layout.addWidget(self.autolevel_checkbox, 5, 1)

        vertical_spacer = QtGui.QSpacerItem(10, 10, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)

        self.vlayout.addWidget(self.roi_widget)
        self.vlayout.addWidget(self.time_widget)
        self.vlayout.addWidget(self.camera_widget)
        self.vlayout.addWidget(self.image_widget)
        self.vlayout.addWidget(self.index_widget)
        self.vlayout.addItem(vertical_spacer)
        mywidget.setLayout(self.vlayout)
        self.setWidget(mywidget)

    def update(self, jpeg_file, data_row, file_size, index, max_index):
        self.camera_widget.frame_status.set_value(str(jpeg_file.frame_status))
        self.camera_widget.frame_id.set_value(str(jpeg_file.frame_id))
        time_s = jpeg_file.frame_timestamp_ns / 1e9
        # self.time_widget.frame_stamp.set_value('%.0f' % time_s)
        # self.time_widget.frame_stamp.set_tooltip(time.strftime("%Y.%m.%d_%H:%M:%S", time.localtime(time_s)))
        self.time_widget.frame_stamp.set_value(time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(time_s)))
        delta_t_s = time.time() - time_s
        m, s = divmod(delta_t_s, 60)
        h, m = divmod(m, 60)
        self.time_widget.frame_stamp.set_tooltip(
            'Image taken %d hours, %d minutes, %d seconds ago' % (h, m, s))
        if int(jpeg_file.focal_length_mm) == 50:
            # Focus step is a scale of 1-1000. The max focus of 135mm lens is around little over 1035, so this is close
            # enough for quick intuition, but the max focus step of 50 mm is about 4940.
            self.camera_widget.focus_step.set_value(str(int(jpeg_file.focus_step * 4940. / 1000)))
        else:
            self.camera_widget.focus_step.set_value(str(int(jpeg_file.focus_step * 1035. / 1000)))

        self.camera_widget.aperture_stop.set_value(
            "%.2f" % (dtypes.decode_aperture_chunk_data(jpeg_file.aperture_stop)))
        self.camera_widget.exposure_us.set_value(str(jpeg_file.exposure_us))
        self.camera_widget.file_index.set_value(str(jpeg_file.file_index))
        # self.time_widget.write_stamp.set_value('%.0f' % jpeg_file.write_timestamp)
        # self.time_widget.write_stamp.set_tooltip(
        #     time.strftime("%Y.%m.%d_%H:%M:%S", time.localtime(jpeg_file.write_timestamp)))
        self.time_widget.write_stamp.set_value(
            time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(jpeg_file.write_timestamp)))

        self.camera_widget.acquisition_count.set_value(str(jpeg_file.acquisition_count))
        self.camera_widget.gain_db.set_value(str(jpeg_file.gain_db))
        self.camera_widget.focal_length_mm.set_value(str(jpeg_file.focal_length_mm))

        self.image_widget.row_offset.set_value(str(jpeg_file.row_offset))
        self.image_widget.column_offset.set_value(str(jpeg_file.column_offset))
        self.image_widget.num_rows.set_value(str(jpeg_file.num_rows))
        self.image_widget.num_columns.set_value(str(jpeg_file.num_columns))

        self.image_widget.scale_by.set_value(str(jpeg_file.scale_by))
        self.image_widget.pixel_offset.set_value(str(jpeg_file.pixel_offset))
        self.image_widget.pixel_scale.set_value('%.3f' % jpeg_file.pixel_scale)
        self.image_widget.quality.set_value(str(jpeg_file.quality))
        self.image_widget.file_size.set_value(str(file_size))
        if int(jpeg_file.request_id) == DEFAULT_REQUEST_ID:
            self.image_widget.request_id.set_value('default')
        else:
            self.image_widget.request_id.set_value(str(jpeg_file.request_id))
        self.image_widget.percentile.set_tooltip(
            '0: %0.f\n1: %0.f\n10: %0.f\n20: %0.f\n30: %0.f\n40: %0.f\n50: %0.f\n60: %0.f\n70: %0.f\n80: %0.f\n90: %0.f\n99: %0.f\n100: %0.f\n' %
            (jpeg_file.percentile_0,
             jpeg_file.percentile_1,
             jpeg_file.percentile_10,
             jpeg_file.percentile_20,
             jpeg_file.percentile_30,
             jpeg_file.percentile_40,
             jpeg_file.percentile_50,
             jpeg_file.percentile_60,
             jpeg_file.percentile_70,
             jpeg_file.percentile_80,
             jpeg_file.percentile_90,
             jpeg_file.percentile_99,
             jpeg_file.percentile_100))

        # self.time_widget.first_stamp.set_value('%.0f' % data_row['first_timestamp'])
        # self.time_widget.first_stamp.set_tooltip(
        #     time.strftime("%Y.%m.%d_%H:%M:%S", time.localtime(float(data_row['first_timestamp']))))
        self.time_widget.first_stamp.set_value(
            time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(float(data_row['first_timestamp']))))
        # self.time_widget.last_stamp.set_value('%.0f' % data_row['last_timestamp'])
        # self.time_widget.last_stamp.set_tooltip(
        #     time.strftime("%Y.%m.%d_%H:%M:%S", time.localtime(float(data_row['last_timestamp']))))
        self.time_widget.last_stamp.set_value(
            time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(float(data_row['last_timestamp']))))
        # self.time_widget.file_write_stamp.set_value('%.0f' % data_row['file_write_timestamp'])
        # self.time_widget.file_write_stamp.set_tooltip(
        #     time.strftime("%Y.%m.%d_%H:%M:%S", time.localtime(float(data_row['file_write_timestamp']))))

        # self.filename_label.setText(str(data_row['filename']))

        self.camera_widget.file_id.set_value(str(data_row['file_id']))
        self.camera_widget.camera_id.set_value(str(data_row['camera_id']))
        self.titlebar.title.setText('Camera %s' % str(data_row['camera_id']))

        lens_status_dict = dtypes.decode_lens_status_chunk_data(jpeg_file.lens_status)

        self.camera_widget.lens_error.set_value(str(lens_status_dict['error']))
        self.camera_widget.lens_error.set_tooltip(
            "Lens error: %s\nAuto Focus: %s\nLens Attached: %s\nLast Error: %s\nLast Error Msg: %s" %
            (str(lens_status_dict['error']),
             str(lens_status_dict['auto_focus']),
             str(lens_status_dict['lens_attached']),
             str(lens_status_dict['last_error']),
             str(lens_status_dict['last_error_message'])
             ))

        self.index_widget.ground_index.set_value(str(index))
        self.index_widget.total_index.set_value(str(max_index))

    def update_from_index_edit(self):
        if self.image_viewer:
            self.image_viewer.update_from_index_edit()
        else:
            print('No image viewer associated with this InfoBar (expected upon startup)')


class CommandBar(QtGui.QDockWidget):
    def __init__(self, fontsize, compact, *args, **kwargs):
        super(CommandBar, self).__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self.setTitleBarWidget(QtGui.QWidget(None))
        self.compact = compact
        mywidget = QtGui.QWidget()
        layout = QtGui.QHBoxLayout()
        label = QtGui.QLabel('Command:')

        self.dynamic_command = QtGui.QLabel('---')
        dfont = self.dynamic_command.font()
        dfont.setPointSize(fontsize)
        label.setFont(dfont)
        dfont.setBold(True)
        self.dynamic_command.setFont(dfont)
        if compact:
            self.dynamic_command.setWordWrap(True)
            self.dynamic_command.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Expanding)
        layout.addWidget(label)
        layout.addWidget(self.dynamic_command)
        mywidget.setLayout(layout)
        self.setWidget(mywidget)

    def set_text(self, text):
        self.dynamic_command.setText(text)


class TitleBar(QtGui.QDockWidget):
    def __init__(self, title, fontsize, *args, **kwargs):
        super(TitleBar, self).__init__(*args, **kwargs)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)
        self.setTitleBarWidget(QtGui.QWidget(None))
        mywidget = QtGui.QWidget()
        layout = QtGui.QHBoxLayout()

        self.title = QtGui.QLabel(title)
        dfont = self.title.font()
        dfont.setPointSize(fontsize + 3)
        dfont.setBold(True)
        self.title.setFont(dfont)

        horizontal_spacer = QtGui.QSpacerItem(5, 5, hPolicy=QtGui.QSizePolicy.Expanding,
                                              vPolicy=QtGui.QSizePolicy.Minimum)
        layout.addItem(horizontal_spacer)
        layout.addWidget(self.title)

        layout.setSpacing(1)
        layout.setContentsMargins(0, 1, 1, 1)
        mywidget.setLayout(layout)
        self.setWidget(mywidget)


if __name__ == "__main__":
    from pmc_turbo.utils import log
    import sys

    parser = argparse.ArgumentParser(description='Set pmc_viewer behavior.')
    parser.add_argument('--camera_id', '-id', nargs=1, default=0,
                        help='Select specific camera to view. 0 does not specify any camera.')
    parser.add_argument('--autoupdate', '-a', action='store_true',
                        help="Starts pmc_viewer with autoupdate on (can be turned off with checkbox. Default is autoupdate off.")
    parser.add_argument('--compact', '-c', action='store_true',
                        help="Starts pmc_viewer with a more compact configuration to fit multiple instances on one screen. Default is fullsize.")
    parser.add_argument('--portrait', '-p', action='store_true',
                        help='Displays image in portrait mode. Default is landscape.')
    parser.add_argument('--data_dir', '-dd', nargs=1, default='/data/gse_data/',
                        help='Root data directory to search for images. Use /data/piggyback_gse_data for piggyback on clouds')
    args = parser.parse_args()

    camera_id = 0
    autoupdate = False
    portrait_mode = False
    compact = False
    if args.camera_id:
        print(args.camera_id[0])
        camera_id = int(args.camera_id[0])
    if args.autoupdate:
        autoupdate = args.autoupdate
    if args.portrait:
        portrait_mode = args.portrait
    if args.compact:
        compact = True
    data_dir = args.data_dir[0]
    if not portrait_mode:
        pg.setConfigOptions(imageAxisOrder='row-major')
    else:
        pg.setConfigOptions(imageAxisOrder='col-major')
    log.setup_stream_handler(log.logging.DEBUG)
    app = QtGui.QApplication([])
    dw = QtGui.QDesktopWidget()

    geom = dw.availableGeometry()
    if not compact:
        fontsize = 10
    else:
        fontsize = 6

    tb = TitleBar(fontsize=fontsize + 3, title='')
    iw = InfoBar(fontsize, tb)
    cb = CommandBar(fontsize, compact)
    win = QtGui.QMainWindow()

    imv = MyImageView(camera_id, autoupdate, iw, cb, win, portrait_mode=portrait_mode, data_dir=data_dir)
    if compact:
        # Shrinking the histogram
        imv.ui.histogram.setMinimumWidth(85)
        imv.ui.histogram.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Expanding)
        imv.ui.roiBtn.setMaximumWidth(42)
        imv.ui.roiBtn.sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        imv.ui.menuBtn.setMaximumWidth(42)
        imv.ui.menuBtn.sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        # Remove spacing between separate grid layouts.
        iw.vlayout.setSpacing(0)
        iw.vlayout.setContentsMargins(0, 0, 0, 0)

        iw.roi_widget.layout.setSpacing(1)
        iw.roi_widget.layout.setContentsMargins(0, 1, 0, 1)

        iw.time_widget.layout.setSpacing(1)
        iw.time_widget.layout.setContentsMargins(0, 1, 0, 1)

        iw.camera_widget.layout.setSpacing(1)
        iw.camera_widget.layout.setContentsMargins(0, 1, 0, 1)

        iw.image_widget.layout.setSpacing(1)
        iw.image_widget.layout.setContentsMargins(0, 1, 0, 1)

        iw.index_widget.layout.setSpacing(1)
        iw.index_widget.layout.setContentsMargins(0, 1, 0, 1)

    iw.image_viewer = imv
    # proxy = pg.SignalProxy(imv.imageItem.scene().sigMouseMoved, rateLimit=60, slot=imv.mouseMoved)
    win.setCentralWidget(imv)
    win.addDockWidget(QtCore.Qt.LeftDockWidgetArea, iw)
    win.addDockWidget(QtCore.Qt.BottomDockWidgetArea, cb)
    win.addDockWidget(QtCore.Qt.TopDockWidgetArea, tb)
    win.resize(600, 600)
    win.resize(geom.width() / 2, geom.height() / 2)
    win.show()
    print("Screen geom %d x %d" % (geom.width(), geom.height()))
    print("main window width x height", win.frameGeometry().width(), win.frameGeometry().height())
    # if win.frameGeometry().height() > 870:
    #     raise Exception("Window is too high, rearrange widgets to reduce height")
    if camera_id is not None and camera_id > 0:
        if dw.screenCount() > 1:
            geom = dw.availableGeometry(0)
            h = geom.height()
            w = geom.width()
            geom1 = dw.availableGeometry(1)
            h1 = geom1.height()
            w1 = geom1.width()
            print(geom, geom1)
            print('Available geometry height is %r width is %r' % (h, w))
            if camera_id < 5:
                h0 = h / 2.0 * ((camera_id - 1) // 2) + geom.top()
                w0 = w / 2.0 * ((camera_id - 1) % 2) + geom.left()
                win.setMaximumHeight(h / 2.0)
                win.setMaximumWidth(w / 2.0)
            else:

                h0 = h1 / 2.0 * ((camera_id - 5) // 2) + geom.height() + geom.top()
                w0 = w1 / 2.0 * ((camera_id - 5) % 2) + geom.left()
                win.setMaximumHeight(h1 / 2.0)
                win.setMaximumWidth(w1 / 2.0)
            print('Intended position is h0: %r, w0: %r' % (h0, w0))

            win.resize(1e4, 1e4)

            win.move(w0, h0)

            # print 'Screencount is %r' % dw.screenCount()
            # print dw.screen(0)
            # print dw.screen(1)
            #
            # win.windowHandle().setScreen(???)
            # PyQt gui can find extra screens, but it doesn't have a consistent way to refer to them.
            # Easier to use geometry.

        else:
            h = geom.height()
            w = geom.width()
            print('Available geometry height is %r width is %r' % (h, w))
            h0 = h / 2. * ((camera_id - 1) % 2) + geom.top()
            w0 = w / 4.0 * ((camera_id - 1) // 2) + geom.left()
            print('Intended position is h0: %r, w0: %r' % (h0, w0))
            win.setMaximumHeight(h / 2.0)
            win.setMaximumWidth(w / 4.0)

            win.move(w0, h0)

    timer = QtCore.QTimer()
    timer.timeout.connect(imv.run_auto_update)
    timer.start(3000)

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        a = QtGui.QApplication.instance().exec_()
