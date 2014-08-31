#
# Copyright (C) 2014 Craig Hobbs
#

from collections import namedtuple
from datetime import datetime, timedelta
import md5
import urllib2

import gridfs # pymongo
import pymongo

from .indexUtil import pipDefaultIndexes, pipPackageVersions


MongoIndexEntry = namedtuple('MongoIndexEntry', ('name', 'version', 'filename', 'hash', 'hash_name', 'url', 'datetime'))


class MongoIndex(object):
    __slots__ = ('mongoUri', 'mongoDatabase', 'indexCollection', 'fsCollection', 'indexUrls', 'indexTTL')

    INDEX_COLLECTION_NAME = 'index'
    FILES_COLLECTION_NAME = 'fs'
    STREAM_CHUNK_SIZE = 4096

    def __init__(self, mongoUri = None, mongoDatabase = None, indexUrls = None, indexTTL = None):

        self.mongoUri = mongoUri if mongoUri is not None else 'mongodb://localhost:27017'
        self.mongoDatabase = mongoDatabase if mongoDatabase is not None else 'mrpypi'
        self.indexUrls = indexUrls if indexUrls is not None else pipDefaultIndexes()
        self.indexTTL = indexTTL if indexTTL is not None else timedelta(days = 7)


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
        mcPackageIndex.ensure_index([('name', pymongo.ASCENDING), ('version', pymongo.ASCENDING)], unique = True)
        return mcPackageIndex

    def _mongoGridFS_PackageFiles(self, mongoClient):
        return gridfs.GridFS(mongoClient[self.mongoDatabase], collection = self.FILES_COLLECTION_NAME)


    def getPackageIndex(self, ctx, packageName, forceUpdate = False):
        packageName = self._normalizeName(packageName)

        # Read mongo index
        with pymongo.MongoClient(self.mongoUri) as mongoClient:
            mcPackageIndex = self._mongoCollection_PackageIndex(mongoClient)

            # Get the package index entries
            localIndex = [MongoIndexEntry(name = x['name'],
                                          version = x['version'],
                                          filename = x['filename'],
                                          hash = x['hash'],
                                          hash_name = x['hash_name'],
                                          url = x['url'],
                                          datetime = x['datetime'])
                          for x in mcPackageIndex.find({'name': packageName})]
            localIndexExists = len(localIndex) != 0

            # Index out-of-date?
            now = datetime.now()
            if (forceUpdate or not localIndexExists or
                (any(pe for pe in localIndex if pe.url is not None) and
                 max(pe.datetime for pe in localIndex if pe.url is not None) - now > self.indexTTL)):

                ctx.log.info('Updating index for "%s"', packageName)

                # Read remote index
                remoteIndex = []
                remoteExists = False
                remoteVersions = set()
                for indexUrl in self.indexUrls:
                    try:
                        pipPackages = pipPackageVersions(indexUrl, packageName)
                        if pipPackages is not None:
                            remoteExists = True
                            for pipPackage in pipPackages:
                                if pipPackage.version not in remoteVersions:
                                    remoteVersions.add(pipPackage.version)
                                    remoteIndex.append(MongoIndexEntry(name = packageName,
                                                                       version = pipPackage.version,
                                                                       filename = pipPackage.link.filename,
                                                                       hash = pipPackage.link.hash,
                                                                       hash_name = pipPackage.link.hash_name,
                                                                       url = pipPackage.link.url,
                                                                       datetime = now))
                    except Exception as e:
                        ctx.log.warning('Package versions pip exception for "%s": %s', packageName, e)

                # Remote package exist?
                if remoteExists:

                    #!! Update persistent index...
                    localIndex = remoteIndex
                    localIndexExists = True
                    mcPackageIndex.insert(x._asdict() for x in remoteIndex)

        return localIndex if localIndexExists else None


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
                if not gfsPackageFiles.exists(filename = gfsFilename):

                    # Download the file
                    assert packageEntry.url, 'Attempt to add package index entry without URL!!'
                    ctx.log.info('Downloading package (%s, %s) from "%s"', packageName, version, packageEntry.url)
                    req = urllib2.Request(url = packageEntry.url)
                    reqf = urllib2.urlopen(req)
                    try:
                        content = reqf.read()
                    finally:
                        reqf.close()

                    # Add the file
                    ctx.log.info('Adding package (%s, %s) (%d bytes)', packageName, version, len(content))
                    with gfsPackageFiles.new_file(filename = gfsFilename) as mf:
                        mf.write(content)

                # Stream the file chunks
                with gfsPackageFiles.get_last_version(filename = gfsFilename) as mf:
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
            if gfsPackageFiles.exists(filename = gfsFilename):
                ctx.log.error('Attempt to add package file (%s, %s) that already exists!', packageName, version)
                return False

            # Add the index
            ctx.log.info('Adding package index (%s, %s)', packageName, version)
            mcPackageIndex.insert(MongoIndexEntry(name = packageName,
                                                  version = version,
                                                  filename = filename,
                                                  hash = md5.new(content).hexdigest(),
                                                  hash_name = 'md5',
                                                  url = None,
                                                  datetime = datetime.now())._asdict())

            # Add the file
            ctx.log.info('Adding package file (%s, %s) (%d bytes)', packageName, version, len(content))
            with gfsPackageFiles.new_file(filename = gfsFilename) as mf:
                mf.write(content)

            return True