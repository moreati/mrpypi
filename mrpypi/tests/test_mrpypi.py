#
# Copyright (C) 2014-2015 Craig Hobbs
#

from collections import namedtuple
import unittest

from mrpypi import MrPyPi
from mrpypi.compat import hashlib_md5_new


TestIndexEntry = namedtuple('TestIndexEntry', ('name', 'version', 'filename', 'hash_name', 'hash'))


class TestIndex(object):

    def __init__(self):
        self._packages = [TestIndexEntry('package1', '1.0.0', 'package1-1.0.0.tar.gz', 'md5', '53bc481b565a8eb2bc72c0b4a66e9c44'),
                          TestIndexEntry('package1', '1.0.1', 'package1-1.0.1.tar.gz', 'md5', '53bc481b565a8eb2bc72c0b4a66e9c45'),
                          TestIndexEntry('package2', '1.0.0', 'package2-1.0.0.tar.gz', None, None),
                          TestIndexEntry('package2', '1.0.1', 'package2-1.0.1.tar.gz', None, None)]

    def getPackageIndex(self, dummy_ctx, packageName, dummy_forceUpdate=False):
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
            yield (packageName + '-' + version).encode('utf-8')
        return stream

    def addPackage(self, ctx, packageName, version, filename, content):
        index = self.getPackageIndex(ctx, packageName)
        if index:
            indexEntry = next((x for x in index if x.version == version), None)
            if indexEntry:
                return False
        self._packages.append(TestIndexEntry(packageName, version, filename, 'md5', hashlib_md5_new(content).hexdigest()))
        return True


class TestMrpypi(unittest.TestCase):

    def test_mrpypi_pypi_index(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/package1')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        self.assertEqual(content, b'''\
<html>
<head>
<title>Links for package1</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for package1</h1>
<a href="../../pypi_download/package1/1.0.0/package1-1.0.0.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c44" rel="internal">package1-1.0.0.tar.gz</a><br/>
<a href="../../pypi_download/package1/1.0.1/package1-1.0.1.tar.gz#md5=53bc481b565a8eb2bc72c0b4a66e9c45" rel="internal">package1-1.0.1.tar.gz</a><br/>
</body>
</html>
''')

    def test_mrpypi_pypi_index_unverified(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/package2')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        self.assertEqual(content, b'''\
<html>
<head>
<title>Links for package2</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for package2</h1>
<a href="../../pypi_download/package2/1.0.0/package2-1.0.0.tar.gz" rel="internal">package2-1.0.0.tar.gz</a><br/>
<a href="../../pypi_download/package2/1.0.1/package2-1.0.1.tar.gz" rel="internal">package2-1.0.1.tar.gz</a><br/>
</body>
</html>
''')

    def test_mrpypi_pypi_index_notFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/packageUnknown')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_mrpypi_pypi_download(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package1-1.0.1.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, b'package1-1.0.1')

    def test_mrpypi_pypi_download_packageNotFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/packageUnknown/1.0.1/packageUnknown-1.0.1.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_mrpypi_pypi_download_versionNotFound(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.2/package1-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_mrpypi_pypi_download_filenameMismatch(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package2-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_mrpypi_pypi_upload(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.0
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 File Exists')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

        status, headers, content = app.request('GET', '/pypi_index/package3')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        self.assertEqual(content, b'''\
<html>
<head>
<title>Links for package3</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for package3</h1>
<a href="../../pypi_download/package3/1.0.0/package3-1.0.0.tar.gz#md5=df9f61bece81c091f7044368fcf62501" rel="internal">package3-1.0.0.tar.gz</a><br/>
</body>
</html>
''')

        status, headers, content = app.request('GET', '/pypi_download/package3/1.0.0/package3-1.0.0.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, b'package3-1.0.0')

    def test_mrpypi_pypi_upload_existing_index(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package1-1.0.2.tar.gz"

package1 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.2
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package1
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 File Exists')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_invalid_contentType(self):

        upload_environ = {
            'CONTENT_TYPE': 'text/plain',
        }
        upload_content = b''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_invalid_action(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.0
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

invalid_action
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_multiple_action(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.0
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload2
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_invalid_filetype(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

invalid_filetype
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.0
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_invalid_version(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"

package3 content
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"


----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_mrpypi_pypi_upload_invalid_content(self):

        upload_environ = {
            'CONTENT_TYPE': 'multipart/form-data; boundary=--------------GHSKFJDLGDS7543FJKLFHRE75642756743254',
        }
        upload_content = b'''
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="filetype"

sdist
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="content";filename="package3-1.0.0.tar.gz"


----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="version"

1.0.0
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name=":action"

file_upload
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254
Content-Disposition: form-data; name="name"

package3
----------------GHSKFJDLGDS7543FJKLFHRE75642756743254--

'''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgiInput=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')
