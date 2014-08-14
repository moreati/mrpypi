import cgi
from collections import namedtuple
from datetime import datetime, timedelta
import logging
import pip
import pip.req
import posixpath
import urllib2
import xml.sax.saxutils as saxutils

import chisel
from pymongo import MongoClient


#
# pip utilities
#

PipPackage = namedtuple('PipPackageVersion', ('versionKey', 'link', 'version'))

def pipDefaultIndexes():
    return (pip.cmdoptions.index_url.kwargs['default'],)

def pipPackageVersions(index, package):
    finder = pip.index.PackageFinder([], [index], use_wheel = False,
                                     allow_external = [package], allow_unverified = [package])
    packageReq = pip.req.InstallRequirement(package, None)
    packageLink = pip.req.Link(posixpath.join(index, packageReq.url_name, ''), trusted = True)
    packageVersions = []
    packageExists = False
    for packagePage in finder._get_pages([packageLink], packageReq):
        packageExists = True
        packageVersions.extend(PipPackage(*pv) for pv in
                               finder._package_versions(packagePage.links, packageReq.name.lower()))
    return packageVersions if packageExists else None


#
# Package cache
#

CACHE_INDEX_TTL = timedelta(days = 7)
CACHE_INDEX_COLLECTION = 'Index'

CachePackage = namedtuple('CachePackage', ('package', 'datetime', 'version', 'filename', 'hash', 'hash_name', 'url'))

def cachePackageVersions(ctx, package):

    now = datetime.now()

    # Read mongo index
    with MongoClient(ctx.mongoUri) as mclient:
        mdb = mclient[ctx.mongoDatabase]
        mix = mdb[CACHE_INDEX_COLLECTION]

        # Get the package index entries
        index = [CachePackage(x['package'], x['datetime'], x['version'],
                              x['filename'], x['hash'], x['hash_name'], x['url'])
                 for x in mix.find({'package': package})]
        indexExists = len(index) != 0

        # Index out-of-date?
        if not indexExists or max(x.datetime for x in index) - now > CACHE_INDEX_TTL:
            ctx.log.info('Updating index for %r', package)

            # Read remote index
            remoteIndex = []
            remoteExists = False
            remoteVersions = set()
            for index in ctx.indexUrls:
                try:
                    pipPackages = pipPackageVersions(index, package)
                    if pipPackages is not None:
                        remoteExists = True
                        for pipPackage in pipPackages:
                            if pipPackage.version not in remoteVersions:
                                remoteVersions.add(pipPackage.version)
                                remoteIndex.append(CachePackage(package, now, pipPackage.version,
                                                                pipPackage.link.filename, pipPackage.link.hash,
                                                                pipPackage.link.hash_name, pipPackage.link.url))
                except Exception as e:
                    ctx.log.warning('Package versions pip exception for %r: %s', package, e)

            # Remote package exist?
            if remoteExists:

                #!! Update persistent index...
                mix.insert(x._asdict() for x in remoteIndex)

    return index if indexExists else None

def cachePackageStream(ctx, package, version, filename):

    cachePackage = next((cp for cp in cachePackageVersions(ctx, package) if cp.version == version), None)
    if cachePackage is None or cachePackage.filename != filename:
        return None

    def packageStream():
        req = urllib2.Request(url = cachePackage.url)
        fh = urllib2.urlopen(req)
        while True:
            data = fh.read(4096)
            if not data:
                break
            yield data
        fh.close()

    return packageStream

def cachePackageAdd(ctx, package, version, filename, content):
    ctx.log.info('Adding package %r, %r, %r, %r', package, version, filename, len(content))


#
# Pypi versioned package index page
#

def pypi_index_response(ctx, req, response):

    # Versioned request?
    cachePackages = cachePackageVersions(ctx, req['package'])
    if cachePackages is None:
        return ctx.responseText('404 Not Found', 'Not Found')

    # Build the link URLs
    linkUrls = ['../../pypi_download/{package}/{version}/{filename}{hash}' \
                .format(package = req['package'].lower(),
                        version = cp.version,
                        filename = cp.filename,
                        hash = ('#{hash_name}={hash}'.format(hash_name = cp.hash_name, hash = cp.hash)
                                if cp.hash is not None else ''))
                for cp in cachePackages]

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
    packageStream = cachePackageStream(ctx, req['package'], req['version'], req['filename'])
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
        return ctx.responseText('400 Bad Request', 'Bad Request')
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

    # Add the package to the cache
    cachePackageAdd(ctx, package, version, filename, content)

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
    __slots__ = ('mongoUri', 'mongoDatabase', 'indexUrls')

    def __init__(self, mongoUri = None, mongoDatabase = None, indexUrls = None):
        chisel.Application.__init__(self)
        self.mongoUri = mongoUri if mongoUri is not None else 'mongodb://localhost:27017'
        self.mongoDatabase = mongoDatabase if mongoDatabase is not None else 'MrPyPi'
        self.indexUrls = indexUrls if indexUrls is not None else pipDefaultIndexes()
        self.logLevel = logging.INFO

    def init(self):
        self.addDocRequest()
        self.addRequest(pypi_index)
        self.addRequest(pypi_download)
        self.addRequest(pypi_upload)
