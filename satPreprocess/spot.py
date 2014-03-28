# -*-coding:Latin-1 -*
"""
/***************************************************************************
 Spot : Radiance and ToaReflectance
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
from osgeo           import gdal
from osgeo.gdalconst import *
import xml.etree.ElementTree as ET

# Class Spot5

class Spot5:
        
    def __init__(self, metafile):
        """
        Metadata parsing (xml)
        """
        print 'metadata filename: %s' %(metafile)
        startTime = time.time()
        tree = ET.parse(metafile)
        self.root = tree.getroot()
        tree = None
        endTime = time.time()
        print'parsing duration: %s seconds' %(endTime-startTime)
        
    def getGain(self):
        """
        List of Spot5 gain values (green, red, nir, mir)
        Metadata file root required
        """
        radioFactor = {}
        for elem in self.root.iter('Spectral_Band_Info'):
            bandIndex = elem.find('BAND_INDEX').text
            bandRadio = elem.find('PHYSICAL_GAIN').text
            radioFactor[bandIndex] = float(bandRadio)
        # reorder gains according to band order in the image file (nir, r, g, mir)
        self.gain = [radioFactor['3'],radioFactor['2'],radioFactor['1'],radioFactor['4']]

    def getSolarAngle(self):
        """
        Solar Zenithal and Azimuthal Angles in degrees
        """
        #for elem in self.root.iter('Dataset_Sources'):
        self.solarAAngle = float(self.root.find(
            'Dataset_Sources/Source_Information/Scene_Source/SUN_AZIMUTH').text)
        self.solarZAngle = 90 - float(self.root.find(
            'Dataset_Sources/Source_Information/Scene_Source/SUN_ELEVATION').text)

    def getDistEarthSun(self):       
        """
        Earth-Sun Distance (UA)
        Equation used (in degrees) :
        | 1-e*cos(r*(JD-4))                              |
        | where  e : Orbital eccentricity (0.01674)      |
        |        r : Mean rotation angle (0.9856 deg/day)|
        |       JD : Julian-day                          |
        """
        date = self.root.find(
            'Dataset_Sources/Source_Information/Scene_Source/IMAGING_DATE').text.split('-')

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
        solarIrrad = {}
        for elem in self.root.iter('Band_Solar_Irradiance'):
            bandIndex = elem.find('BAND_INDEX').text
            bandRadio = elem.find('SOLAR_IRRADIANCE_VALUE').text
            solarIrrad[bandIndex] = float(bandRadio)
        # reorder solar irradiance according to band order in the image file (nir, r, g, mir)
        self.eSun = [solarIrrad['3'],solarIrrad['2'],solarIrrad['1'],solarIrrad['4']]      

    def reflectanceToa(self, imgfile, outname='_refToa.tif', bitcode='32', outpath=None):
        """
        TOA Reflectance
        Equation for Spot5:
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
                    toa  = (maxi*(numpy.pi * self.distEarthSun**2 * data)/
                            (self.gain[band] * self.eSun[band] * numpy.cos(numpy.radians(self.solarZAngle)))).astype(nptype)
                    # saturated pixels (> 1 or > 1000)
                    mask = numpy.less_equal(toa, maxi)
                    toa  = numpy.choose(mask, (maxi, toa))
                    outBand.WriteArray(toa,j,i)
            outBand.FlushCache()
            stats = outBand.GetStatistics(0, 1) 
            outBand = None
            canal = None
        # Import of inDs' GCPs
        outDs.SetGCPs(inDs.GetGCPs(),inDs.GetGCPProjection())
        # Metadata chage in order to spedify a "point" origine for GCPs
        #(otherwise shift of 1/2 pixel)
        outDs.SetMetadataItem("AREA_OR_POINT", "Point")
        # pyramid layers processing
        gdal.SetConfigOption('USE_RRD', 'YES')
        outDs.BuildOverviews(overviewlist = [2,4,8,16,32,64,128])
        
        inDs  = None
        outDs = None

        endTime = time.time()
        print 'reflectance processing duration: ' + str(endTime - startTime) + ' seconds'



