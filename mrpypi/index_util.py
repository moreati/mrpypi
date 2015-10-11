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

from pip.cmdoptions import index_url
from pip.download import PipSession
from pip.index import FormatControl, PackageFinder


DEFAULT_PIP_INDEX = index_url.keywords['default']

PACKAGE_EXT_ORDER = ('.tar.gz', '.zip', '.tar.bz2')


IndexEntry = namedtuple('IndexEntry', (
    'name',
    'version',
    'filename',
    'hash',
    'hash_name',
    'url',
    'datetime'
))


PipPackage = namedtuple('PipPackageVersion', (
    'version',
    'link'
))


def _pip_package_sort_key(pip_package):
    try:
        return (pip_package.version, PACKAGE_EXT_ORDER.index(pip_package.link.ext))
    except ValueError:
        return (pip_package.version, len(PACKAGE_EXT_ORDER))


def pip_package_versions(index, package):
    format_control = FormatControl(no_binary=(':all:'), only_binary=())
    session = PipSession()
    finder = PackageFinder([], [index], format_control=format_control, session=session,
                           allow_external=[package], allow_unverified=[package])
    return sorted((PipPackage(str(pv.version), pv.location) for pv in finder._find_all_versions(package)), # pylint: disable=protected-access
                  key=_pip_package_sort_key)
