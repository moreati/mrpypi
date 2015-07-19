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
