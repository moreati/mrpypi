#
# Copyright (C) 2014 Craig Hobbs
#

import cgi
import logging
import urllib
import xml.sax.saxutils as saxutils

import chisel


#
# Pypi package index page
#

@chisel.action(urls = ['/pypi_index/{package}', '/pypi_index/{package}/'], wsgiResponse = True,
               spec = '''\
action pypi_index
    input
        string package
''')
def pypi_index(ctx, req):

    # Get the package index
    packageIndex = ctx.index.getPackageIndex(ctx, req['package'])
    if packageIndex is None:
        return ctx.responseText('404 Not Found', 'Not Found')

    # Build the link URLs
    linkUrls = ['../../pypi_download/{package}/{version}/{filename}{hash}' \
                .format(package = urllib.pathname2url(pe.name),
                        version = urllib.pathname2url(pe.version),
                        filename = urllib.pathname2url(pe.filename),
                        hash = (('#' + urllib.quote(pe.hash_name) + '=' + urllib.quote(pe.hash))
                                if pe.hash is not None else ''))
                for pe in packageIndex]

    # Build the link HTML
    linkHtmls = ['<a href={linkUrlHref} rel="internal">{linkUrlText}</a><br/>' \
                 .format(linkUrlHref = saxutils.quoteattr(linkUrl),
                         linkUrlText = cgi.escape(linkUrl))
                 for linkUrl in linkUrls]

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
</html>'''.format(package = cgi.escape(req['package']),
                  linkHtmls = '\n'.join(linkHtmls))

    return ctx.responseText('200 OK', response, contentType = 'text/html')


#
# Pypi package download
#

@chisel.action(urls = ['/pypi_download/{package}/{version}/{filename}'], wsgiResponse = True,
               spec = '''\
action pypi_download
    input
        string package
        string version
        string filename
''')
def pypi_download(ctx, req):

    # Get the package stream generator
    packageStream = ctx.index.getPackageStream(ctx, req['package'], req['version'], req['filename'])
    if packageStream is None:
        return ctx.responseText('404 Not Found', 'Not Found')

    # Stream the package
    ctx.start_response('200 OK', [('Content-Type','application/octet-stream')])
    return packageStream()


#
# Pypi package upload
#

_uploadFiletypeToExt = {
    'sdist': '.tar.gz'
}

@chisel.request
def pypi_upload(environ, start_response):
    ctx = environ[chisel.Application.ENVIRON_APP]

    # Decode the multipart post
    ctype, pdict = cgi.parse_header(ctx.environ.get('CONTENT_TYPE', ''))
    if ctype != 'multipart/form-data':
        return ctx.responseText('400 Bad Request', '')
    parts = cgi.parse_multipart(ctx.environ['wsgi.input'], pdict)

    def getPart(key, expectedType = str, minLen = 1, strip = True):
        values = parts.get(key)
        if values is None or not isinstance(values, list) or len(values) != 1:
            return None
        value = values[0]
        if not isinstance(value, expectedType):
            return None
        if strip:
            value = value.strip()
        if minLen is not None and len(value) < minLen:
            return None
        return value

    # Handle the action
    action = getPart(':action')
    if action == 'file_upload':

        # Get file upload arguments
        filetype = getPart('filetype')
        package = getPart('name')
        version = getPart('version')
        content = getPart('content', expectedType = bytes, strip = False)
        if filetype not in _uploadFiletypeToExt or package is None or version is None or content is None:
            return ctx.responseText('400 Bad Request', 'Bad Request')

        # Add the package to the index
        filename = package + '-' + version + _uploadFiletypeToExt[filetype]
        result = ctx.index.addPackage(ctx, package, version, filename, content)
        return ctx.responseText('200 OK' if result else '400 File Exists', '')

    else: # Unknown action
        return ctx.responseText('400 Bad Request', 'Bad Request')


#
# Pypi application
#

class MrPyPi(chisel.Application):
    __slots__ = ('index')

    def __init__(self, index):

        # Override application defaults
        chisel.Application.__init__(self)
        self.logLevel = logging.INFO

        # Set the index
        self.index = index

        # Add application requests
        self.addDocRequest()
        self.addRequest(pypi_index)
        self.addRequest(pypi_download)
        self.addRequest(pypi_upload)
