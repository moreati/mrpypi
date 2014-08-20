#
# Copyright (C) 2014 Craig Hobbs
#

import unittest

from mrpypi import MrPyPi


class TestApp(unittest.TestCase):

    def test_app(self):
        app = MrPyPi(None)
        self.assertTrue(app.index is None)
