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

try:
    import gridfs
    import pymongo
except ImportError:
    pass

from .compat import hashlib_md5_new, urllib_request_Request, urllib_request_urlopen
from .index_util import pip_default_indexes, pip_package_versions


MongoIndexEntry = namedtuple('MongoIndexEntry', (
    'name',
    'version',
    'filename',
    'hash',
    'hash_name',
    'url',
    'datetime'
))


# Prefer tarball's over files of other extensions...
PIP_PACKAGE_EXT_ORDER = ('.tar.gz', '.zip', '.tar.bz2')


def _pip_package_sort_key(pip_package):
    try:
        return (pip_package.version, PIP_PACKAGE_EXT_ORDER.index(pip_package.link.ext))
    except ValueError:
        return (pip_package.version, len(PIP_PACKAGE_EXT_ORDER))


class MongoIndex(object):
    __slots__ = ('mongo_uri', 'mongo_database', 'index_urls')

    INDEX_COLLECTION_NAME = 'index'
    FILES_COLLECTION_NAME = 'fs'
    STREAM_CHUNK_SIZE = 4096

    def __init__(self, mongo_uri=None, mongo_database=None, index_urls=None):
        self.mongo_uri = mongo_uri if mongo_uri is not None else 'mongodb://localhost:27017'
        self.mongo_database = mongo_database if mongo_database is not None else 'mrpypi'
        self.index_urls = index_urls if index_urls is not None else pip_default_indexes()

    @staticmethod
    def _normalize_name(package_name):
        return package_name.strip().lower()

    @staticmethod
    def _normalize_version(version):
        return version.strip()

    @staticmethod
    def _normalize_filename(filename):
        return filename.strip()

    @staticmethod
    def _local_filename(package_name, version):
        return package_name + '/' + version

    def _mongo_collection_package_index(self, mongo_client):
        mongo_package_index = mongo_client[self.mongo_database][self.INDEX_COLLECTION_NAME]
        mongo_package_index.ensure_index([('name', pymongo.ASCENDING), ('version', pymongo.ASCENDING)], unique=True)
        return mongo_package_index

    def _mongo_gridfs_package_files(self, mongo_client):
        return gridfs.GridFS(mongo_client[self.mongo_database], collection=self.FILES_COLLECTION_NAME)

    def get_package_index(self, ctx, package_name, force_update=False):
        package_name = self._normalize_name(package_name)

        # Read mongo index
        with pymongo.MongoClient(self.mongo_uri) as mongo_client:
            mongo_package_index = self._mongo_collection_package_index(mongo_client)

            # Get the package index entries
            package_index = [MongoIndexEntry(name=x['name'],
                                             version=x['version'],
                                             filename=x['filename'],
                                             hash=x['hash'],
                                             hash_name=x['hash_name'],
                                             url=x['url'],
                                             datetime=x['datetime'])
                             for x in mongo_package_index.find({'name': package_name})]
            package_versions = set(x.version for x in package_index)

            # Index out-of-date?
            if not package_index or force_update:
                ctx.log.info('Updating index for "%s"', package_name)

                # For each cached pypi index
                now = datetime.now()
                update_package_index = []
                for index_url in self.index_urls:
                    try:
                        # Get the pip index
                        pip_packages = pip_package_versions(index_url, package_name)
                        if pip_packages is not None:
                            for pip_package in sorted(pip_packages, key=_pip_package_sort_key):
                                # New package version?
                                pip_package_version = self._normalize_version(pip_package.version)
                                if pip_package_version not in package_versions:
                                    package_index_entry = MongoIndexEntry(name=package_name,
                                                                          version=pip_package_version,
                                                                          filename=pip_package.link.filename,
                                                                          hash=pip_package.link.hash,
                                                                          hash_name=pip_package.link.hash_name,
                                                                          url=pip_package.link.url,
                                                                          datetime=now)
                                    package_index.append(package_index_entry)
                                    update_package_index.append(package_index_entry)
                                    package_versions.add(pip_package_version)
                    except Exception as exc: # pylint: disable=broad-except
                        ctx.log.warning('Package versions pip exception for "%s": %s', package_name, exc)

                # Insert any new package versions
                if update_package_index:
                    mongo_package_index.insert(x._asdict() for x in update_package_index)

        return package_index or None

    def get_package_stream(self, ctx, package_name, version, filename):
        package_name = self._normalize_name(package_name)
        version = self._normalize_version(version)
        filename = self._normalize_filename(filename)

        # Find the package index entry
        package_entry = next((pe for pe in self.get_package_index(ctx, package_name) if pe.version == version), None)
        if package_entry is None or package_entry.filename != filename:
            return None

        # File stream...
        def package_stream():

            # Open the gridfs
            with pymongo.MongoClient(self.mongo_uri) as mongo_client:
                gridfs_package_files = self._mongo_gridfs_package_files(mongo_client)

                # Package file not exist?
                gridfs_filename = self._local_filename(package_name, version)
                if not gridfs_package_files.exists(filename=gridfs_filename):

                    # Download the file
                    assert package_entry.url, 'Attempt to add package index entry without URL!!'
                    ctx.log.info('Downloading package (%s, %s) from "%s"', package_name, version, package_entry.url)
                    req = urllib_request_Request(url=package_entry.url)
                    reqf = urllib_request_urlopen(req)
                    try:
                        content = reqf.read()
                    finally:
                        reqf.close()

                    # Add the file
                    ctx.log.info('Adding package (%s, %s) (%d bytes)', package_name, version, len(content))
                    with gridfs_package_files.new_file(filename=gridfs_filename) as gridfs_file:
                        gridfs_file.write(content)

                # Stream the file chunks
                with gridfs_package_files.get_last_version(filename=gridfs_filename) as gridfs_file:
                    while True:
                        data = gridfs_file.read(self.STREAM_CHUNK_SIZE)
                        if not data:
                            break
                        yield data

        return package_stream

    def add_package(self, ctx, package_name, version, filename, content):
        package_name = self._normalize_name(package_name)
        version = self._normalize_version(version)
        filename = self._normalize_filename(filename)

        # Index exist?
        package_index = self.get_package_index(ctx, package_name) or ()
        package_exists = next((pe for pe in package_index if pe.version == version), None)
        if package_exists is not None:
            ctx.log.error('Attempt to add package index (%s, %s) that already exists!', package_name, version)
            return False

        # Open the gridfs
        with pymongo.MongoClient(self.mongo_uri) as mongo_client:
            mongo_package_index = self._mongo_collection_package_index(mongo_client)
            gridfs_package_files = self._mongo_gridfs_package_files(mongo_client)

            # File exist?
            gridfs_filename = self._local_filename(package_name, version)
            if gridfs_package_files.exists(filename=gridfs_filename):
                ctx.log.error('Attempt to add package file (%s, %s) that already exists!', package_name, version)
                return False

            # Add the index
            ctx.log.info('Adding package index (%s, %s)', package_name, version)
            mongo_package_index.insert(MongoIndexEntry(name=package_name,
                                                       version=version,
                                                       filename=filename,
                                                       hash=hashlib_md5_new(content).hexdigest(),
                                                       hash_name='md5',
                                                       url=None,
                                                       datetime=datetime.now())._asdict())

            # Add the file
            ctx.log.info('Adding package file (%s, %s) (%d bytes)', package_name, version, len(content))
            with gridfs_package_files.new_file(filename=gridfs_filename) as gridfs_file:
                gridfs_file.write(content)

            return True
