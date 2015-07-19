#
# Copyright (C) 2014-2015 Craig Hobbs
#

import sys

_PY3 = (sys.version_info >= (3, 0))

# hashlib
if _PY3:
    from hashlib import md5 as hashlib_md5_new # pylint: disable=unused-import
else: # pragma: no cover
    from md5 import new as hashlib_md5_new # pylint: disable=import-error,unused-import

# html
if _PY3:
    from html import escape as html_escape # pylint: disable=unused-import
else: # pragma: no cover
    from cgi import escape as html_escape

# urllib
if _PY3:
    from urllib.parse import quote as urllib_parse_quote # pylint: disable=unused-import
    from urllib.request import Request as urllib_request_Request, urlopen as urllib_request_urlopen # pylint: disable=unused-import
else: # pragma: no cover
    from urllib import quote as urllib_parse_quote # pylint: disable=no-name-in-module
    from urllib2 import Request as urllib_request_Request, urlopen as urllib_request_urlopen # pylint: disable=import-error
