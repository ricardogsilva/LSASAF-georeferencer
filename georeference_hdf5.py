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
# - Add 'nodata' value information
# - Correct the scaling factor 
# - The MSG areas are overlapping by one pixel
# - There seems to be a small offset between the georeferencing with
# the method used in this script and the one suggested by A. Rocha's
# contact
# - When georeferencing GOES and MTSAT products, there are probably some
# changes to be made to the 'geosProjString' variable. The lon_0 and h parameters
# will probably be different

import re
import os
import numpy as np # can this dependency be removed?
import subprocess
from math import pow, sin, cos, atan, sqrt, radians, degrees
import tables

class HDF5Georeferencer(object):

    def __init__(self, h5FilePath):
        """
        Open an HDF5 file and extract its relevant parameters.
        """

        self.h5FilePath = h5FilePath
        # the LSA-SAF parameters have this shift because they use Fortran
        # (an array's first index starts at 1 and not 0)
        self.CLCorrection = -1 
        # self.p1: Distance between satellite and center of the Earth, measured in km
        self.p1 = 42164 
        self.p2 = 1.006803
        self.p3 = 1737121856
        h5File = tables.openFile(h5FilePath)
        self.arrayNames = [arr.name for arr in h5File.walkNodes("/", "Array")]
        self.mainArray = h5File.root._f_getChild(\
                         h5File.root._v_attrs["PRODUCT"]).name
        subLonRE = re.search(r"[A-Za-z]{4}[<(][-+]*[0-9]{3}\.?[0-9]*[>)]",
                             h5File.root._v_attrs["PROJECTION_NAME"])

        if subLonRE:
            self.subLon = float(subLonRE.group()[5:-1])
        else:
            raise ValueError
        self.coff = h5File.root._v_attrs["COFF"] + self.CLCorrection
        self.loff = h5File.root._v_attrs["LOFF"] + self.CLCorrection
        self.cfac = h5File.root._v_attrs["CFAC"] # should this be corrected too?
        self.lfac = h5File.root._v_attrs["LFAC"] # should this be corrected too?
        datasetArray = h5File.root._f_getChild(h5File.root._v_attrs["PRODUCT"])
        self.nCols = datasetArray._v_attrs["N_COLS"]
        self.nLines = datasetArray._v_attrs["N_LINES"]
        self.satHeight = 35785831
        self.GEOSProjString = "+proj=geos +lon_0=%s +h=%s +x_0=0.0 +y_0=0.0" \
                              % (self.subLon, self.satHeight)
        h5File.close()

    def get_sample_coords(self, numSamples=10):
        """
        Return a list of tuples holding line, col, northing,easting.
        """

        samplePoints = []
        while len(samplePoints) < numSamples:
            line = np.random.randint(1, self.nLines + 1)
            col = np.random.randint(1, self.nCols + 1)
            lon, lat = self._get_lat_lon(line, col)
            if lon:
                easting, northing = self._get_east_north(lon, lat)
                samplePoints.append((line, col, northing, easting))
        return samplePoints

    def _get_east_north(self, lon, lat):
        """
        Convert between latlon and geos coordinates.
        """

        cs2csCommand = "cs2cs +init=epsg:4326 +to %s <<EOF\n%s %s\nEOF" \
                        % (self.GEOSProjString, lon, lat)
        newProcess = subprocess.Popen(cs2csCommand, shell=True, 
                                      stdin=subprocess.PIPE, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE)
        stdout, stderr = newProcess.communicate()
        easting, northing, other = stdout.strip().split()
        return easting, northing

    def _get_lat_lon(self, nLin, nCol):
        """
        Get the lat lon coordinates of a pixel.
        """
        
        try:
            # x and y are measured in Degrees
            x = radians((nCol - self.coff) / (pow(2, -16) * self.cfac)) 
            y = radians((nLin - self.loff) / (pow(2, -16) * self.lfac))
            sd = sqrt(pow(self.p1 * cos(x) * cos(y), 2) - \
                      self.p3 * (pow(cos(y), 2) + self.p2 * pow(sin(y), 2)))
            sn = ((self.p1 * cos(x) * cos(y)) - sd) / (pow(cos(y), 2) + \
                 self.p2 * pow(sin(y), 2))
            s1 = self.p1 - sn * cos(x) * cos(y)
            s2 = sn * sin(x) * cos(y)
            s3 = -sn * sin(y)
            sxy = sqrt(pow(s1, 2) + pow(s2, 2))
            lon = degrees(atan(s2 / s1) + self.subLon)
            lat = degrees(atan(self.p2 * s3 / sxy))
        except ValueError:
            lon = lat = None
        return lon, lat

    def georef_gtif(self, samplePoints, outFileDir=None, selectedArrays=None):
        """
        ...
        """

        if outFileDir is None:
            outFileDir = os.getcwd()
        translateCommand = 'gdal_translate -a_srs "%s" ' % self.GEOSProjString
        if selectedArrays is None:
            selectedArrays = [self.mainArray]
        successfullGeorefs = []
        for arrayName in selectedArrays:
            inFileName = os.path.basename(self.h5FilePath)
            extensionList = inFileName.rsplit(".")
            if len(extensionList) > 1:
                inFileName = ".".join(extensionList[:-1])
            outFileName = os.path.join(outFileDir, "%s_%s.tif" \
                                       % (inFileName, arrayName))
            for (line, col, northing, easting) in samplePoints:
                translateCommand += '-gcp %s %s %s %s ' % (col, line, easting, northing)
            translateCommand += '"HDF5:"%s"://%s" %s' % (self.h5FilePath,
                                arrayName, outFileName)
            returnCode = subprocess.call(translateCommand, shell=True)
            if returnCode == 0:
                successfullGeorefs.append(outFileName)
        return successfullGeorefs

    def warp(self, fileList, outDir, projectionString="+proj=latlong"):
        """
        Warp the georeferenced files to the desired projection.

        This method uses the external 'gdalwarp' utility program to warp
        already georeferenced files that are in the GEOS projection to another
        desired projection.

        Inputs:
            fileList - a list of paths pointing to already
                       georeferenced files that are still in the GEOS
                       projection.
            projectionString - a string, taking any of the accepted PROJ4
                               formats for describing a projection. Defaults
                               to '+proj=latlong'.
            outdir - The path to the desired output directory. Defaults
                     to the same directory of the files in 'fileList'.

        Returns: A list of paths to the successfully warped files.
        """

        warpCommand = 'gdalwarp  -s_srs "%s" -t_srs "%s" %s %s'
        warpedFiles = []
        for filePath in fileList:
            dirName, basename = os.path.split(filePath)
            extList = basename.rsplit(".")
            outName = "%s_warped.%s" % (".".join(extList[:-1]), extList[-1])
            outFileName = os.path.join(outDir, outName)
            returnCode = subprocess.call(warpCommand % (self.GEOSProjString,
                                         projectionString, filePath,
                                         outFileName), shell=True)
            if returnCode == 0:
                warpedFiles.append(outFileName)
        return warpedFiles

if __name__ == "__main__":
    pass
