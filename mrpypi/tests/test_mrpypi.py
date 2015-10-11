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

import unittest

from chisel import Application, Context

from mrpypi import MrPyPi, MemoryIndex


class TestMrpypi(unittest.TestCase):

    @staticmethod
    def _test_index():
        ctx = Context(Application(), {}, None, {})
        index = MemoryIndex(index_url=None)
        index.add_package(ctx, 'package1', '1.0.0', 'package1-1.0.0.tar.gz', b'package1-1.0.0')
        index.add_package(ctx, 'package1', '1.0.1', 'package1-1.0.1.tar.gz', b'package1-1.0.1')
        index.add_package(ctx, 'package2', '1.0.0', 'package2-1.0.0.tar.gz', b'package2-1.0.0')
        index.add_package(ctx, 'package2', '1.0.1', 'package2-1.0.1.tar.gz', b'package2-1.0.1')
        return index

    def test_mrpypi_pypi_index(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_index/package1')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        expected_content = b'''\
<!doctype html>
<html lang="en">
  <head>
    <title>Links for package1</title>
    <meta name="api-version" value="2">
  </head>
  <body>
    <h1>Links for package1</h1>
    <a href="../../pypi_download/package1/1.0.0/package1-1.0.0.tar.gz#md5=5f832e6e6b2107ba3b0463fc171623d7" rel="internal">package1-1.0.0.tar.gz</a><br>
    <a href="../../pypi_download/package1/1.0.1/package1-1.0.1.tar.gz#md5=7ff99f5a955518cece354b9a0e94007d" rel="internal">package1-1.0.1.tar.gz</a><br>
  </body>
</html>'''
        self.assertEqual(content, expected_content)

    def test_index_unverified(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_index/package2')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'text/html') in headers)
        expected_content = b'''\
<!doctype html>
<html lang="en">
  <head>
    <title>Links for package2</title>
    <meta name="api-version" value="2">
  </head>
  <body>
    <h1>Links for package2</h1>
    <a href="../../pypi_download/package2/1.0.0/package2-1.0.0.tar.gz#md5=e5bb63cbaf57f917dec872455807ea9a" rel="internal">package2-1.0.0.tar.gz</a><br>
    <a href="../../pypi_download/package2/1.0.1/package2-1.0.1.tar.gz#md5=5196a17e0ebf66da9ac16f09a836d60f" rel="internal">package2-1.0.1.tar.gz</a><br>
  </body>
</html>'''
        self.assertEqual(content, expected_content)

    def test_index_not_found(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_index/packageUnknown')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.1/package1-1.0.1.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, b'package1-1.0.1')

    def test_download_package_not_found(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_download/packageUnknown/1.0.1/packageUnknown-1.0.1.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download_version_not_found(self):

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('GET', '/pypi_download/package1/1.0.2/package1-1.0.2.tar.gz')
        self.assertEqual(status, '404 Not Found')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'Not Found')

    def test_download_filename_mismatch(self):

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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
        expected_content = b'''\
<!doctype html>
<html lang="en">
  <head>
    <title>Links for package3</title>
    <meta name="api-version" value="2">
  </head>
  <body>
    <h1>Links for package3</h1>
    <a href="../../pypi_download/package3/1.0.0/package3-1.0.0.tar.gz#md5=df9f61bece81c091f7044368fcf62501" rel="internal">package3-1.0.0.tar.gz</a><br>
  </body>
</html>'''
        self.assertEqual(content, expected_content)

        status, headers, content = app.request('GET', '/pypi_download/package3/1.0.0/package3-1.0.0.tar.gz')
        self.assertEqual(status, '200 OK')
        self.assertTrue(('Content-Type', 'application/octet-stream') in headers)
        self.assertEqual(content, b'package3 content')

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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
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

        app = MrPyPi(self._test_index())
        status, headers, content = app.request('POST', '/pypi_upload', environ=upload_environ, wsgi_input=upload_content)
        self.assertEqual(status, '400 Bad Request')
        self.assertTrue(('Content-Type', 'text/plain') in headers)
        self.assertEqual(content, b'')
