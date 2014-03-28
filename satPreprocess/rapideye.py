# -*-coding:Latin-1 -*
"""
/***************************************************************************
 RapidEye : Radiance and ToaReflectance
                                 A Geosud tool
 Convert Spot DN to Top of Atmosphere (TOA) Reflectance
                              -------------------
        begin                : 2014-02-26
        copyright            : (C) 2014 by Kenji Ose / UMR Tetis - Irstea
        email                : kenji.ose@teledetection.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

# libraries

import sys, numpy, os, time
from osgeo import gdal
from osgeo.gdalconst import *
import xml.etree.ElementTree as ET

# Class RapidEye

class RapidEye:

    def __init__(self, metafile):
        """
        Metadata parsing (xml)
        """
        print 'metadata filename: %s' %(metafile)
        startTime = time.time()
        tree = ET.parse(metafile)
        self.root = tree.getroot()
        self.ns = self.root.tag.split('{')[1].split('}')[0]
        tree = None
        endTime = time.time()
        print'parsing duration: %s seconds' %(endTime-startTime)

    def getGain(self):
        """
        List of RapidEye gain values (blue, green, red, rededge, nir)
        Metadata file root required
        """
        radioFactor = {}
        for elem in self.root.iter('{%s}bandSpecificMetadata' %(self.ns)):
            bandIndex = elem.find('{%s}bandNumber' %(self.ns)).text
            bandRadio = elem.find('{%s}radiometricScaleFactor' %(self.ns)).text
            radioFactor[bandIndex] = float(bandRadio)
        self.gain = [radioFactor[str(i+1)] for i in range(len(radioFactor))]

    def getSolarAngle(self):
        """
        Solar Zenithal and Azimuthal Angles in degrees
        """
        for elem in self.root.iter('{%s}Acquisition' %(self.ns)):
            for i in elem:
                if 'illuminationElevationAngle' in i.tag:
                    self.solarZAngle = 90 - float(i.text)
                if 'illuminationAzimuthAngle' in i.tag:
                    self.solarAAngle = float(i.text)

    def getDistEarthSun(self):
        """
        Earth-Sun Distance (UA)
        Equation used (in degrees) :
        | 1-e*cos(r*(JD-4))                              |
        | where  e : Orbital eccentricity (0.01674)      |
        |        r : Mean rotation angle (0.9856 deg/day)|
        |       JD : Julian-day                          |
        """
        for elem in self.root.iter('{%s}Acquisition' %(self.ns)):
            for i in elem:
                if 'acquisitionDateTime' in i.tag:
                    date = i.text.split('T')[0].split('-')

        # Creation of julian-day table for leap year
        table_bi = {}
        anbi_nbj = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        i = 1
        for mois in range(len(anbi_nbj)):
            for jour in range(1,anbi_nbj[mois]+1):
                table_bi[mois+1, jour] = i
                i += 1

        # Creation of julian-day table for non-leap year
        table_no = {}
        anno_nbj = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        i = 1
        for mois in range(len(anno_nbj)):
            for jour in range(1,anno_nbj[mois]+1):
                table_no[mois+1, jour] = i
                i += 1

        # Earth-Sun distance calculation

        if int(date[0])%400==0 or (int(date[0])%4 == 0 and int(date[0])%100!=0):
            print "leap year"
            jour = table_bi[int(date[1]),int(date[2])]
            print "the input day is " + str(jour) + "th of the year " + date[0]
            distance_form = 1-0.01674*numpy.cos((numpy.pi/180)*0.9856*(jour-4))
            print "the Earth-Sun distance (in UA) is: " + str(distance_form)
        else:
            print "non-leap year"
            jour = table_no[int(date[1]),int(date[2])]
            print "the input day is " + str(jour) + "th of the year " + date[0]
            distance_form = 1-0.01674*numpy.cos((numpy.pi/180)*0.9856*(jour-4))
            print "the Earth-Sun distance (in UA) is: " + str(distance_form)

        self.distEarthSun = distance_form        

    def getSolarIrrad(self):
        """
        Solar irradiance values for each spectral band
        """
        # solar irradiance : blue, green, red, rededge, nir
        self.eSun = [1997.8, 1863.5, 1560.4, 1395.0, 1124.4] 
        
    def reflectanceToa(self, imgfile, outname='_refToa.tif', bitcode='32', outpath=None):
        """
        TOA Reflectance
        Equation for RapidEye:
        r = pi*dist^2*CN/(eSun*cos(thZ)*G)
        with r for TOA Reflectance
             dist for Earth-Sun Distance (in UA)
             CN for pixel value (digital number)
             eSun for Solar Irradiance
             thZ for Solar Zenithal angle
             G for gain
        """
        startTime = time.time()
        # image driver
        driver = gdal.GetDriverByName('GTiff')
        driver.Register()
        # image opening
        inDs = gdal.Open(imgfile, GA_ReadOnly)
        if inDs is None:
            print 'could not open ' + imgfile
            sys.exit(1)
        # image size and tiles 
        cols  = inDs.RasterXSize
        rows  = inDs.RasterYSize
        bands = inDs.RasterCount
        xBSize = 60
        yBSize = 60
        # output image name
        if bitcode == '32':
            codage = GDT_Float32
            nptype = numpy.float
            maxi = 1
        elif bitcode == '16':
            codage = GDT_UInt16
            nptype = numpy.uint16
            maxi = 1000

        if outpath:
            outDs = driver.Create('%s%s' %(os.path.join(outpath,os.path.splitext(os.path.basename(imgfile))[0]),outname),
                                  cols, rows, bands, codage)
        else:
            outDs = driver.Create('%s%s' %(os.path.splitext(imgfile)[0], outname), cols, rows, bands, codage)
        if outDs is None:
            print 'could not create %s%s' %(os.path.splitext(imgfile)[0], outname)
            sys.exit(1)

        for band in range(bands):
            outBand = outDs.GetRasterBand(band + 1)
            canal   = inDs.GetRasterBand(band + 1)
            # line search
            for i in range(0, rows, yBSize):
                if i + yBSize < rows:
                    numRows = yBSize
                else:
                    numRows = rows - i
                # column search
                for j in range(0, cols, xBSize):
                    if j + xBSize < cols:
                        numCols = xBSize
                    else:
                        numCols = cols - j
                    data = canal.ReadAsArray(j,i,numCols, numRows).astype(numpy.float)
                    # TOA reflectance equation
                    toa  = (maxi*(numpy.pi * self.distEarthSun**2 * data * self.gain[band])/
                            (self.eSun[band]* numpy.cos(numpy.radians(self.solarZAngle)))).astype(nptype)
                    # saturated pixels (> 1 or > 1000)
                    mask = numpy.less_equal(toa, maxi)
                    toa  = numpy.choose(mask, (maxi, toa))
                    outBand.WriteArray(toa,j,i)
            outBand.FlushCache()
            stats = outBand.GetStatistics(0, 1) 
            outBand = None
            canal = None
        # projection import
        outDs.SetGeoTransform(inDs.GetGeoTransform())
        outDs.SetProjection(inDs.GetProjection())
        # pyramid layers processing
        gdal.SetConfigOption('USE_RRD', 'YES')
        outDs.BuildOverviews(overviewlist = [2,4,8,16,32,64,128])

        inDs  = None
        outDs = None
    
        endTime = time.time()
        print 'reflectance processing duration: ' + str(endTime - startTime) + ' seconds'

    
    




