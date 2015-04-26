#
# Copyright (C) 2014 Craig Hobbs
#

from collections import namedtuple
from datetime import datetime

import gridfs  # pymongo
import pymongo

from .compat import md5_new, urllib2
from .indexUtil import pipDefaultIndexes, pipPackageVersions


MongoIndexEntry = namedtuple('MongoIndexEntry', ('name', 'version', 'filename', 'hash', 'hash_name', 'url', 'datetime'))


# Prefer tarball's over files of other extensions...
_pipPackageExtOrder = ('.tar.gz', '.zip', '.tar.bz2')


def _pipPackageSortKey(pipPackage):
    try:
        return (pipPackage.version, _pipPackageExtOrder.index(pipPackage.link.ext))
    except ValueError:
        return (pipPackage.version, len(_pipPackageExtOrder))


class MongoIndex(object):
    __slots__ = ('mongoUri', 'mongoDatabase', 'indexUrls')

    INDEX_COLLECTION_NAME = 'index'
    FILES_COLLECTION_NAME = 'fs'
    STREAM_CHUNK_SIZE = 4096

    def __init__(self, mongoUri=None, mongoDatabase=None, indexUrls=None):
        self.mongoUri = mongoUri if mongoUri is not None else 'mongodb://localhost:27017'
        self.mongoDatabase = mongoDatabase if mongoDatabase is not None else 'mrpypi'
        self.indexUrls = indexUrls if indexUrls is not None else pipDefaultIndexes()

    @staticmethod
    def _normalizeName(packageName):
        return packageName.strip().lower()

    @staticmethod
    def _normalizeVersion(version):
        return version.strip()

    @staticmethod
    def _normalizeFilename(filename):
        return filename.strip()

    @staticmethod
    def _localFilename(packageName, version):
        return packageName + '/' + version

    def _mongoCollection_PackageIndex(self, mongoClient):
        mcPackageIndex = mongoClient[self.mongoDatabase][self.INDEX_COLLECTION_NAME]
        mcPackageIndex.ensure_index([('name', pymongo.ASCENDING), ('version', pymongo.ASCENDING)], unique=True)
        return mcPackageIndex

    def _mongoGridFS_PackageFiles(self, mongoClient):
        return gridfs.GridFS(mongoClient[self.mongoDatabase], collection=self.FILES_COLLECTION_NAME)

    def getPackageIndex(self, ctx, packageName, forceUpdate=False):
        packageName = self._normalizeName(packageName)

        # Read mongo index
        with pymongo.MongoClient(self.mongoUri) as mongoClient:
            mcPackageIndex = self._mongoCollection_PackageIndex(mongoClient)

            # Get the package index entries
            packageIndex = [MongoIndexEntry(name=x['name'],
                                            version=x['version'],
                                            filename=x['filename'],
                                            hash=x['hash'],
                                            hash_name=x['hash_name'],
                                            url=x['url'],
                                            datetime=x['datetime'])
                            for x in mcPackageIndex.find({'name': packageName})]
            packageVersions = set(x.version for x in packageIndex)

            # Index out-of-date?
            if not packageIndex or forceUpdate:
                ctx.log.info('Updating index for "%s"', packageName)

                # For each cached pypi index
                now = datetime.now()
                updatePackageIndex = []
                for indexUrl in self.indexUrls:
                    try:
                        # Get the pip index
                        pipPackages = pipPackageVersions(indexUrl, packageName)
                        if pipPackages is not None:
                            for pipPackage in sorted(pipPackages, key=_pipPackageSortKey):
                                # New package version?
                                pipPackageVersion = self._normalizeVersion(pipPackage.version)
                                if pipPackageVersion not in packageVersions:
                                    packageIndexEntry = MongoIndexEntry(name=packageName,
                                                                        version=pipPackageVersion,
                                                                        filename=pipPackage.link.filename,
                                                                        hash=pipPackage.link.hash,
                                                                        hash_name=pipPackage.link.hash_name,
                                                                        url=pipPackage.link.url,
                                                                        datetime=now)
                                    packageIndex.append(packageIndexEntry)
                                    updatePackageIndex.append(packageIndexEntry)
                                    packageVersions.add(pipPackageVersion)
                    except Exception as e:
                        ctx.log.warning('Package versions pip exception for "%s": %s', packageName, e)

                # Insert any new package versions
                if updatePackageIndex:
                    mcPackageIndex.insert(x._asdict() for x in updatePackageIndex)

        return packageIndex or None

    def getPackageStream(self, ctx, packageName, version, filename):
        packageName = self._normalizeName(packageName)
        version = self._normalizeVersion(version)
        filename = self._normalizeFilename(filename)

        # Find the package index entry
        packageEntry = next((pe for pe in self.getPackageIndex(ctx, packageName) if pe.version == version), None)
        if packageEntry is None or packageEntry.filename != filename:
            return None

        # File stream...
        def packageStream():

            # Open the gridfs
            with pymongo.MongoClient(self.mongoUri) as mongoClient:
                gfsPackageFiles = self._mongoGridFS_PackageFiles(mongoClient)

                # Package file not exist?
                gfsFilename = self._localFilename(packageName, version)
                if not gfsPackageFiles.exists(filename=gfsFilename):

                    # Download the file
                    assert packageEntry.url, 'Attempt to add package index entry without URL!!'
                    ctx.log.info('Downloading package (%s, %s) from "%s"', packageName, version, packageEntry.url)
                    req = urllib2.Request(url=packageEntry.url)
                    reqf = urllib2.urlopen(req)
                    try:
                        content = reqf.read()
                    finally:
                        reqf.close()

                    # Add the file
                    ctx.log.info('Adding package (%s, %s) (%d bytes)', packageName, version, len(content))
                    with gfsPackageFiles.new_file(filename=gfsFilename) as mf:
                        mf.write(content)

                # Stream the file chunks
                with gfsPackageFiles.get_last_version(filename=gfsFilename) as mf:
                    while True:
                        data = mf.read(self.STREAM_CHUNK_SIZE)
                        if not data:
                            break
                        yield data

        return packageStream

    def addPackage(self, ctx, packageName, version, filename, content):
        packageName = self._normalizeName(packageName)
        version = self._normalizeVersion(version)
        filename = self._normalizeFilename(filename)

        # Index exist?
        packageIndex = self.getPackageIndex(ctx, packageName) or ()
        packageExisting = next((pe for pe in packageIndex if pe.version == version), None)
        if packageExisting is not None:
            ctx.log.error('Attempt to add package index (%s, %s) that already exists!', packageName, version)
            return False

        # Open the gridfs
        with pymongo.MongoClient(self.mongoUri) as mongoClient:
            mcPackageIndex = self._mongoCollection_PackageIndex(mongoClient)
            gfsPackageFiles = self._mongoGridFS_PackageFiles(mongoClient)

            # File exist?
            gfsFilename = self._localFilename(packageName, version)
            if gfsPackageFiles.exists(filename=gfsFilename):
                ctx.log.error('Attempt to add package file (%s, %s) that already exists!', packageName, version)
                return False

            # Add the index
            ctx.log.info('Adding package index (%s, %s)', packageName, version)
            mcPackageIndex.insert(MongoIndexEntry(name=packageName,
                                                  version=version,
                                                  filename=filename,
                                                  hash=md5_new(content).hexdigest(),
                                                  hash_name='md5',
                                                  url=None,
                                                  datetime=datetime.now())._asdict())

            # Add the file
            ctx.log.info('Adding package file (%s, %s) (%d bytes)', packageName, version, len(content))
            with gfsPackageFiles.new_file(filename=gfsFilename) as mf:
                mf.write(content)

            return True
