# -*- coding: utf-8 -*-
"""
/***************************************************************************
 geosudRefToa
                                 A QGIS plugin
 TOA reflectance conversion for Geosud satellite data
                              -------------------
        begin                : 2014-02-27
        copyright            : (C) 2014 by Kenji Ose/Irstea
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
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import showPluginHelp
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from geosudreftoadialog import geosudRefToaDialog
import os.path
# Import the code for raster processing
from satPreprocess import rapideye
from satPreprocess import spot
from satPreprocess import ldcm
# Other
import time
import glob

class geosudRefToa:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, 'i18n', 'geosudreftoa_{}.qm'.format(locale))

        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = geosudRefToaDialog()

        self.bar = QgsMessageBar()
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.dlg.glInfo.addWidget(self.bar, 0,0,1,1)
        
        self.path = os.path.expanduser("~")
      
        QObject.connect(self.dlg.pbLoadImg, SIGNAL('clicked()'), self.displayDirFile)
        QObject.connect(self.dlg.pbMetadata, SIGNAL('clicked()'), self.displayDirMetadata)
        QObject.connect(self.dlg.pbGetParam, SIGNAL('clicked()'), self.displayMetadata)
        QObject.connect(self.dlg.pbConvert, SIGNAL('clicked()'), self.processToa)
        QObject.connect(self.dlg.pbLucky, SIGNAL('clicked()'), self.autoLoadMetadata)
        QObject.connect(self.dlg.cbOutput, SIGNAL('clicked()'),self.activeOutputDir)
        QObject.connect(self.dlg.pbOutput, SIGNAL('clicked()'),self.outputDir)
        QObject.connect(self.dlg.pbAbout, SIGNAL('clicked()'), self.helpFile)

        self.dlg.cbOutput.setEnabled(False)
        self.dlg.pbConvert.setEnabled(False)
        self.dlg.pbOutput.setEnabled(False)
        self.dlg.leOutput.setEnabled(False)
        self.dlg.pbLucky.setEnabled(False)
        self.dlg.rbRefNorm.setChecked(True)

        self.dlg.groupInstrument = QButtonGroup()
        self.dlg.groupInstrument.addButton(self.dlg.rbSpot)
        self.dlg.groupInstrument.addButton(self.dlg.rbRapideye)
        self.dlg.groupInstrument.addButton(self.dlg.rbLandsat)

        self.dlg.groupOutbit = QButtonGroup()
        self.dlg.groupOutbit.addButton(self.dlg.rbRefNorm)
        self.dlg.groupOutbit.addButton(self.dlg.rbRefMilli)

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(":/plugins/geosudreftoa/icon.png"),
            u"geosud Toa", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&Geosud Toa Reflectance", self.action)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&Geosud Toa Reflectance", self.action)
        self.iface.removeToolBarIcon(self.action)

    def displayDirFile(self):
        if self.dlg.rbRapideye.isChecked():
            self.dlg.leInput.setText(QFileDialog.getOpenFileName(self.dlg,
                                                                 u'RapidEye Image',
                                                                 self.path,
                                                                 "RapidEye image file (*.tif)"))
        elif self.dlg.rbSpot.isChecked():
            self.dlg.leInput.setText(QFileDialog.getOpenFileName(self.dlg,
                                                                 u'Spot Image',
                                                                 self.path,
                                                                 "Spot image file (*.tif)"))
        elif self.dlg.rbLandsat.isChecked():
            bandList = QFileDialog.getOpenFileNames(self.dlg,
                                                    u'Landsat Spectral Bands',
                                                    self.path,
                                                    "Landsat band files (*.tif)")
            for i in bandList:
                bandId = os.path.splitext(i)[0][-2:]
                if not bandId in ['B%s' %i for i in range(1,10)]:
                    self.bar.pushMessage("Info", "Select spectral bands between B1 and B9", level=QgsMessageBar.WARNING, duration=3)
                else:
                    self.dlg.leInput.setText(', '.join(bandList))
        else:
            self.bar.pushMessage("Info", "Select an instrument before loading satellite image", level=QgsMessageBar.WARNING, duration=3)
        self.imgfile = self.dlg.leInput.text().split(', ')
        self.path = os.path.dirname(self.imgfile[0])
        if os.path.exists(self.path): 
            self.dlg.pbLucky.setEnabled(True)
        
    def displayDirMetadata(self):
        if self.dlg.rbRapideye.isChecked():
            self.dlg.leMetadata.setText(QFileDialog.getOpenFileName(self.dlg,
                                                                    u'RapidEye Metadata',
                                                                    self.path,
                                                                    'XML file (*.xml)'))
        elif self.dlg.rbSpot.isChecked():
            self.dlg.leMetadata.setText(QFileDialog.getOpenFileName(self.dlg,
                                                                    u'Spot Metadata',
                                                                    self.path,
                                                                    "DIMAP file (*.dim)"))
        elif self.dlg.rbLandsat.isChecked():
            self.dlg.leMetadata.setText(QFileDialog.getOpenFileName(self.dlg,
                                                                    u'Spot Metadata',
                                                                    self.path,
                                                                    "MTL file (*.txt)"))
        else:
            self.bar.pushMessage("Info", "Select an instrument before loading satellite image", level=QgsMessageBar.WARNING, duration=3)
        self.metafile = self.dlg.leMetadata.text()
        self.path = os.path.dirname(self.metafile)

    def autoLoadMetadata(self):
        if self.dlg.rbRapideye.isChecked():
            try:
                idfile = self.imgfile[0].split('LA93_')[1].rsplit('_',1)[0]
                idlist = glob.glob(os.path.join(os.path.dirname(self.imgfile[0]),'%s*.xml' %(idfile)))
                self.metafile = idlist[0]
                self.dlg.leMetadata.setText(self.metafile)
            except IndexError:
                self.bar.pushMessage("Info", "Can't find RapidEye metadata file", level=QgsMessageBar.WARNING, duration=3)
        elif self.dlg.rbSpot.isChecked():
            self.metafile = os.path.join(os.path.dirname(self.imgfile[0]), 'metadata.dim')
            if os.path.exists(self.metafile):
                self.dlg.leMetadata.setText(self.metafile)
            else:
                self.bar.pushMessage("Info", "Can't find Spot 5 metadata file", level=QgsMessageBar.WARNING, duration=3)
        elif self.dlg.rbLandsat.isChecked():
            idfile = os.path.basename(self.imgfile[0]).split('_')[0]
            self.metafile = os.path.join(os.path.dirname(self.imgfile[0]),'%s_MTL.txt' %(idfile))
            if os.path.exists(self.metafile):
                self.dlg.leMetadata.setText(self.metafile)
            else:
                self.bar.pushMessage("Info", "Can't find Landsat 8 metadata file", level=QgsMessageBar.WARNING, duration=3)

    def displayMetadata(self):
        try:
            print self.metafile
            self.bar.pushMessage("Metadata parsing... Wait please...", level=QgsMessageBar.INFO)
            time.sleep(1)
            self.dlg.teParam.append('===<br><b>image:</b>')
            self.dlg.teParam.append((''.join(['%s<br>'] * len(self.imgfile))) %tuple([os.path.basename(i) for i in self.imgfile]))
            self.dlg.teParam.append('<b>metadata:</b> %s<br>---' %(os.path.basename(self.metafile)))

            if self.dlg.rbRapideye.isChecked():
                self.meta = rapideye.RapidEye(self.metafile)
                self.dlg.teParam.append('<b>band index:</b><br> 1: blue, 2: green, 3: red, 4: rededge, 5: nir<br>---' )
            elif self.dlg.rbSpot.isChecked():
                self.meta = spot.Spot5(self.metafile)
                self.dlg.teParam.append('<b>band index:</b><br> 1: nir, 2: red, 3: green, 4: swir<br>---' )
            elif self.dlg.rbLandsat.isChecked():
                self.meta = ldcm.Landsat8(self.metafile)
                self.dlg.teParam.append('<b>band index:</b><br> 1: coastal/aerosol, 2: blue, 3: green,\
                                        4: red, 5: nir, 5: swir1, 7: swir2, 8: pan, 9: cirrus<br>---' )
            self.meta.getGain()
            self.meta.getSolarAngle()
            self.meta.getDistEarthSun()
            self.meta.getSolarIrrad()
            self.dlg.teParam.append('<b>gain:</b>')
            self.dlg.teParam.append((''.join(['%s<br>'] * len(self.meta.gain))) %tuple(self.meta.gain))
            try:
                self.dlg.teParam.append('<b>offset:</b>')
                self.dlg.teParam.append((''.join(['%s<br>'] * len(self.meta.add))) %tuple(self.meta.add))
            except AttributeError:
                pass
            self.dlg.teParam.append('<b>solar zenithal angle:</b><br> %s<br>' %(self.meta.solarZAngle))
            self.dlg.teParam.append('<b>Earth-Sun distance:</b><br> %s<br>' %(self.meta.distEarthSun))
            self.dlg.teParam.append('<b>solar irradiance:</b>')
            self.dlg.teParam.append((''.join(['%s<br>'] * len(self.meta.eSun))) %tuple(self.meta.eSun))
            self.dlg.cbOutput.setEnabled(True)
            self.dlg.pbConvert.setEnabled(True)
            self.bar.clearWidgets()
        except AttributeError:
            self.bar.clearWidgets()
            self.bar.pushMessage("Info", "Metadata file required", level=QgsMessageBar.WARNING, duration=3)
        except (KeyError, IndexError):
            self.bar.clearWidgets()
            self.bar.pushMessage("Info", "Problem with the input image file or metadata file", level=QgsMessageBar.WARNING, duration=5)

    def processToa(self):
        self.bar.pushMessage("DN to TOA... Wait please...", level=QgsMessageBar.INFO, duration=3)
        time.sleep(1) 
        if self.dlg.cbOutput.isChecked() and os.path.exists(self.outputPath):
            outpath = self.outputPath
        else:
            outpath = os.path.dirname(self.imgfile[0])
        if self.dlg.rbRefNorm.isChecked():
            bitcode = '32'
            outname = '_refToa32.tif'
        elif self.dlg.rbRefMilli.isChecked():
            bitcode = '16'
            outname = '_refToa16.tif'
        time.sleep(1)
        startTime = time.time()
        if self.dlg.rbRapideye.isChecked() or self.dlg.rbSpot.isChecked():
            self.meta.reflectanceToa(self.imgfile[0],outname=outname,bitcode=bitcode,outpath=outpath)
        elif self.dlg.rbLandsat.isChecked():
            self.meta.reflectanceToa(self.imgfile,outname=outname,bitcode=bitcode,outpath=outpath)
        endTime = time.time()
        self.dlg.teParam.append('===<br><b>image converted in TOA reflectance !</b>')
        self.dlg.teParam.append('<b>processing duration:</b><br> %s seconds' %(endTime-startTime))
        self.dlg.teParam.append('<b>output file directory:</b><br> %s<br>===' %(outpath))

        self.bar.clearWidgets()
        self.bar.pushMessage("Image processed !", level=QgsMessageBar.INFO, duration=3)

    def activeOutputDir(self):
        if self.dlg.cbOutput.isChecked():
            self.dlg.pbOutput.setEnabled(True)
            self.dlg.leOutput.setEnabled(True)
        else:
            self.dlg.pbOutput.setEnabled(False)
            self.dlg.leOutput.setEnabled(False)
        
    def outputDir(self):
        self.dlg.leOutput.setText(QFileDialog.getExistingDirectory(self.dlg,
                                                                   u'Output directory',
                                                                   self.path))
        self.outputPath = self.dlg.leOutput.text()
        
    def uncheckRadio(self):
        self.dlg.groupInstrument.setExclusive(False)
        self.dlg.rbSpot.setChecked(False)
        self.dlg.rbRapideye.setChecked(False)
        self.dlg.rbLandsat.setChecked(False)
        self.dlg.groupInstrument.setExclusive(True)
        self.dlg.rbRefNorm.setChecked(True)
        self.dlg.pbConvert.setEnabled(False)
        self.dlg.pbOutput.setEnabled(False)
        self.dlg.leOutput.setEnabled(False)
        self.dlg.pbLucky.setEnabled(False)
        self.dlg.cbOutput.setEnabled(False)

    def clearFields(self):
        self.dlg.leInput.clear()
        self.dlg.leMetadata.clear()
        self.dlg.teParam.clear()

    def helpFile(self):
        showPluginHelp()

    # run method that performs all the real work
    def run(self):
        # show the dialog   
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        print 'result %s' %(result)
        # See if 'Cancel [x]' was pressed
        if result == 0:
            if hasattr(self,'metafile'):
                del self.metafile
            self.clearFields()
            self.uncheckRadio()
            self.bar.clearWidgets()
            # do something useful (delete the line containing pass and
            # substitute with your code)            
            pass
