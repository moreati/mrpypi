#
# Copyright (C) 2014 Craig Hobbs
#

import sys

PY3 = (sys.version_info >= (3, 0))

# cgi
if PY3: # pragma: no cover
    import cgi as _cgi
    import html as _html
    class cgi(object):
        __slots__ = ()
        escape = _html.escape
        parse_header = _cgi.parse_header
        parse_multipart = _cgi.parse_multipart
else:
    import cgi as _cgi
    cgi = _cgi

# md5
if PY3:
    import hashlib as _hashlib
    md5 = _hashlib
else:
    import md5 as _md5
    md5 = _md5

# urllib, urllib2, urlparse
if PY3: # pragma: no cover
    import urllib.parse as _urllib_parse
    import urllib.request as _urllib_request
    class urllib(object):
        __slots__ = ()
        quote = _urllib_parse.quote
    class urllib2(object):
        __slots__ = ()
        Request = _urllib_request.Request
        urlopen = _urllib_request.urlopen
else:
    import urllib as _urllib
    import urllib2 as _urllib2
    urllib = _urllib
    urllib2 = _urllib2
