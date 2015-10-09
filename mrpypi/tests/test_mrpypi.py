#
# Copyright (C) 2014-2015 Craig Hobbs
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
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

    def get_package_index(self, dummy_ctx, package_name, dummy_force_update=False):
        return [x for x in self._packages if x.name == package_name] or None

    def get_package_stream(self, ctx, package_name, version, filename):
        index = self.get_package_index(ctx, package_name)
        if index is None:
            return None
        index_entry = next((x for x in index if x.version == version), None)
        if index_entry is None:
            return None
        if index_entry.filename != filename:
            return None

        def stream():
            yield (package_name + '-' + version).encode('utf-8')
        return stream

    def add_package(self, ctx, package_name, version, filename, content):
        index = self.get_package_index(ctx, package_name)
        if index:
            index_entry = next((x for x in index if x.version == version), None)
            if index_entry:
                return False
        self._packages.append(TestIndexEntry(package_name, version, filename, 'md5', hashlib_md5_new(content).hexdigest()))
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

    def test_index_unverified(self):

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

    def test_index_not_found(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_index/packageUnknown')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package1-1.0.1.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, b'package1-1.0.1')

    def test_download_package_not_found(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/packageUnknown/1.0.1/packageUnknown-1.0.1.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download_version_not_found(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.2/package1-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download_filename_mismatch(self):

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package2-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_upload(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=dict(upload_environ), wsgi_input=upload_content)
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
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

    def test_upload_existing_index(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=dict(upload_environ), wsgi_input=upload_content)
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 File Exists')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_bad_content_type(self):

        upload_environ = {
            'CONTENT_TYPE': 'text/plain',
        }
        upload_content = b''

        app = MrPyPi(TestIndex())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_bad_action(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_multiple_action(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_bad_filetype(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_bad_version(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')

    def test_upload_bad_content(self):

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
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')
