#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
Script description goes here...
"""

import sys
from optparse import OptionParser
import logging
import os

from h5georef import H5Georef

def create_parser():
    usage = """
    Georeference a HDF5 file and warp it to the desired projection.

            %prog [options] [input_hdf5_file]

    """
    parser = OptionParser(usage=usage, version="%prog 0.9")
    parser.add_option("-d", "--dataset", dest="datasetName",
                      help="Name of a specific dataset to process. If not"
                      " specified, only the main dataset will be processed.",
                      default=None)
    parser.add_option("-o", "--output-dir", dest="outputDir",
                      help="Output directory for the warped files."
                      " Defaults to the directory where this script is called.",
                      default=os.getcwd())
    parser.add_option("-g", "--georef-dir", dest="georefDir",
                      help="Output directory for the georeferenced files that"
                      " are still in the GEOS projection. Defaults to"
                      " <output_dir>/georef", default=None)
    parser.add_option("-p", "--projection-string", dest="projectionString",
                      help="Projection string indicating the desired output"
                      " projection. Accepts the same string formats as proj4."
                      " Defaults to '+proj=latlong'.",
                      default="+proj=latlong")
    parser.add_option("-x", "--delete-georefs", action="store_true",
                      dest="deleteGeorefs",
                      help="Delete intermediary georeferenced files.",
                      default=False)
    parser.add_option("-v", "--verbose", action="count", dest="verbose",
                      help="Increase verbosity (specify "
                      "multiple times for more)", default=1)
    return parser

def main(fileList, georefsDir, warpedDir, projectionString):
    logging.info("Starting execution...")
    if georefsDir is None:
        georefsDir = os.path.join(warpedDir, "georefs")
    logging.debug("georefsDir: %s" % georefsDir)
    logging.debug("warpedDir: %s" % warpedDir)
    logging.debug("projectionString: %s" % projectionString)
    logging.debug("fileList: %s" % fileList)
    for dirPath in (warpedDir, georefsDir):
        logging.debug("Creating directory: %s" % dirPath)
        if not os.path.isdir(dirPath):
            os.makedirs(dirPath)
    georefFiles = []
    for hdf5FilePath in fileList:
        logging.debug("Processing file %s..." % hdf5FilePath)
        h5g = H5Georef(hdf5FilePath)
        samples = h5g.get_sample_coords()
        logging.debug("Sample points: %s" % [s for s in samples])
        logging.debug("Georeferencing...")
        georefs = h5g.georef_gtif(samples, georefsDir)
        logging.debug("Georeferenced files: %s" % [f for f in georefs])
        logging.debug("Warping...")
        warps = h5g.warp(georefs, warpedDir, projectionString)
        logging.debug("Warped files: %s" % [f for f in warps])
        georefFiles += georefs
    if options.deleteGeorefs:
        logging.info("About to delete intermediary files...")
        for filePath in georefFiles:
            logging.debug("Deleting %s" % filePath)
            os.remove(filePath)
        try:
            logging.debug("Deleting %s" % georefsDir)
            os.rmdir(georefsDir)
        except OSError:
            logging.debug("Unable to delete the temporary files' directory.")
    logging.info("Done!")

if __name__ == "__main__":
    parser = create_parser()
    options, fileList = parser.parse_args(sys.argv[1:])
    if options.verbose == 1:
        logLevel = logging.INFO
    elif options.verbose > 1:
        logLevel = logging.DEBUG
    logging.basicConfig(level=logLevel)
    main(fileList, options.georefDir, options.outputDir,
         options.projectionString)
