# -*- coding: utf-8 -*-
"""QGIS Unit tests for QgsPalLabeling: base suite setup

From build dir: ctest -R PyQgsPalLabelingBase -V
Set the following env variables when manually running tests:
  PAL_SUITE to run specific tests (define in __main__)
  PAL_VERBOSE to output individual test summary
  PAL_CONTROL_IMAGE to trigger building of new control images
  PAL_REPORT to open any failed image check reports in web browser

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
__author__ = 'Larry Shaffer'
__date__ = '07/09/2013'
__copyright__ = 'Copyright 2013, The QGIS Project'
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import os
import sys
import datetime
import glob
import shutil
import StringIO
import tempfile
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import (
    QGis,
    QgsCoordinateReferenceSystem,
    QgsDataSourceURI,
    QgsLabelingEngineInterface,
    QgsMapLayerRegistry,
    QgsMapRenderer,
    QgsMapSettings,
    QgsPalLabeling,
    QgsPalLayerSettings,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorLayer,
    QgsRenderChecker
)

from utilities import (
    getQgisTestApp,
    TestCase,
    unittest,
    unitTestDataPath,
    loadTestFonts,
    getTestFont,
    openInBrowserTab
)

QGISAPP, CANVAS, IFACE, PARENT = getQgisTestApp()
FONTSLOADED = loadTestFonts()

PALREPORT = 'PAL_REPORT' in os.environ
PALREPORTS = {}


# noinspection PyPep8Naming,PyShadowingNames
class TestQgsPalLabeling(TestCase):

    _TestDataDir = unitTestDataPath()
    _PalDataDir = os.path.join(_TestDataDir, 'labeling')
    _PalFeaturesDb = os.path.join(_PalDataDir, 'pal_features_v3.sqlite')
    _TestFont = getTestFont()  # Roman at 12 pt
    """:type: QFont"""
    _MapRegistry = None
    """:type: QgsMapLayerRegistry"""
    _MapRenderer = None
    """:type: QgsMapRenderer"""
    _MapSettings = None
    """:type: QgsMapSettings"""
    _Canvas = None
    """:type: QgsMapCanvas"""
    _Map = None
    """:type: QgsMapCanvasMap"""
    _Pal = None
    """:type: QgsPalLabeling"""
    _PalEngine = None
    """:type: QgsLabelingEngineInterface"""

    @classmethod
    def setUpClass(cls):
        """Run before all tests"""

        # qgis instances
        cls._QgisApp, cls._Canvas, cls._Iface, cls._Parent = \
            QGISAPP, CANVAS, IFACE, PARENT

        # verify that spatialite provider is available
        msg = '\nSpatialite provider not found, SKIPPING TEST SUITE'
        # noinspection PyArgumentList
        res = 'spatialite' in QgsProviderRegistry.instance().providerList()
        assert res, msg

        cls._TestFunction = ''
        cls._TestGroup = ''
        cls._TestGroupPrefix = ''
        cls._TestGroupAbbr = ''
        cls._TestImage = ''

        # initialize class MapRegistry, Canvas, MapRenderer, Map and PAL
        # noinspection PyArgumentList
        cls._MapRegistry = QgsMapLayerRegistry.instance()
        # set color to match render test comparisons background
        cls._Canvas.setCanvasColor(QColor(152, 219, 249))
        cls._Map = cls._Canvas.map()
        cls._Map.resize(QSize(600, 400))  # is this necessary now?
        cls._MapRenderer = cls._Canvas.mapRenderer()

        cls._MapSettings = QgsMapSettings()
        cls._CRS = QgsCoordinateReferenceSystem()
        """:type: QgsCoordinateReferenceSystem"""
        # default for labeling test data sources: WGS 84 / UTM zone 13N
        cls._CRS.createFromSrid(32613)
        cls._MapSettings.setBackgroundColor(QColor(152, 219, 249))
        cls._MapSettings.setOutputSize(QSize(600, 400))
        cls._MapSettings.setOutputDpi(72)
        cls._MapSettings.setFlag(QgsMapSettings.Antialiasing)
        cls._MapSettings.setDestinationCrs(cls._CRS)
        cls._MapSettings.setCrsTransformEnabled(False)
        cls._MapSettings.setMapUnits(cls._CRS.mapUnits())  # meters
        cls._MapSettings.setExtent(cls.aoiExtent())

        cls.setDefaultEngineSettings()
        msg = ('\nCould not initialize PAL labeling engine, '
               'SKIPPING TEST SUITE')
        assert cls._PalEngine, msg

    @classmethod
    def setDefaultEngineSettings(cls):
        """Restore default settings for pal labelling"""
        cls._Pal = QgsPalLabeling()
        cls._MapRenderer.setLabelingEngine(cls._Pal)
        cls._PalEngine = cls._MapRenderer.labelingEngine()

    @classmethod
    def tearDownClass(cls):
        """Run after all tests"""
        cls.removeAllLayers()

    @classmethod
    def removeAllLayers(cls):
        cls._MapRegistry.removeAllMapLayers()

    @classmethod
    def getTestFont(cls):
        return QFont(cls._TestFont)

    @classmethod
    def loadFeatureLayer(cls, table):
        uri = QgsDataSourceURI()
        uri.setDatabase(cls._PalFeaturesDb)
        uri.setDataSource('', table, 'geometry')
        vlayer = QgsVectorLayer(uri.uri(), table, 'spatialite')
        # .qml should contain only style for symbology
        vlayer.loadNamedStyle(os.path.join(cls._PalDataDir,
                                           '{0}.qml'.format(table)))
        cls._MapRegistry.addMapLayer(vlayer)
        # place new layer on top of render stack
        render_lyrs = [vlayer.id()] + list(cls._MapSettings.layers())
        cls._MapSettings.setLayers(render_lyrs)

        # zoom to aoi
        cls._MapSettings.setExtent(cls.aoiExtent())
        cls._Canvas.zoomToFullExtent()
        return vlayer

    @classmethod
    def aoiExtent(cls):
        """Area of interest extent, which matches output aspect ratio"""
        uri = QgsDataSourceURI()
        uri.setDatabase(cls._PalFeaturesDb)
        uri.setDataSource('', 'aoi', 'geometry')
        aoilayer = QgsVectorLayer(uri.uri(), 'aoi', 'spatialite')
        return aoilayer.extent()

    def configTest(self, prefix, abbr):
        """Call in setUp() function of test subclass"""
        self._TestGroupPrefix = prefix
        self._TestGroupAbbr = abbr

        # insert test's Class.function marker into debug output stream
        # this helps visually track down the start of a test's debug output
        testid = self.id().split('.')
        self._TestGroup = testid[1]
        self._TestFunction = testid[2]
        testheader = '\n#####_____ {0}.{1} _____#####\n'.\
            format(self._TestGroup, self._TestFunction)
        qDebug(testheader)

        # define the shorthand name of the test (to minimize file name length)
        self._Test = '{0}_{1}'.format(self._TestGroupAbbr,
                                      self._TestFunction.replace('test_', ''))

    def defaultSettings(self):
        lyr = QgsPalLayerSettings()
        lyr.enabled = True
        lyr.fieldName = 'text'  # default in data sources
        font = self.getTestFont()
        font.setPointSize(48)
        lyr.textFont = font
        lyr.textNamedStyle = 'Roman'
        return lyr

    @staticmethod
    def settingsDict(lyr):
        """Return a dict of layer-level labeling settings

        .. note:: QgsPalLayerSettings is not a QObject, so we can not collect
        current object properties, and the public properties of the C++ obj
        can't be listed with __dict__ or vars(). So, we sniff them out relative
        to their naming convention (camelCase), as reported by dir().
        """
        res = {}
        for attr in dir(lyr):
            if attr[0].islower() and not attr.startswith("__"):
                value = getattr(lyr, attr)
                if not callable(value):
                    res[attr] = value
        return res

    def saveContolImage(self, tmpimg=''):
        # don't save control images for RenderVsOtherOutput (Vs) tests, since
        # those control images belong to a different test result
        if ('PAL_CONTROL_IMAGE' not in os.environ
                or 'Vs' in self._TestGroup):
            return
        testgrpdir = 'expected_' + self._TestGroupPrefix
        testdir = os.path.join(self._TestDataDir, 'control_images',
                               testgrpdir, self._Test)
        if not os.path.exists(testdir):
            os.makedirs(testdir)
        imgbasepath = os.path.join(testdir, self._Test)
        imgpath = imgbasepath + '.png'
        for f in glob.glob(imgbasepath + '.*'):
            if os.path.exists(f):
                os.remove(f)
        if tmpimg:
            if os.path.exists(tmpimg):
                shutil.copyfile(tmpimg, imgpath)
        else:
            self._Map.render()
            self._Canvas.saveAsImage(imgpath)
            # delete extraneous world file (always generated)
            wrld_file = imgbasepath + '.PNGw'
            if os.path.exists(wrld_file):
                os.remove(wrld_file)

    def renderCheck(self, mismatch=0, imgpath='', grpprefix=''):
        """Check rendered map canvas or existing image against control image

        mismatch: number of pixels different from control, and still valid check
        imgpath: existing image; if present, skips rendering canvas
        grpprefix: compare test image/rendering against different test group
        """
        if not grpprefix:
            grpprefix = self._TestGroupPrefix
        chk = QgsRenderChecker()
        chk.setControlPathPrefix('expected_' + grpprefix)
        chk.setControlName(self._Test)
        chk.setMapSettings(self._MapSettings)
        # noinspection PyUnusedLocal
        res = False
        if imgpath:
            res = chk.compareImages(self._Test, mismatch, str(imgpath))
        else:
            res = chk.runTest(self._Test, mismatch)
        if PALREPORT and not res:  # don't report ok checks
            testname = self._TestGroup + ' . ' + self._Test
            PALREPORTS[testname] = str(chk.report().toLocal8Bit())
        msg = '\nRender check failed for "{0}"'.format(self._Test)
        return res, msg


class TestPALConfig(TestQgsPalLabeling):

    @classmethod
    def setUpClass(cls):
        TestQgsPalLabeling.setUpClass()
        cls.layer = TestQgsPalLabeling.loadFeatureLayer('point')

    def setUp(self):
        """Run before each test."""
        self.configTest('pal_base', 'base')

    def tearDown(self):
        """Run after each test."""
        pass

    def test_default_pal_disabled(self):
        # Verify PAL labeling is disabled for layer by default
        palset = self.layer.customProperty('labeling', '').toString()
        msg = '\nExpected: Empty string\nGot: {0}'.format(palset)
        self.assertEqual(palset, '', msg)

    def test_settings_enable_pal(self):
        # Verify default PAL settings enable PAL labeling for layer
        lyr = QgsPalLayerSettings()
        lyr.writeToLayer(self.layer)
        palset = self.layer.customProperty('labeling', '').toString()
        msg = '\nExpected: Empty string\nGot: {0}'.format(palset)
        self.assertEqual(palset, 'pal', msg)

    def test_layer_pal_activated(self):
        # Verify, via engine, that PAL labeling can be activated for layer
        lyr = self.defaultSettings()
        lyr.writeToLayer(self.layer)
        msg = '\nLayer labeling not activated, as reported by labelingEngine'
        self.assertTrue(self._PalEngine.willUseLayer(self.layer), msg)

    def test_write_read_settings(self):
        # Verify written PAL settings are same when read from layer
        # load and write default test settings
        lyr1 = self.defaultSettings()
        lyr1dict = self.settingsDict(lyr1)
        # print lyr1dict
        lyr1.writeToLayer(self.layer)

        # read settings
        lyr2 = QgsPalLayerSettings()
        lyr2.readFromLayer(self.layer)
        lyr2dict = self.settingsDict(lyr1)
        # print lyr2dict

        msg = '\nLayer settings read not same as settings written'
        self.assertDictEqual(lyr1dict, lyr2dict, msg)

    def test_default_partials_labels_enabled(self):
        # Verify ShowingPartialsLabels is enabled for PAL by default
        pal = QgsPalLabeling()
        self.assertTrue(pal.isShowingPartialsLabels())

    def test_partials_labels_activate(self):
        pal = QgsPalLabeling()
         # Enable partials labels
        pal.setShowingPartialsLabels(True)
        self.assertTrue(pal.isShowingPartialsLabels())

    def test_partials_labels_deactivate(self):
        pal = QgsPalLabeling()
        # Disable partials labels
        pal.setShowingPartialsLabels(False)
        self.assertFalse(pal.isShowingPartialsLabels())


# noinspection PyPep8Naming,PyShadowingNames
def runSuite(module, tests):
    """This allows for a list of test names to be selectively run.
    Also, ensures unittest verbose output comes at end, after debug output"""
    loader = unittest.defaultTestLoader
    if 'PAL_SUITE' in os.environ:
        if tests:
            suite = loader.loadTestsFromNames(tests, module)
        else:
            raise Exception(
                "\n\n####__ 'PAL_SUITE' set, but no tests specified __####\n")
    else:
        suite = loader.loadTestsFromModule(module)
    verb = 2 if 'PAL_VERBOSE' in os.environ else 0

    out = StringIO.StringIO()
    res = unittest.TextTestRunner(stream=out, verbosity=verb).run(suite)
    if verb:
        print '\nIndividual test summary:'
    print '\n' + out.getvalue()
    out.close()

    if PALREPORTS:
        teststamp = 'PAL Test Report: ' + \
                    datetime.datetime.now().strftime('%Y-%m-%d %X')
        report = '<html><head><title>{0}</title></head><body>'.format(teststamp)
        report += '\n<h2>Failed Tests: {0}</h2>'.format(len(PALREPORTS))
        for k, v in PALREPORTS.iteritems():
            report += '\n<h3>{0}</h3>\n{1}'.format(k, v)
        report += '</body></html>'

        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
        tmp.write(report)
        tmp.close()
        openInBrowserTab('file://' + tmp.name)

    return res


if __name__ == '__main__':
    # NOTE: unless PAL_SUITE env var is set all test class methods will be run
    # ex: 'TestGroup(Point|Line|Curved|Polygon|Feature).test_method'
    suite = [
        'TestPALConfig.test_write_read_settings'
    ]
    res = runSuite(sys.modules[__name__], suite)
    sys.exit(not res.wasSuccessful())
