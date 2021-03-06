# -*- coding: utf-8 -*-
"""QGIS unit tests for QgsPalLabeling: label rendering via QGIS Server

From build dir: ctest -R PyQgsPalLabelingServer -V
Set the following env variables when manually running tests:
  PAL_SUITE to run specific tests (define in __main__)
  PAL_VERBOSE to output individual test summary
  PAL_CONTROL_IMAGE to trigger building of new control images
  PAL_REPORT to open any failed image check reports in web browser

  PAL_SERVER_TEMP to open the web server temp directory, instead of deleting

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

__author__ = 'Larry Shaffer'
__date__ = '07/12/2013'
__copyright__ = 'Copyright 2013, The QGIS Project'
# This will get replaced with a git SHA1 when you do a git archive
__revision__ = '$Format:%H$'

import sys
import os
import glob
import shutil
import tempfile
import time
from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from utilities import (
    unittest,
    expectedFailure,
)

from qgis_local_server import (
    QgisLocalServer,
    FcgiServerProcess,
    WebServerProcess,
    getLocalServer
)

from test_qgspallabeling_base import TestQgsPalLabeling, runSuite
from test_qgspallabeling_tests import (
    TestPointBase,
    suiteTests
)

MAPSERV = getLocalServer()


class TestServerBase(TestQgsPalLabeling):

    _TestProj = None
    """:type: QgsProject"""
    _TestProjName = ''

    @classmethod
    def setUpClass(cls):
        TestQgsPalLabeling.setUpClass()
        MAPSERV.startup()
        MAPSERV.web_dir_install(glob.glob(cls._PalDataDir + os.sep + '*.qml'))

        # noinspection PyArgumentList
        cls._TestProj = QgsProject.instance()
        cls._TestProjName = 'pal_test.qgs'
        cls._TestProj.setFileName(
            os.path.join(MAPSERV.web_dir(), cls._TestProjName))

        # the blue background (set via layer style) to match renderchecker's
        cls._BkgrdLayer = TestQgsPalLabeling.loadFeatureLayer('background')
        cls._CheckMismatch = 200  # default for server tests; mismatch expected
        cls._CheckGroup = ''  # default '' will check against server control

        settings = QSettings()
        # noinspection PyArgumentList
        cls._CacheDir = settings.value(
            "cache/directory", QgsApplication.qgisSettingsDirPath() + "cache")

    @classmethod
    def tearDownClass(cls):
        """Run after all tests"""
        TestQgsPalLabeling.tearDownClass()
        # layers removed, save empty project file
        cls._TestProj.write()
        if "PAL_SERVER_TEMP" in os.environ:
            MAPSERV.stop_processes()
            MAPSERV.open_temp_dir()
        else:
            MAPSERV.shutdown()

    def setUp(self):
        """Run before each test."""
        # web server stays up across all tests
        # MAPSERV.fcgi_server_process().stop()
        # self.deleteCache()

    # noinspection PyPep8Naming
    def deleteCache(self):
        for item in os.listdir(self._CacheDir):
            shutil.rmtree(os.path.join(self._CacheDir, item),
                          ignore_errors=True)

    # noinspection PyPep8Naming
    def defaultWmsParams(self, layername):
        return {
            'SERVICE': 'WMS',
            'VERSION': '1.3.0',
            'REQUEST': 'GetMap',
            'MAP': self._TestProjName,
            # layer stacking order for rendering: bottom,to,top
            'LAYERS': ['background', str(layername).strip()],  # or 'name,name'
            'STYLES': ',',
            # authid str or QgsCoordinateReferenceSystem obj
            'CRS': 'EPSG:32613',  # self._CRS
            'BBOX': '606510,4823130,612510,4827130',  # self.aoiExtent(),
            'FORMAT': 'image/png',  # or: 'image/png; mode=8bit'
            'WIDTH': '600',
            'HEIGHT': '400',
            'DPI': '72',
            'MAP_RESOLUTION': '72',
            'FORMAT_OPTIONS': 'dpi:72',
            'TRANSPARENT': 'FALSE',
            'IgnoreGetMapUrl': '1'
        }


class TestServerPoint(TestServerBase, TestPointBase):

    @classmethod
    def setUpClass(cls):
        TestServerBase.setUpClass()
        cls.layer = TestQgsPalLabeling.loadFeatureLayer('point')

    def setUp(self):
        """Run before each test."""
        self.configTest('pal_server', 'sp')
        TestQgsPalLabeling.setDefaultEngineSettings()
        self.lyr = self.defaultSettings()
        self.params = self.defaultWmsParams('point')
        self._TestImage = ''

    def tearDown(self):
        """Run after each test."""
        pass

    def checkTest(self, **kwargs):
        self.lyr.writeToLayer(self.layer)
        # save project file
        self._TestProj.write()
        # always restart FCGI before tests, so settings can be applied
        # MAPSERV.fcgi_server_process().start()
        # get server results
        # print self.params.__repr__()
        res_m, self._TestImage = MAPSERV.get_map(self.params, False)
        # print self._TestImage.__repr__()
        self.saveContolImage(self._TestImage)
        self.assertTrue(res_m, 'Failed to retrieve/save image from test server')
        # gp = kwargs['grpprefix'] if 'grpprefix' in kwargs else ''
        self.assertTrue(*self.renderCheck(mismatch=self._CheckMismatch,
                                          imgpath=self._TestImage,
                                          grpprefix=self._CheckGroup))


class TestServerVsCanvasPoint(TestServerPoint):

    @classmethod
    def setUpClass(cls):
        TestServerPoint.setUpClass()
        cls._CheckGroup = 'pal_canvas'


if __name__ == '__main__':
    # NOTE: unless PAL_SUITE env var is set all test class methods will be run
    # SEE: test_qgspallabeling_tests.suiteTests() to define suite
    suite = (
        ['TestServerPoint.' + t for t in suiteTests()['sp_suite']] +
        ['TestServerVsCanvasPoint.' + t for t in suiteTests()['sp_vs_suite']]
    )
    res = runSuite(sys.modules[__name__], suite)
    sys.exit(not res.wasSuccessful())
