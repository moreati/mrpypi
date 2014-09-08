#
# Copyright (C) 2014 Craig Hobbs
#

from collections import namedtuple
import unittest

from mrpypi import MrPyPi


TestIndexEntry = namedtuple('TestIndexEntry', ('name', 'version', 'filename', 'hash_name', 'hash'))

class TestIndex(object):

    def __init__(self):
        self._packages = [TestIndexEntry('package1', '1.0.0', 'package1-1.0.0.tar.gz', 'md5', '53bc481b565a8eb2bc72c0b4a66e9c44'),
                          TestIndexEntry('package1', '1.0.1', 'package1-1.0.1.tar.gz', 'md5', '53bc481b565a8eb2bc72c0b4a66e9c45'),
                          TestIndexEntry('package2', '1.0.0', 'package2-1.0.0.tar.gz', None, None),
                          TestIndexEntry('package2', '1.0.1', 'package2-1.0.1.tar.gz', None, None)]

    def getPackageIndex(self, ctx, packageName, forceUpdate = False):
        return [x for x in self._packages if x.name == packageName] or None

    def getPackageStream(self, ctx, packageName, version, filename):
        index = self.getPackageIndex(ctx, packageName)
        if index is None:
            return None
        indexEntry = next((x for x in index if x.version == version), None)
        if indexEntry is None:
            return None
        if indexEntry.filename != filename:
            return None
        def stream():
            yield packageName + '-' + version
        return stream

    def addPackage(self, ctx, packageName, version, filename, content):
        return True


class TestMrpypi(unittest.TestCase):

    def test_mrpypi_pypi_index(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/package1')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        self.assertEqual(content, '''\
<html>
<head>
<title>Links for package1</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for package1</h1>
<a href="../../pypi_download/package1/1.0.0/package1-1.0.0.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c44" rel="internal">../../pypi_download/package1/1.0.0/package1-1.0.0.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c44</a><br/>
<a href="../../pypi_download/package1/1.0.1/package1-1.0.1.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c45" rel="internal">../../pypi_download/package1/1.0.1/package1-1.0.1.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c45</a><br/>
</body>
</html>
''')

    def test_mrpypi_pypi_index_unverified(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/package2')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        self.assertEqual(content, '''\
<html>
<head>
<title>Links for package2</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for package2</h1>
<a href="../../pypi_download/package2/1.0.0/package2-1.0.0.tar.gz" rel="internal">../../pypi_download/package2/1.0.0/package2-1.0.0.tar.gz</a><br/>
<a href="../../pypi_download/package2/1.0.1/package2-1.0.1.tar.gz" rel="internal">../../pypi_download/package2/1.0.1/package2-1.0.1.tar.gz</a><br/>
</body>
</html>
''')

    def test_mrpypi_pypi_index_notFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/packageUnknown')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, 'Not Found')

    def test_mrpypi_pypi_download(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package1-1.0.1.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, 'package1-1.0.1')

    def test_mrpypi_pypi_download_packageNotFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/packageUnknown/1.0.1/packageUnknown-1.0.1.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, 'Not Found')

    def test_mrpypi_pypi_download_versionNotFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.2/package1-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, 'Not Found')

    def test_mrpypi_pypi_download_filenameMismatch(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package2-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, 'Not Found')

    def test_mrpypi_pypi_upload(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request(
            'POST', '/pypi_upload',
            environ = {
                'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
            },
            wsgiInput = '''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

0.1.4
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

''')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, '')
