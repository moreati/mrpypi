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
from datetime import datetime

from .compat import hashlib_md5_new, urllib_request_urlopen
from .index_util import pip_default_indexes, pip_package_versions


MemoryIndexEntry = namedtuple('MemoryIndexEntry', (
    'name',
    'version',
    'filename',
    'hash',
    'hash_name',
    'url',
    'datetime'
))


class MemoryIndex(object):
    __slots__ = ('_index', '_index_url', '_index_content')

    def __init__(self, index_url=pip_default_indexes()[0]):
        self._index = {}
        self._index_url = index_url
        self._index_content = {}

    def _update_index(self, ctx, package_name):
        if self._index_url is None:
            return
        ctx.log.info('Updating index for package "{0}"'.format(package_name))
        pip_packages = pip_package_versions(self._index_url, package_name)
        if pip_packages is None:
            return
        package_index = self._index.setdefault(package_name, {})
        for pip_package in pip_packages:
            if pip_package.version not in package_index:
                index_entry = MemoryIndexEntry(name=package_name,
                                               version=pip_package.version,
                                               filename=pip_package.link.filename,
                                               hash=pip_package.link.hash,
                                               hash_name=pip_package.link.hash_name,
                                               url=pip_package.link.url,
                                               datetime=None)
                package_index[pip_package.version] = index_entry

    def get_package_index(self, ctx, package_name, force_update=False):
        package_index = self._index.get(package_name)
        if package_index is None or force_update:
            self._update_index(ctx, package_name)
            package_index = self._index.get(package_name)
        if package_index is None:
            return None
        return package_index.values()

    def add_package(self, ctx, package_name, version, filename, content):
        index_entry = self._index.setdefault(package_name, {}).get(version)
        if index_entry is not None:
            ctx.log.info('Attempt to re-add package "{0}", version "{1}"'.format(
                index_entry.name, index_entry.version))
            return False
        ctx.log.info('Adding package "{0}", version "{1}" with filename "{2}" of {3} bytes'.format(
            package_name, version, filename, len(content)))
        index_entry = MemoryIndexEntry(name=package_name,
                                       version=version,
                                       filename=filename,
                                       hash=hashlib_md5_new(content).hexdigest(),
                                       hash_name='md5',
                                       url=None,
                                       datetime=datetime.now())
        self._index[package_name][version] = index_entry
        self._index_content[index_entry] = content
        return True

    def get_package_stream(self, ctx, package_name, version, filename):
        package_index = self._index.get(package_name)
        index_entry = package_index.get(version) if package_index is not None else None
        if index_entry is None:
            self._update_index(ctx, package_name)
            package_index = self._index.get(package_name)
            index_entry = package_index.get(version) if package_index is not None else None
        if index_entry is None or index_entry.filename != filename:
            return None
        if index_entry not in self._index_content:
            ctx.log.info('Downloading package "{0}", version "{1}" from "{2}"'.format(
                index_entry.name, index_entry.version, index_entry.url))
            self._index_content[index_entry] = urllib_request_urlopen(index_entry.url).read()
        def package_stream():
            yield self._index_content[index_entry]
        return package_stream
