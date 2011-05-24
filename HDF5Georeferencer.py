#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
...
"""

# TODO
#
#   - Work on the get_files() method, adding some validation
#   - Use a secondary thread for georeferencing of the files

import logging
from optparse import OptionParser

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from h5georef import H5Georef
from ui_HDF5Georeferencer import Ui_Form

class HDF5Georeferencer(QDialog, Ui_Form):

    def __init__(self, log="debug", parent=None):
        """
        ...
        """

        self.logger = create_logger(log)
        self.logger.debug("Starting execution")
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
        if len(filePaths) > 0:
            self.logger.debug("Some files have been selected.")
            self.inputFilesLE.setText(";".join([str(p) for p in filePaths]))
        else:
            self.logger.debug("No files have been selected.")



def create_logger(logLevel="info"):
    level = eval("logging.%s" % (logLevel.upper()))
    logging.basicConfig(level=level)
    logger = logging.getLogger()
    return logger

def parse_arguments(argList):
    parser = OptionParser()
    parser.add_option("-v", "--verbose", dest="verbose", action="count",
                      help="increase verbosity (specify multiple times"
                      " for more", default=0)
    options, args = parser.parse_args(argList)
    return options, args

def get_log_level(levelCount):
    if levelCount == 0:
        logLevel = "error"
    elif levelCount == 1:
        logLevel = "warning"
    elif levelCount == 2:
        logLevel = "info"
    else:
        logLevel = "debug"
    return logLevel

if __name__ == "__main__":
    import sys
    options, args = parse_arguments(sys.argv[1:])
    logLevel = get_log_level(options.verbose)
    
    app = QApplication(args)
    form = HDF5Georeferencer(log=logLevel)
    form.show()
    app.exec_()
