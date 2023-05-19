# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GrdLoader
                                 A QGIS plugin
 Load GRD Format Rasters
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-05-11
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Mark Jessell
        email                : mark.jessell@uwa.edu.au
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
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QLineEdit
from qgis.core import QgsRasterLayer, QgsCoordinateReferenceSystem
from qgis.core import Qgis

import numpy as np
from osgeo import gdal, osr
import struct
import zlib
import os
import ntpath
from .geosoft_grid_parser import * 

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .GRD_Loader_dialog import GrdLoaderDialog
import os.path


class GrdLoader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GrdLoader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
            
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GRD_Loader')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GrdLoader', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToRasterMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/GRD_Loader/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'GRD Loader'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(
                self.tr(u'&GRD_Loader'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_input_file(self):
        filename, _filter = QFileDialog.getOpenFileName(
            self.dlg, "Select input file ","", '*.grd *.GRD')
        self.dlg.lineEdit.setText(filename)



    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = GrdLoaderDialog()
            self.dlg.pushButton.clicked.connect(self.select_input_file)

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            file_path = self.dlg.lineEdit.text()
            if(os.path.exists(file_path+'.xml')):
                epsg=extract_proj_str(file_path+'.xml')
                if(epsg== None):
                    if not self.dlg.lineEdit_2.text():
                        epsg=4326
                        self.iface.messageBar().pushMessage("No CRS found in XML, default to 4326", level=Qgis.Warning, duration=15)
                    else:
                        epsg = int(self.dlg.lineEdit_2.text())
                        self.iface.messageBar().pushMessage("CRS Read from manual input as "+str(epsg)+"", level=Qgis.Warning, duration=15)
                else:
                    self.iface.messageBar().pushMessage("CRS Read from XML as "+epsg+", manual input ignored", level=Qgis.Info, duration=15)
            else:
                try:
                    epsg = int(self.dlg.lineEdit_2.text())
                except:
                    epsg = 4326
                    self.iface.messageBar().pushMessage("No CRS Defined, assumed to be 4326", level=Qgis.Warning, duration=15)

            #read geosoft binary grid and return components
            #inputs:
                #file_path: path to geosoft grid (str)
                #epsg: EPSG projection ID (int)
            #returns:
                #header: header data (dict)
                #grid: grid data (2D array of float32)
                
            if(file_path !=''): 
                if(not os.path.exists(file_path)):
                    self.iface.messageBar().pushMessage("File: "+file_path+" not found", level=Qgis.Warning, duration=3)
                else:    
                    grid,header,Gdata_type=load_oasis_montaj_grid(file_path)
                    print(header)
                                    
                    path,name=ntpath.split(file_path)
                    fn='/vsimem/'+name[:-4]+'.tif'

                    driver=gdal.GetDriverByName('GTiff')
                    if(header["ordering"]==1):
                        ds = driver.Create(fn,xsize=header["shape_e"],ysize=header["shape_v"],bands=1,eType=Gdata_type)
                    else:
                        ds = driver.Create(fn,xsize=header["shape_v"],ysize=header["shape_e"],bands=1,eType=Gdata_type)

                    ds.GetRasterBand(1).WriteArray(grid)
                    geot=[header["x_origin"]-(header["spacing_e"]/2),
                        header["spacing_e"],
                        0,
                        header["y_origin"]-(header["spacing_v"]/2),
                        0,
                        header["spacing_e"],
                        ]
                    ds.SetGeoTransform(geot)
                    srs=osr.SpatialReference()

                    ds.SetProjection(srs.ExportToWkt())
                    ds=None
                    rlayer=self.iface.addRasterLayer(fn)
                    rlayer.setCrs( QgsCoordinateReferenceSystem('EPSG:'+str(epsg) ))
                    self.iface.messageBar().pushMessage("GRD file loaded as layer in memory, use export to save as file", level=Qgis.Success, duration=5)

            else:
                self.iface.messageBar().pushMessage("You need to select a file first", level=Qgis.Warning, duration=3)
