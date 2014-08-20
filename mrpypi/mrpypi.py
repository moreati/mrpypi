#
# Copyright (C) 2014 Craig Hobbs
#

import cgi
import logging
import xml.sax.saxutils as saxutils

import chisel


#
# Pypi versioned package index page
#

def pypi_index_response(ctx, req, response):

    # Versioned request?
    packageIndex = ctx.index.getPackageIndex(ctx, req['package'])
    if packageIndex is None:
        return ctx.responseText('404 Not Found', 'Not Found')

    # Build the link URLs
    linkUrls = ['../../pypi_download/{package}/{version}/{filename}{hash}' \
                .format(package = pe.name,
                        version = pe.version,
                        filename = pe.filename,
                        hash = ('#{hash_name}={hash}'.format(hash_name = pe.hash_name, hash = pe.hash)
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
</html>'''.format(package = req['package'],
                  linkHtmls = '\n'.join(linkHtmls))

    return ctx.responseText('200 OK', response, contentType = 'text/html')

@chisel.action(urls = ['/pypi_index/{package}', '/pypi_index/{package}/'],
               response = pypi_index_response,
               spec = '''\
action pypi_index
    input
        string package
''')
def pypi_index(ctx, req):
    pass


#
# Pypi package download
#

def pypi_download_response(ctx, req, response):

    # Get the package stream generator
    packageStream = ctx.index.getPackageStream(ctx, req['package'], req['version'], req['filename'])
    if packageStream is None:
        return ctx.responseText('404 Not Found', 'Not Found')

    # Stream the package
    ctx.start_response('200 OK', [('Content-Type','application/octet-stream')])
    return packageStream()

@chisel.action(urls = ['/pypi_download/{package}/{version}/{filename}'],
               response = pypi_download_response,
               spec = '''\
action pypi_download
    input
        string package
        string version
        string filename
''')
def pypi_download(ctx, req):
    pass


#
# Pypi package upload
#

_uploadFiletypeToExt = {
    'sdist': '.tar.gz'
}

def _pypi_upload(ctx):

    # Decode the multipart post
    ctype, pdict = cgi.parse_header(ctx.environ.get('CONTENT_TYPE', ''))
    if ctype != 'multipart/form-data':
        return ctx.responseText('400 Bad Request', '')
    parts = cgi.parse_multipart(ctx.environ['wsgi.input'], pdict)

    # Sanity check
    def getPart(key):
        value = parts.get(key)
        return value[0] if (value is not None and isinstance(value, list) and len(value) == 1) else None
    action = getPart(':action')
    filetype = getPart('filetype')
    package = getPart('name')
    version = getPart('version')
    content = getPart('content')
    if (action != 'file_upload' or
        filetype not in _uploadFiletypeToExt or
        not isinstance(package, str) or len(package) == 0 or
        not isinstance(version, str) or len(version) == 0 or
        not isinstance(content, bytes) or len(content) == 0):
        return ctx.responseText('400 Bad Request', 'Bad Request')

    # Construct the package filename
    filename = package + '-' + version + _uploadFiletypeToExt[filetype]

    # Add the package to the index
    if not ctx.index.addPackage(ctx, package, version, filename, content):
        return ctx.responseText('400 File Exists', '')

    return ctx.responseText('200 OK', '')

@chisel.request
def pypi_upload(environ, start_response):
    ctx = environ[chisel.Application.ENVIRON_APP]
    try:
        return _pypi_upload(ctx)
    except:
        ctx.log.exception('Exception raised in pypi_upload')
        return ctx.responseText('500 Internal Server Error', 'Internal Server Error')


#
# Pypi application
#

class MrPyPi(chisel.Application):
    __slots__ = ('index')

    def __init__(self, index):
        chisel.Application.__init__(self)
        self.index = index
        self.logLevel = logging.INFO

    def init(self):
        self.addDocRequest()
        self.addRequest(pypi_index)
        self.addRequest(pypi_download)
        self.addRequest(pypi_upload)
