import glob
import os, sys
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np

pg.setConfigOptions(imageAxisOrder='row-major')
from pmc_turbo.camera.image_processing import blosc_file
from pmc_turbo.camera.pipeline.indexer import MergedIndex

# root_path = '/home/pmcroot/c2'
root_path = '/'


class MyImageView(pg.ImageView):
    # def __init__(self,root_path=root_path,*args,**kwargs):
    def __init__(self, real_time_values=None, *args, **kwargs):
        self.root_path = '/'
        print(self.root_path)
        super(MyImageView, self).__init__(*args, **kwargs)
        self.mi = MergedIndex('*', data_dirs=[os.path.join(self.root_path, ('data%d' % k)) for k in range(1, 5)])
        self.last_index = 0
        self.real_time_values = real_time_values
        self.update(-1, autoLevels=True, autoRange=True)

    def update(self, index, autoLevels=False, autoRange=False):
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
        if self.real_time_values:
            self.real_time_values.update_filename(filename)
        img, chunk = blosc_file.load_blosc_image(filename)
        self.setImage(img, autoLevels=autoLevels, autoRange=autoRange)

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


if __name__ == "__main__":
    app = QtGui.QApplication([])
    win = QtGui.QMainWindow()
    win.resize(800, 800)
    imv = MyImageView()
    win.setCentralWidget(imv)
    win.show()

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
