
"""
/***************************************************************************
 entf_besch
                                 A QGIS plugin
 Bescheinigung nach Entfernung
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-11-16
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Marius Schaefer
        email                : marius.schaefer@kreis-unna.de
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
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .entf_besch_dialog import entf_beschDialog
import os.path
import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog, QApplication, QFileDialog
from qgis.core import *
from qgis.utils import iface
from qgis.gui import QgsMapTool,QgsMapToolPan
import requests #um POST an ORS zu schicken
from pyproj import Proj, transform #Projektion von 25832 zu 4326 für ORS
import json #response ORS-API als geoJSON speichern

class SendPointToolCoordinates(QgsMapTool):
    """ Catches the coordinates from a click on a layer and displays them in a UI element
    """
    def __init__(self, canvas, window, label):
        """ Constructor.
        """
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.window = window # where we'll show the coordinates
        self.label = label
        self.setCursor(Qt.CrossCursor)
        window.hide()
    """ Wird aufgerufen, wenn mit der Maus in den Map-Canvas geklickt wird.
    """
    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.label.setText(str(point.x())+", "+str(point.y()))
        self.window.show()

class entf_besch:
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
            'entf_besch_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = u'&entfernungebscheinigung'

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None


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
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/entf_besch/icon.png'
        self.add_action(
            icon_path,
            text=u'Entfernungebscheinigung',
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                u'&entfernungebscheinigung',
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = entf_beschDialog()

            canvas = self.iface.mapCanvas()

            def getStartpoint():
                send_point_tool_coordinates= SendPointToolCoordinates(canvas,self.dlg, self.dlg.startpointlabel)
                canvas.setMapTool(send_point_tool_coordinates)

            def getEndpoint():
                send_point_tool_coordinates= SendPointToolCoordinates(canvas,self.dlg, self.dlg.endpointlabel)
                canvas.setMapTool(send_point_tool_coordinates)

            def calculateRoute():
                """Nachricht ausgeben, dass etwas passiert"""
                self.iface.messageBar().pushMessage("Plugin:", "Entfernungbescheinigung wird erstellt!", level=Qgis.Info,duration=3)

                """vordefinierte Objekte"""
                project  = QgsProject.instance()
                filepath = self.dlg.savedirectory.text()
                filename = self.dlg.proj_name.text()

                """Radio-Button Auswahl abholen, speichern in Variable für request an ORS-API"""
                if self.dlg.car.isChecked():
                    routeuser = "driving-car"
                elif self.dlg.pedestrian.isChecked():
                    routeuser = "foot-walking"

                """hard coded EPSG für Transformation"""
                inProj = Proj('epsg:25832')
                qgsInProj = QgsCoordinateReferenceSystem('epsg:25832')
                outProj = Proj('epsg:4326')
                qgsOutProj= QgsCoordinateReferenceSystem('epsg:4326')

                """Text aus dem GUI abholen -> str"""
                startpoint = self.dlg.startpointlabel.text()
                endpoint = self.dlg.endpointlabel.text()

                """aufteilen des string in x,y-Koordinaten"""
                s = startpoint.split(",")
                e = endpoint.split(",")

                """Startpunkt als Layer importieren zur Visualisierung"""
                startpointVis = QgsPoint(float(s[0]),float(s[1]))

                """Endpunkt für Layer importieren zur Visualisierung abgreifen"""
                endpointVis = QgsPoint(float(e[0]),float(e[1]))

                """transformation von ETRS89/utm zu WGS84 für ORS"""
                print(s)
                s[0],s[1]= transform(inProj,outProj,s[0],s[1])
                print(s)
                s=s[1],s[0]
                print(s)
                e[0],e[1]= transform(inProj,outProj,e[0],e[1])
                e=e[1],e[0]#Koordinaten wurden durch Trafo vertauscht, Format: "long,lat" gefordert

                points=s,e
                API_ENDPOINT ="https://api.openrouteservice.org/v2/directions/"+routeuser+"/geojson"

                headers = {
                    'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
                    'Authorization': '5b3ce3597851110001cf62481faa0b5ae2c142368bfdfffef95ee6a1',
                    'Content-Type': 'application/json; charset=utf-8'
                }

                body={"coordinates":points}

                response = requests.post(API_ENDPOINT,json=body, headers=headers)
                print(response)
                routeastext = response.text
                print(routeastext)

                """response als geojson speichern"""
                jsonroute = json.loads(routeastext)
                json.dump(jsonroute, open(filepath+'/'+filename+'.geojson','w'))

                """Anzahl der Straßen auf Route"""
                anzahlstrassennamen = len(jsonroute['features'][0]['properties']['segments'][0]['steps'])

                """auslesen aus geoJSON """
                strassennamenliste=[]
                for x in range(anzahlstrassennamen-1):
                    strassennamenliste.append(jsonroute['features'][0]['properties']['segments'][0]['steps'][x]['name'])

                """Duplikate entfernen (Umwandlung in Dictionary)"""
                strassennamenliste = list(dict.fromkeys(strassennamenliste))

                """Längenausgabe"""
                laenge=jsonroute['features'][0]['properties']['segments'][0]['distance']

                """Route zur Karte hinzufügen"""
                self.iface.addVectorLayer(filepath+'/'+filename+'.geojson','','ogr')
                route = self.iface.activeLayer()

                """Startpunkt als Layer importieren zur Visualisierung"""
                startpointLayer = QgsVectorLayer("Point", filename+"Startpunkt", "memory")
                pr = startpointLayer.dataProvider()

                """Layer in EditModus setzen"""
                startpointLayer.startEditing()
                """Felder hinzufügen"""
                pr.addAttributes([])
                """Feature hinzufügen"""
                fet = QgsFeature()
                fet.setGeometry( startpointVis )
                pr.addFeatures( [ fet ] )
                # Commit changes
                startpointLayer.commitChanges()
                startpointLayerProj = QgsCoordinateReferenceSystem('epsg:25832')
                startpointLayer.setCrs(startpointLayerProj)
                project.addMapLayer(startpointLayer)
                startpointLayer.renderer().symbol().setColor(QColor(0,225,0))
                self.iface.mapCanvas().refresh()
                """Endpunkt als Layer importieren zur Visualisierung"""
                endpointLayer = QgsVectorLayer("Point", filename+"Endpunkt", "memory")

                pr = endpointLayer.dataProvider()

                """Layer in EditModus setzen"""
                endpointLayer.startEditing()
                """Felder hinzufügen"""
                pr.addAttributes([])
                """Feature hinzufügen"""
                fet = QgsFeature()
                fet.setGeometry( endpointVis )
                pr.addFeatures( [ fet ] )
                # Commit changes
                endpointLayer.commitChanges()
                endpointLayerProj = QgsCoordinateReferenceSystem('epsg:25832')
                endpointLayer.setCrs(endpointLayerProj)
                project.addMapLayer(endpointLayer)
                endpointLayer.renderer().symbol().setColor(QColor(225,0,0))
                self.iface.mapCanvas().refresh()


                """Symbolisierung Route"""
                route.renderer().symbol().setWidth(0.8)
                route.renderer().symbol().setColor(QColor(0,225,0))
                route.triggerRepaint()

                """Printlayout mit Namen als Eingabe aus GUI erstellen"""
                manager = project.layoutManager()
                layout = QgsPrintLayout(project)

                layout.initializeDefaults()

                """Namen vergeben und zum Layoutmanager hinzufügen"""
                layoutname = self.dlg.proj_name.text()
                layout.setName(layoutname)
                manager.addLayout(layout)

                """zweite Seite hinzufügen"""
                page = QgsLayoutItemPage(layout)
                page.setPageSize('A4',QgsLayoutItemPage.Portrait)
                layout.pageCollection().addPage(page)


                """Drucklayout Gestaltung"""
                """(Seite 1)Überschrift"""
                headLabel = "Entfernungebscheinigung"
                headp1 = QgsLayoutItemLabel(layout)
                headp1.setText(headLabel)
                headp1.setFont(QFont("Arial",18))
                headp1.adjustSizeToText()
                layout.addLayoutItem(headp1)
                headp1.attemptMove(QgsLayoutPoint(10,10))

                """(Seite 1) Logo """
                #logo = QgsLayoutItemPicture(layout)
                #logo.setMode(QgsLayoutItemPicture.FormatRaster)
                #logo.setPicturePath(self.plugin_dir+"/pfad")
                #logo.attemptResize(QgsLayoutSize(15,15), QgsUnitTypes.LayoutMillimeters)
                #logo.attemptMove(QgsLayoutPoint(273,7),0)
                #layout.addLayoutItem(logo)

                """ (Seite 1) Hauptkarte zum Layout hinzufügen"""
                map = QgsLayoutItemMap(layout)
                ext = route.extent()

                """ (Seite 1) Transformation des Extent von 4326 zu 25832 """
                inProj = 'epsg:4326'
                outProj = 'epsg:25832'
                ymin,xmin = transform(inProj,outProj,ext.yMinimum(),ext.xMinimum())
                ymax,xmax = transform(inProj,outProj,ext.yMaximum(),ext.xMaximum())
                rectangle = QgsRectangle(ymin,xmin,ymax,xmax)
                map.attemptResize(QgsLayoutSize(200,175, QgsUnitTypes.LayoutMillimeters))
                map.attemptMove(QgsLayoutPoint(10,25))
                map.zoomToExtent(rectangle)
                massstab =map.scale()
                map.setScale(massstab+500)
                map.setFrameEnabled(True)
                layout.addLayoutItem(map)

                """(Seite 1) Nebenkarte für Startpunkt hinzufügen"""
                mapStart = QgsLayoutItemMap(layout)
                mapStart.attemptResize(QgsLayoutSize(70,70, QgsUnitTypes.LayoutMillimeters))
                mapStart.attemptMove(QgsLayoutPoint(218,25))
                ymin,xmin,ymax,xmax = startpointVis.y()-35,startpointVis.x()-35,startpointVis.y()+35,startpointVis.x()+35
                rectangleStart = QgsRectangle(xmin,ymin,xmax,ymax)
                mapStart.zoomToExtent(rectangleStart)
                mapStart.setFrameEnabled(True)
                layout.addLayoutItem(mapStart)

                """(Seite 1) Nebenkarte für Endpuntk hinzufügen"""
                mapEnd = QgsLayoutItemMap(layout)
                mapEnd.attemptResize(QgsLayoutSize(70,70, QgsUnitTypes.LayoutMillimeters))
                mapEnd.attemptMove(QgsLayoutPoint(218,100))
                ymin,xmin,ymax,xmax = endpointVis.y()-35,endpointVis.x()-35,endpointVis.y()+35,endpointVis.x()+35
                rectangleEnd = QgsRectangle(xmin,ymin,xmax,ymax)
                mapEnd.zoomToExtent(rectangleEnd)
                mapEnd.setFrameEnabled(True)
                layout.addLayoutItem(mapEnd)

                """(Seite 2)Überschirft 2. Seite """
                headp2 = QgsLayoutItemLabel(layout)
                headp2.setText(headLabel)
                headp2.setFont(QFont("Arial",18))
                headp2.adjustSizeToText()
                layout.addLayoutItem(headp2)
                headp2.attemptMove(QgsLayoutPoint(10,10), page= 1)

                """(Seite 1) Logo """
                #logo2 = QgsLayoutItemPicture(layout)
                #logo2.setMode(QgsLayoutItemPicture.FormatRaster)
                #logo2.setPicturePath(self.plugin_dir+"/pfad")
                #logo2.attemptResize(QgsLayoutSize(15,15), QgsUnitTypes.LayoutMillimeters)
                #logo2.attemptMove(QgsLayoutPoint(185,7),page = 1)
                #layout.addLayoutItem(logo2)

                """(Seite 2)Angabe zu über """
                ueberLabel = QgsLayoutItemLabel(layout)
                ueberLabel.setText("Die Straßen die bei 'über' aufgeführt werden, können nur sehr kleine Streckenanteile haben." )
                ueberLabel.setFont(QFont("Arial",12))
                ueberLabel.adjustSizeToText()
                layout.addLayoutItem(ueberLabel)
                ueberLabel.attemptMove(QgsLayoutPoint(10,30), page=1)

                """(Seite 2)Startadresse abholen """
                startadress = self.dlg.startadress.text()
                startadressLabel = QgsLayoutItemLabel(layout)
                startadressLabel.setText("von: "+startadress)
                startadressLabel.setFont(QFont("Arial Black",12))
                startadressLabel.adjustSizeToText()
                layout.addLayoutItem(startadressLabel)
                startadressLabel.attemptMove(QgsLayoutPoint(10,40), page=1)

                """(Seite2)strassennamenliste als Tabelle zum Drucklayout hinzufügen"""
                table = QgsLayoutItemTextTable(layout)
                layout.addMultiFrame(table)

                cols = [QgsLayoutTableColumn()]
                cols[0].setHeading("über:")
                table.setColumns(cols)

                for i in strassennamenliste:
                    table.addRow([i])

                frame = QgsLayoutFrame(layout, table)
                frame.attemptResize(QgsLayoutSize(100, 175), True)
                table.addFrame(frame)
                table.setContentFont(QFont("Arial",12))
                table.setHeaderFont(QFont("Arial",12))
                frame.attemptMove(QgsLayoutPoint(10,55),page=1)
                frame.setFrameEnabled(False)

                """(Seite 2)Endadresse abholen """
                endadress = self.dlg.endadress.text()

                endadressLabel = QgsLayoutItemLabel(layout)
                endadressLabel.setText("nach: "+endadress)
                endadressLabel.setFont(QFont("Arial Black",12))
                endadressLabel.adjustSizeToText()
                layout.addLayoutItem(endadressLabel)
                endadressLabel.attemptMove(QgsLayoutPoint(10,250), page=1)

                """(Seite 2)Laengenangabe in Metern"""
                laengeMeterLabel = QgsLayoutItemLabel(layout)
                laengeMeterLabel.setText("Gesamtlänge des Weges (Meter): ")
                laengeMeterLabel.setFont(QFont("Arial",15))
                laengeMeterLabel.adjustSizeToText()
                layout.addLayoutItem(laengeMeterLabel)
                laengeMeterLabel.attemptMove(QgsLayoutPoint(10,265), page=1)

                laengeMeterLabelNum = QgsLayoutItemLabel(layout)
                laengeMeterLabelNum.setText(str(laenge)[:-2])
                laengeMeterLabelNum.setFont(QFont("Arial Black",15))
                laengeMeterLabelNum.adjustSizeToText()
                layout.addLayoutItem(laengeMeterLabelNum)
                laengeMeterLabelNum.attemptMove(QgsLayoutPoint(110,264), page=1) #einen mm höher wegen fetter Schrift

                """(Seite 2)Laengenangabe in Kilometern"""
                laengeKilometerLabel = QgsLayoutItemLabel(layout)
                laengeKilometerLabel.setText("Gesamtlänge des Weges (Kilometer): ")
                laengeKilometerLabel.setFont(QFont("Arial",15))
                laengeKilometerLabel.adjustSizeToText()
                layout.addLayoutItem(laengeKilometerLabel)
                laengeKilometerLabel.attemptMove(QgsLayoutPoint(10,275), page=1)

                laengeKilometerLabelNum = QgsLayoutItemLabel(layout)
                laengeKilometerLabelNum.setText(str(round((laenge/1000),1)))
                laengeKilometerLabelNum.setFont(QFont("Arial Black",15))
                laengeKilometerLabelNum.adjustSizeToText()
                layout.addLayoutItem(laengeKilometerLabelNum)
                laengeKilometerLabelNum.attemptMove(QgsLayoutPoint(110,274), page=1)#einen mm höher wegen fetter Schrift

                """Layout-Export an anegegebenen Pfad"""

                layout = manager.layoutByName(layoutname)
                layoutname = filepath+layout.name()
                exporter = QgsLayoutExporter(layout)
                exporter.exportToPdf(filepath+"/"+layout.name()+".pdf", QgsLayoutExporter.PdfExportSettings())



            self.dlg.startpoint.clicked.connect(getStartpoint)

            self.dlg.endpoint.clicked.connect(getEndpoint)

            """Namen für Drucklayout/Route abholen
            Pfad zum ablegen von Drucklayout/Route"""


            savepath=self.dlg.savedirectory
            def getSaveDirectory():
                filepath = QFileDialog.getExistingDirectory(None, "Pfade", "/home")
                savepath.setText(filepath)
            self.dlg.browse.clicked.connect(getSaveDirectory)

            """bei Plugin-Aufruf -> CRS auf 25832 setzen
            wichtig für spätere Transformation (hard coded EPSG Trafo von 25832 -> 4326)"""
            QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(25832))

            """ ausführen der Haputmethode, wenn das Fenster mit OK geschlossen wird """
            self.dlg.accepted.connect(calculateRoute)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
