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

from datetime import datetime

try:
    import gridfs
    import pymongo
except ImportError:
    pass

from .compat import hashlib_md5_new, itervalues, urllib_request_urlopen
from .index_util import IndexEntry, PIP_DEFAULT_INDEX, pip_package_versions


DEFAULT_MONGO_URI = 'mongodb://localhost'


class MongoIndex(object):
    __slots__ = ('mongo_uri', 'mongo_database', 'index_url')

    INDEX_COLLECTION_NAME = 'index'
    FILES_COLLECTION_NAME = 'fs'
    STREAM_CHUNK_SIZE = 4096

    def __init__(self, index_url=PIP_DEFAULT_INDEX, mongo_uri=DEFAULT_MONGO_URI, mongo_database='mrpypi'):
        self.index_url = index_url
        self.mongo_uri = mongo_uri
        self.mongo_database = mongo_database

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

        # Read mongo index
        with pymongo.MongoClient(self.mongo_uri) as mongo_client:
            mongo_package_index = self._mongo_collection_package_index(mongo_client)

            # Get the package index entries
            package_index = {x['version']:
                             IndexEntry(name=x['name'],
                                        version=x['version'],
                                        filename=x['filename'],
                                        hash=x['hash'],
                                        hash_name=x['hash_name'],
                                        url=x['url'],
                                        datetime=x['datetime'])
                             for x in mongo_package_index.find({'name': package_name})}

            # Index out-of-date?
            if not package_index or force_update:
                ctx.log.info('Updating index for "%s"', package_name)

                # For each cached pypi index
                package_index_update = {}
                if self.index_url is not None:
                    try:
                        # Get the pip index
                        pip_packages = pip_package_versions(self.index_url, package_name)
                        if pip_packages is not None:
                            for pip_package in pip_packages:
                                # New package version?
                                if pip_package.version not in package_index:
                                    package_index_entry = IndexEntry(name=package_name,
                                                                     version=pip_package.version,
                                                                     filename=pip_package.link.filename,
                                                                     hash=pip_package.link.hash,
                                                                     hash_name=pip_package.link.hash_name,
                                                                     url=pip_package.link.url,
                                                                     datetime=None)
                                    package_index[pip_package.version] = package_index_entry
                                    package_index_update[pip_package.version] = package_index_entry
                    except Exception as exc: # pylint: disable=broad-except
                        ctx.log.warning('Package versions pip exception for "%s": %s', package_name, exc)

                # Insert any new package versions
                if package_index_update:
                    mongo_package_index.insert(x._asdict() for x in itervalues(package_index_update))

        if not package_index:
            return None
        return itervalues(package_index)

    def get_package_stream(self, ctx, package_name, version, filename):

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
                    content = urllib_request_urlopen(package_entry.url).read()

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
            mongo_package_index.insert(IndexEntry(name=package_name,
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
