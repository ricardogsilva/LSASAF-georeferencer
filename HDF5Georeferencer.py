#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
...
"""

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from h5georef import H5Georef
from ui_HDF5Georeferencer import Ui_Form

class HDF5Georeferencer(QDialog, Ui_Form):

    def __init__(self, parent=None):
        """
        ...
        """

        super(HDF5Georeferencer, self).__init__(parent)
        self.setupUi(self)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    form = HDF5Georeferencer()
    form.show()
    app.exec_()
