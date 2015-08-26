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
import xml.sax.saxutils as saxutils

import chisel

from .compat import html_escape, urllib_parse_quote


#
# Pypi package index page
#

@chisel.action(urls=['/pypi_index/{package}', '/pypi_index/{package}/'], wsgi_response=True,
               spec='''\
action pypi_index
    input
        string package
        optional bool forceUpdate
''')
def pypi_index(ctx, req):

    # Get the package index
    packageIndex = ctx.app.index.getPackageIndex(ctx, req['package'], req.get('forceUpdate', False))
    if packageIndex is None:
        return ctx.response_text('404 Not Found', 'Not Found')

    # Build the link HTML
    linkHtmls = [
        '<a href={linkUrlHref} rel="internal">{filenameText}</a><br/>'.format(
            linkUrlHref=saxutils.quoteattr('../../pypi_download/{package}/{version}/{filename}{hash}'.format(
                package=urllib_parse_quote(pe.name),
                version=urllib_parse_quote(pe.version),
                filename=urllib_parse_quote(pe.filename),
                hash=(('#' + urllib_parse_quote(pe.hash_name) + '=' + urllib_parse_quote(pe.hash))
                      if pe.hash is not None else ''))),
            filenameText=html_escape(pe.filename))
        for pe in packageIndex]

    # Build the index response
    response = '''\
<html>
<head>
<title>Links for {package}</title>
<meta name="api-version" value="2" />
</head>
<body>
<h1>Links for {package}</h1>
{linkHtmls}
</body>
</html>
'''.format(package=html_escape(req['package']),
           linkHtmls='\n'.join(linkHtmls))

    return ctx.response_text('200 OK', response, content_type='text/html')


#
# Pypi package download
#

@chisel.action(urls=['/pypi_download/{package}/{version}/{filename}'], wsgi_response=True,
               spec='''\
action pypi_download
    input
        string package
        string version
        string filename
''')
def pypi_download(ctx, req):

    # Get the package stream generator
    packageStream = ctx.app.index.getPackageStream(ctx, req['package'], req['version'], req['filename'])
    if packageStream is None:
        return ctx.response_text('404 Not Found', 'Not Found')

    # Stream the package
    ctx.start_response('200 OK', [('Content-Type', 'application/octet-stream')])
    return packageStream()


#
# Pypi package upload
#

_uploadFiletypeToExt = {
    'sdist': '.tar.gz'
}


@chisel.request
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

    def getPart(key, strip=True):
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
    action = getPart(':action')
    if action == 'file_upload':

        # Get file upload arguments
        filetype = getPart('filetype')
        package = getPart('name')
        version = getPart('version')
        content = getPart('content', strip=False)
        if filetype not in _uploadFiletypeToExt or package is None or version is None or content is None:
            return ctx.response_text('400 Bad Request', '')

        # Add the package to the index
        filename = package + '-' + version + _uploadFiletypeToExt[filetype]
        result = ctx.app.index.addPackage(ctx, package, version, filename, content)
        return ctx.response_text('200 OK' if result else '400 File Exists', '')

    # Unknown action
    return ctx.response_text('400 Bad Request', '')


#
# Pypi application
#

class MrPyPi(chisel.Application):
    __slots__ = ('index')

    def __init__(self, index):

        # Override application defaults
        chisel.Application.__init__(self)
        self.log_level = logging.INFO

        # Set the index
        self.index = index

        # Add application requests
        self.add_request(chisel.DocAction())
        self.add_request(pypi_index)
        self.add_request(pypi_download)
        self.add_request(pypi_upload)
