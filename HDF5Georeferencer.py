#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
...
"""

# TODO
#
#   - Use QMessageBox's property-based API instead of the static functions
#   - Use validators for both browse... operations

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

        self.logger = create_logger(log, logName=self.__class__.__name__)
        self.logger.debug("Starting execution")
        super(HDF5Georeferencer, self).__init__(parent)
        self.setupUi(self)
        self.processedFiles = 0
        self.filePaths = []
        self.datasetsLW.setSelectionMode(3) # multiple selection
        self.progressBar.setVisible(False)
        self.progressBar.setMaximum(100)
        self.progressBar.setMinimum(0)
        self.deleteIntermediaryCB.setChecked(True)
        self.processingThread = GeoreferencerThread()
        self.connect(self.processingThread, SIGNAL("finished(bool)"),
                     self.finish_processing)
        self.connect(self.processingThread, SIGNAL("processedFile(QString)"),
                     self.update_progress)
        self.connect(self.inputFilesPB, SIGNAL("clicked()"), self.get_files)
        self.connect(self.outputDirPB, SIGNAL("clicked()"), 
                     self.select_output_dir)
        self.connect(self.processFilesPB, SIGNAL("clicked()"), 
                     self.process_files)
        self.connect(self.loadFilePB, SIGNAL("clicked()"), self.get_datasets)
        self.connect(self.wgs84RB, SIGNAL("toggled(bool)"),
                     self.toggle_radio_buttons)
        self.wgs84RB.setChecked(True)
        self.enable_other_widgets(toggleState=False)

    def toggle_widgets(self, widgetList, toggleState=True):
        """Toggle widgets' enabled state."""

        self.logger.debug("toggle_widgets method called.")
        for wid in widgetList:
            wid.setEnabled(toggleState)
        self.logger.debug("toggle_widgets method exiting.")

    def get_files(self):
        self.logger.debug("get_files method called.")
        filePaths = QFileDialog.getOpenFileNames(self, "Select HDF5 files")
        if len(filePaths) > 0:
            self.logger.debug("Some files have been selected.")
            self.inputFilesLE.setText(";".join([str(p) for p in filePaths]))
        else:
            self.logger.debug("No files have been selected.")
            self.inputFilesLE.setText("")
        self.logger.debug("get_files method exiting.")

    def get_selected_file_paths(self):
        self.logger.debug("get_selected_file_paths method called.")
        self.logger.debug("get_selected_file_paths method exiting.")
        return [str(s) for s in self.inputFilesLE.text().split(";")]

    def get_datasets(self):
        """Open one of the user selected files and extract dataset names."""

        self.logger.debug("get_datasets method called.")
        filePaths = self.get_selected_file_paths()
        self.datasetsLW.clear()
        try:
            h5f = H5Georef(filePaths[0])
            datasets = h5f.arrays.keys()
            mainDataset = [name for name, params in h5f.arrays.iteritems() \
                           if params.get("mainArray")][0]
            self.logger.info("datasets: %s" % datasets)
            self.logger.info("main dataset: %s" % mainDataset)
            for datasetName in datasets:
                self.datasetsLW.addItem(datasetName)
            if len(datasets) > 0:
                self.enable_other_widgets(toggleState=True)
            else:
                self.enable_other_widgets(toggleState=False)
                raise IOError("Invalid HDF5 file.\nCouldn't determine "
                              "available datasets.")
        except IOError, msg:
            self.enable_other_widgets(toggleState=False)
            self.logger.error(msg)
            QMessageBox.critical(self, "Error", msg.args[0])
        self.logger.debug("get_datasets method exiting.")

    def toggle_radio_buttons(self):
        self.logger.debug("toggle_radio_buttons method called.")
        if self.wgs84RB.isChecked():
            self.customProjectionTE.setEnabled(False)
        else:
            self.customProjectionTE.setEnabled(True)
        self.logger.debug("toggle_radio_buttons method exiting.")

    def enable_other_widgets(self, toggleState=True):
        self.logger.debug("enable_other_widgets method called.")
        widgetsToActUpon = (self.label_2, self.datasetsLW, self.label_4,
                            self.wgs84RB, self.customProjRB,
                            self.customProjectionTE, self.label_3,
                            self.outputDirLE, self.outputDirPB,
                            self.deleteIntermediaryCB, self.processFilesPB)
        self.toggle_widgets(widgetsToActUpon, toggleState=toggleState)
        self.logger.debug("enable_other_widgets method exiting.")

    def select_output_dir(self):
        self.logger.debug("select_output_dir method called.")
        outputDir = QFileDialog.getExistingDirectory(self, "Select an output directory")
        self.logger.debug("outputDir: %s" % outputDir)
        if outputDir:
            self.logger.debug("There is an output directory selected.")
            self.outputDirLE.setText(outputDir)
        else:
            self.logger.debug("No output directory selected. Using current directory.")
            self.outputDirLE.setText("")
        self.logger.debug("select_output_dir method exiting.")

    def get_selected_projection(self):
        self.logger.debug("get_selected_projection method called.")
        if self.wgs84RB.isChecked():
            projectionString = "+proj=latlong"
        else:
            projectionString = str(self.customProjectionTE.toPlainText())
        self.logger.debug("get_selected_projection method exiting.")
        return projectionString

    def process_files(self):
        self.logger.debug("process_files method called.")
        infoDict = self.get_necessary_info()
        self.logger.info("infoDict: %s" % infoDict)
        self.processedFiles = 0
        self.filePaths = infoDict["filePaths"]
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.processingThread.initialize(infoDict)
        self.processingThread.start()
        self.logger.debug("process_files method exiting.")

    def get_necessary_info(self):
        self.logger.debug("get_necessary_info method called.")
        filePaths = self.get_selected_file_paths()
        datasets = [str(i.text()) for i in self.datasetsLW.selectedItems()]
        projectionString = self.get_selected_projection()
        outputDir = str(self.outputDirLE.text())
        error = False
        if len(filePaths) == 0:
            error = True
            msg = "No HDF5 files selected."
        elif len(datasets) == 0:
            error = True
            msg = "No dataset selected."
        elif outputDir == "":
            error = True
            msg = "No output directory specified."
        elif projectionString == "":
            error = True
            msg = "No projection specified."
        if error:
            QMessageBox.critical(self, "Error", msg)
        deleteIntermediary = self.deleteIntermediaryCB.isChecked()
        self.logger.debug("get_necessary_info method exiting.")
        return {"filePaths" : filePaths, "datasets" : datasets,
                "projectionString" : projectionString, "outputDir" : outputDir,
                "deleteIntermediary" : deleteIntermediary}

    def update_progress(self, filePath):
        """
        Update progress bar when files are processed by the secondary thread.
        """

        self.logger.debug("update_progress method called.")
        self.processedFiles += 1
        progress = (self.processedFiles * 100.0) / len(self.filePaths)
        self.progressBar.setValue(progress)
        self.logger.debug("update_progress method exiting.")

    def finish_processing(self, finishStatus):
        """
        Terminate the processing and inform the user.
        """

        self.logger.debug("finish_processing method called.")
        self.logger.debug("finishStatus: %s" % finishStatus)
        if finishStatus:
            QMessageBox.information(self, "Success", "Files have been"
                                    " processed successfully.")
        else:
            QMessageBox.critical(self, "Error", "there was an error"
                                    " processing the files.")
        self.progressBar.setVisible(False)
        self.logger.debug("finish_processing method exiting.")


class GeoreferencerThread(QThread):

    def __init__(self, parent=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        super(GeoreferencerThread, self).__init__(parent)

    def initialize(self, paramsDict):

        self.logger.debug("initialize method called.")
        self.filePaths = paramsDict["filePaths"]
        self.datasets = paramsDict["datasets"]
        self.outputDir = paramsDict["outputDir"]
        self.projectionString = paramsDict["projectionString"]
        self.logger.debug("initialize method exiting.")

    def run(self):
        self.logger.debug("run method called.")
        processResults = self.process_files()
        success = False
        if not False in [res.values()[0] for res in processResults]:
            success = True
        self.emit(SIGNAL("finished(bool)"), success)
        self.logger.debug("run method exiting.")

    def process_files(self):
        self.logger.debug("process_files method called.")
        results = []
        for filePath in self.filePaths:
            self.logger.debug("filePath: %s" % filePath)
            warpedFiles = self.process_file(filePath)
            if len(warpedFiles) > 0:
                result = {filePath : True}
            else:
                result = {filePath : False}
            self.logger.debug("result: %s" % result)
            results.append(result)
            self.emit(SIGNAL("processedFile(QString)"), filePath)
        self.logger.debug("results: %s" % results)
        self.logger.debug("process_files method exiting.")
        return results

    def process_file(self, filePath):

        self.logger.debug("process_file method called.")
        h5f = H5Georef(filePath)
        sampleCoords = h5f.get_sample_coords()
        self.logger.debug("sampleCoords: %s" % sampleCoords)
        georefFiles = h5f.georef_gtif(sampleCoords, self.outputDir,
                                      self.datasets)
        self.logger.debug("georefFiles: %s" % georefFiles)
        warpedFiles = h5f.warp(georefFiles, self.outputDir,
                               self.projectionString)
        self.logger.debug("warpedFiles: %s" % warpedFiles)
        self.logger.debug("process_file method exiting.")
        return warpedFiles


def create_logger(logLevel, logName):
    level = eval("logging.%s" % (logLevel.upper()))
    logging.basicConfig(level=level)
    logger = logging.getLogger(logName)
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
