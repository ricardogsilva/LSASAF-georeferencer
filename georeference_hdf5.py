#!/usr/bin/env python
#-*- coding: utf-8 -*-

"""
A script to georeference HDF5 files produced at the IM processing lines.

This script is based on the Product User Manual(PUM) of the LSA-SAF 
LST product.
The PUM can be obtained onlined at:

http://landsaf.meteo.pt/GetDocument.do?id=304

Refer to section 4.2(Geolocation/Rectification) for some background on
the formulas used in this script.

Besides the formulas mentioned, this script is using some gdal and proj4 
utility programs to perform the actual georeferencing.

Other useful links:
    EUMETSAT's technical specs on the LRIT/HRIT formats, including a section
    on the Normalized Geostationary Projection
        -> http://www.eumetsat.int/groups/cps/documents/document/pdf_cgms_03.pdf

    Description of the GEOS projection and it's description with the Proj4
    Cartographic Projections Library
        -> http://www.remotesensing.org/geotiff/proj_list/geos.html
"""

# TODO
#
# - Reorganize the code in order to improve the parsing of the inputs
# - There seems to be a small offset between the georeferencing with
# the method used in this script and the one suggested by A. Rocha's
# contact
# - The MSG areas are overlapping by one pixel
# - Create a VRT output
# - Add 'nodata' value information
# - When georeferencing GOES and MTSAT products, there are probably some
# changes to be made to the 'geosProjString' variable. The lon_0 and h parameters
# will probably be different

import sys
import re
import os.path
import numpy as np
import subprocess
from optparse import OptionParser
from math import pow, sin, cos, atan, sqrt, radians, degrees
import tables


def main(argList):
    parser = create_parser()
    options, arguments = parser.parse_args(argList)
    inputFile = arguments[0]
    outputFile = arguments[1]
    fileNameList = inputFile.split("_")
    hdf5Params = get_hdf5_data(inputFile, options.datasetName)
    print("subLon: %s" % hdf5Params["subLon"])
    geosProjString = "+proj=geos +lon_0=%s +h=35785831 +x_0=0.0 +y_0=0.0" % hdf5Params["subLon"]
    samplePoints = get_sample_coords(hdf5Params, geosProjString)
    translateCommand = 'gdal_translate -a_srs "%s" ' % geosProjString
    for (line, col, northing, easting) in samplePoints:
        translateCommand += '-gcp %s %s %s %s ' % (col, line, easting, northing)
    translateCommand += '"HDF5:"%s"://%s" %s' % (inputFile, hdf5Params["dataset"], outputFile)
    print("translateCommand: %s" % translateCommand)
    returnCode = subprocess.call(translateCommand, shell=True)

def get_hdf5_data(filePath, dataset=None):
    """
    Extract all the relevant parameters from the HDF5 file's metadata.
    """

    inDs = tables.openFile(filePath)
    if dataset is None:
        dataset = inDs.root._v_attrs["PRODUCT"]
    datasetArray = inDs.root._f_getChild(dataset)
    subLonRE = re.search(r"[A-Za-z]{4}[<(][-+]*[0-9]{3}\.?[0-9]*[>)]",
                         inDs.root._v_attrs["PROJECTION_NAME"])
    if subLonRE:
        subLon = float(subLonRE.group()[5:-1])
    else:
        raise ValueError

    hdf5Params = {"subLon" : subLon,
                  "dataset" : dataset,
                  "CFAC" : inDs.root._v_attrs["CFAC"],
                  "LFAC" : inDs.root._v_attrs["LFAC"],
                  "COFF" : inDs.root._v_attrs["COFF"],
                  "LOFF" : inDs.root._v_attrs["LOFF"],
                  "datasetArray" : inDs.root._f_getChild(dataset),
                  "missingValue" : datasetArray._v_attrs["MISSING_VALUE"],
                  "scalingFactor" : datasetArray._v_attrs["SCALING_FACTOR"],
                  "nCols" : datasetArray._v_attrs["N_COLS"],
                  "nLines" : datasetArray._v_attrs["N_LINES"]}
    inDs.close()
    return hdf5Params

def get_sample_coords(hdf5Params, geosProjString, numSamples=10):
    """
    Return a list of tuples holding line, col, lat,lon.
    """

    samplePoints = []
    while len(samplePoints) < numSamples:
        line = np.random.randint(1, hdf5Params["nLines"] + 1)
        col = np.random.randint(1, hdf5Params["nCols"] + 1)
        lon, lat = get_lat_lon(line, col, hdf5Params)
        if lon:
            easting, northing = get_east_north(lon, lat, geosProjString)
            samplePoints.append((line, col, northing, easting))
    return samplePoints

def get_east_north(lon, lat, geosProjString):
    """
    Convert between latlon and geos coordinates.
    """

    print("geosProjString: %s" % geosProjString)
    cs2csCommand = "cs2cs +init=epsg:4326 +to %s <<EOF\n%s %s\nEOF" % (geosProjString, lon, lat)
    newProcess = subprocess.Popen(cs2csCommand, shell=True, 
                                  stdin=subprocess.PIPE, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE)
    stdout, stderr = newProcess.communicate()
    easting, northing, other = stdout.strip().split()
    return easting, northing

def create_parser():
    usage = """
    Georeference a HDF5

            %prog [options] input_hdf5_file output_vrt_file 

    VRT is the GDAL Virtual Format. It allows a virtual GDAL dataset to be composed from other datasets.
    For more information, visit: http://www.gdal.org/gdal_vrttut.html
    """
    parser = OptionParser(usage=usage, version="%prog 0.9")
    parser.add_option("-d", "--dataset", dest="datasetName",
                      help="Name of a specific dataset to process. If not specified, the main dataset will be processed. The main dataset's name will be extracted from the filename of the input hdf5 file.")
    return parser

def get_lat_lon(nLin, nCol, hdf5Params):
    # CONSTANTS
    subLon = hdf5Params["subLon"]
    # p1: Distance between satellite and center of the Earth, measured in km
    p1 = 42164 
    p2 = 1.006803
    p3 = 1737121856
    CFAC = hdf5Params["CFAC"]
    LFAC = hdf5Params["LFAC"]
    CLCorrection = -1
    COFF = hdf5Params["COFF"] + CLCorrection
    LOFF = hdf5Params["LOFF"] + CLCorrection
    try:
        x = radians((nCol - COFF) / (pow(2, -16) * CFAC)) # x is measured in Degrees
        y = radians((nLin - LOFF) / (pow(2, -16) * LFAC)) # y is measured in Degrees
        sd = sqrt(pow(p1 * cos(x) * cos(y), 2) - \
                  p3 * (pow(cos(y), 2) + p2 * pow(sin(y), 2)))
        sn = ((p1 * cos(x) * cos(y)) - sd) / (pow(cos(y), 2) + p2 * pow(sin(y), 2))
        s1 = p1 - sn * cos(x) * cos(y)
        s2 = sn * sin(x) * cos(y)
        s3 = -sn * sin(y)
        sxy = sqrt(pow(s1, 2) + pow(s2, 2))
        lon = degrees(atan(s2 / s1) + subLon)
        lat = degrees(atan(p2 * s3 / sxy))
    except ValueError:
        lon = lat = None
    return lon, lat

if __name__ == "__main__":
    main(sys.argv[1:])
