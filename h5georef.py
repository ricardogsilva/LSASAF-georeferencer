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
# - Check out the -sds flag of the gdal_translate program. It may be useful.
# - The MSG areas are overlapping by one pixel
# - There seems to be a small offset between the georeferencing with
# the method used in this script and the one suggested by A. Rocha's
# contact
# - When georeferencing GOES and MTSAT products, there are probably some
# changes to be made to the 'geosProjString' variable. The lon_0 and h parameters
# will probably be different

import re
import os
import random
import subprocess
from math import pow, sin, cos, atan, sqrt, radians, degrees
import tables

class H5Georef(object):

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
        self.arrays = dict()
        mainArrayName = h5File.root._f_getChild(h5File.root._v_attrs[\
                        "PRODUCT"]).name
        for arr in h5File.walkNodes("/", "Array"):
            npArray = arr.read()
            scalingFactor = arr._v_attrs["SCALING_FACTOR"]
            self.arrays[arr.name] = {
                        "nCols" : arr._v_attrs["N_COLS"],
                        "nLines" : arr._v_attrs["N_LINES"],
                        "scalingFactor" : scalingFactor,
                        "missingValue" : arr._v_attrs["MISSING_VALUE"] / scalingFactor,
                        "min" : npArray.min() / scalingFactor,
                        "max" : npArray.max() / scalingFactor,
                        "oldMin" : npArray.min(),
                        "oldMax" : npArray.max()}
            if arr.name == mainArrayName:
                self.arrays[arr.name]["mainArray"] = True
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
        self.satHeight = 35785831
        self.GEOSProjString = "+proj=geos +lon_0=%s +h=%s +x_0=0.0 +y_0=0.0" \
                              % (self.subLon, self.satHeight)
        h5File.close()

    def get_sample_coords(self, numSamples=10):
        """
        Return a list of tuples holding line, col, northing,easting.
        """

        samplePoints = []
        #using the main array to extract nCols and nLines
        nCols, nLines = [(v["nCols"], v["nLines"]) for k, v in\
                        self.arrays.iteritems() if v.get("mainArray")][0]
        while len(samplePoints) < numSamples:
            line = random.randint(1, nLines)
            col = random.randint(1, nCols)
            lon, lat = self._get_lat_lon(line, col)
            if lon:
                easting, northing = self._get_east_north(lon, lat)
                samplePoints.append((line, col, northing, easting))
        return samplePoints

    def _get_east_north(self, lon, lat):
        """
        Convert between latlon and geos coordinates.

        This method uses the external 'cs2cs' utility to perform coordinate
        transformation.
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
            lon = degrees(atan(s2 / s1)) + self.subLon
            lat = degrees(atan(self.p2 * s3 / sxy))
        except ValueError:
            lon = lat = None
        return lon, lat

    def georef_gtif(self, samplePoints, outFileDir=None, selectedArrays=None):
        """
        Create a georeferenced GeoTiff file for each of the selected arrays.

        Inputs:
            samplePoints - a list of tuples containing line, column, northing,
                           easting, for each of the desired GCPs to set. This
                           corresponds to the output of the 'get_sample_coords'
                           method.
            outFileDir - a string specifying the directory where the files
                         are to be stored.
            selectedArrays - a list of strings specifying the name of the 
                             arrays present in the original HDF5 file that
                             are to be georeferenced.

        This method is calling the 'gdal_translate' utility to perform GCP
        georeferencing based on the 'samplePoints' argument. The input CRS
        is assumed to be the GEOS projection.
        """

        if outFileDir is None:
            outFileDir = os.getcwd()
        if selectedArrays is None:
            selectedArrays = [k for k, v in self.arrays.iteritems() if
                              v.get("mainArray")]
        successfullGeorefs = []
        for arrayName in selectedArrays:
            missingValue = self.arrays[arrayName].get("missingValue")
            translateCommand = 'gdal_translate -q -scale %s %s %s %s"\
                               " -a_nodata "%s" -a_srs "%s" ' % \
                                (self.arrays[arrayName].get("oldMin"),
                                 self.arrays[arrayName].get("oldMax"),
                                 self.arrays[arrayName].get("min"),
                                 self.arrays[arrayName].get("max"),
                                 missingValue, self.GEOSProjString)
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

        warpCommand = 'gdalwarp -dstnodata "%s" -s_srs "%s" -t_srs "%s" %s %s'
        warpedFiles = []
        for filePath in fileList:
            arrayName = self._array_name_from_file(filePath)
            missingValue = self.arrays[arrayName].get("missingValue")
            dirName, basename = os.path.split(filePath)
            extList = basename.rsplit(".")
            outName = "%s_warped.%s" % (".".join(extList[:-1]), extList[-1])
            outFileName = os.path.join(outDir, outName)
            print(warpCommand % (missingValue, self.GEOSProjString,
                projectionString, filePath, outFileName))
            returnCode = subprocess.call(warpCommand % (missingValue, 
                                         self.GEOSProjString,
                                         projectionString, filePath,
                                         outFileName), shell=True)
            if returnCode == 0:
                warpedFiles.append(outFileName)
        return warpedFiles

    def _array_name_from_file(self, filePath):
        """
        Extract the name of the array from the input filePath.
        """

        return [n for n in self.arrays.keys() if n in filePath][0]


if __name__ == "__main__":
    pass
