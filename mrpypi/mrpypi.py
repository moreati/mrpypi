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

import cgi
import logging

import chisel


class MrPyPi(chisel.Application):
    __slots__ = ('index')

    def __init__(self, index):
        chisel.Application.__init__(self)
        self.log_level = logging.INFO
        self.index = index

        # Add requests
        self.add_request(chisel.DocAction())
        self.add_request(pypi_index)
        self.add_request(pypi_download)
        self.add_request(pypi_upload)


def _normalize_package_name(package_name):
    return package_name.strip().lower()

def _normalize_version(version):
    return version.strip()

def _normalize_filename(filename):
    return filename.strip()


@chisel.action(urls=('/pypi_index/{package}', '/pypi_index/{package}/'),
               wsgi_response=True, spec='''\
# Pypi package index page
action pypi_index
    input
        string package
        optional bool force_update
''')
def pypi_index(ctx, req):

    # Get the package index
    package_name = req.get('package')
    package_index = ctx.app.index.get_package_index(ctx, _normalize_package_name(package_name),
                                                    force_update=req.get('force_update', False))
    if package_index is None:
        return ctx.response_text('404 Not Found', 'Not Found')

    # Build the link HTML
    root = chisel.Element('html', lang='en')
    head = root.add_child('head')
    head.add_child('title', inline=True).add_child('Links for {0}'.format(package_name), text=True)
    head.add_child('meta', closed=False, _name='api-version', value='2')
    body = root.add_child('body')
    body.add_child('h1', inline=True).add_child('Links for {0}'.format(package_name), text=True)
    for package_entry in sorted(package_index, key=lambda package_entry: package_entry.version):
        package_hash = ''
        if package_entry.hash is not None:
            package_hash = '#' + package_entry.hash_name + '=' + package_entry.hash
        package_url = '../../pypi_download/{0}/{1}/{2}{3}'.format(
            package_entry.name, package_entry.version, package_entry.filename, package_hash)
        body.add_child('a', inline=True, href=package_url, rel='internal') \
            .add_child(package_entry.filename, text=True)
        body.add_child('br', closed=False, indent=False)

    return ctx.response_text('200 OK', root.serialize(), content_type='text/html')


@chisel.action(urls=('/pypi_download/{package}/{version}/{filename}',),
               wsgi_response=True, spec='''\
# Pypi package download
action pypi_download
    input
        string package
        string version
        string filename
''')
def pypi_download(ctx, req):

    # Get the package stream generator
    package_stream = ctx.app.index.get_package_stream(ctx, _normalize_package_name(req['package']),
                                                      _normalize_version(req['version']),
                                                      _normalize_filename(req['filename']))
    if package_stream is None:
        return ctx.response_text('404 Not Found', 'Not Found')

    # Stream the package
    ctx.start_response('200 OK', [('Content-Type', 'application/octet-stream')])
    return package_stream()


UPLOAD_FILETYPE_TO_EXT = {
    'sdist': '.tar.gz'
}


@chisel.request(urls=('/pypi_upload',),
                doc=('Pypi package upload',))
def pypi_upload(environ, dummy_start_response):
    ctx = environ[chisel.Application.ENVIRON_CTX]

    # Decode the multipart post
    ctype, pdict = cgi.parse_header(environ.get('CONTENT_TYPE', ''))

    # Ensure boundary is bytes for Python3
    boundary = pdict.get('boundary')
    if boundary is not None:
        pdict['boundary'] = boundary.encode('ascii')

    if ctype != 'multipart/form-data':
        return ctx.response_text('400 Bad Request', '')
    parts = cgi.parse_multipart(environ['wsgi.input'], pdict)

    def get_part(key, strip=True):
        values = parts.get(key)
        if values is None or not isinstance(values, list) or len(values) != 1:
            return None
        value = values[0]
        if strip:
            value = value.strip().decode('utf-8')
        if len(value) <= 0:
            return None
        return value

    # Handle the action
    action = get_part(':action')
    if action == 'file_upload':

        # Get file upload arguments
        filetype = get_part('filetype')
        package = get_part('name')
        version = get_part('version')
        content = get_part('content', strip=False)
        if filetype not in UPLOAD_FILETYPE_TO_EXT or package is None or version is None or content is None:
            return ctx.response_text('400 Bad Request', '')

        # Add the package to the index
        filename = package + '-' + version + UPLOAD_FILETYPE_TO_EXT[filetype]
        result = ctx.app.index.add_package(ctx, _normalize_package_name(package),
                                           _normalize_version(version),
                                           _normalize_filename(filename),
                                           content)
        return ctx.response_text('200 OK' if result else '400 File Exists', '')

    # Unknown action
    return ctx.response_text('400 Bad Request', '')
