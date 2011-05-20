#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
...
"""

# TODO

#   - Implement logging
#   - Work on the get_files() method, adding some validation
#   - Use a secondary thread for georeferencing of the files

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
        self.connect(self.inputFilesPB, SIGNAL("clicked()"), self.get_files)
        self.toggle_widgets([self.datasetsLV, self.wgs84RB, self.customProjRB,
                            self.outputDirLE, self.outputDirPB,
                            self.deleteIntermediaryCB, self.processFilesPB])


    def toggle_widgets(self, widgetList):
        """Toggles widgets' enabled state."""

        for wid in widgetList:
            wid.setEnabled(not wid.isEnabled())

    def get_files(self):
        filePaths = QFileDialog.getOpenFileNames(self, "Select HDF5 files")


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    form = HDF5Georeferencer()
    form.show()
    app.exec_()
