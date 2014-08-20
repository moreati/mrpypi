#
# Copyright (C) 2014 Craig Hobbs
#

from collections import namedtuple
from datetime import datetime, timedelta
import md5
import posixpath
import urllib2

import gridfs # pymongo
from pymongo import MongoClient

from .indexUtil import pipDefaultIndexes, pipPackageVersions


MongoIndexEntry = namedtuple('MongoIndexEntry', ('name', 'version', 'filename', 'hash', 'hash_name', 'url', 'datetime'))


class MongoIndex(object):
    __slots__ = ('mongoUri', 'mongoDatabase', 'indexCollection', 'fsCollection', 'indexUrls', 'indexTTL')

    STREAM_CHUNK_SIZE = 4096

    def __init__(self, mongoUri = None, mongoDatabase = None, indexCollection = None, fsCollection = None,
                 indexUrls = None, indexTTL = None):

        self.mongoUri = mongoUri if mongoUri is not None else 'mongodb://localhost:27017'
        self.mongoDatabase = mongoDatabase if mongoDatabase is not None else 'mrpypi'
        self.indexCollection = indexCollection if indexCollection is not None else 'index'
        self.fsCollection = fsCollection if fsCollection is not None else 'fs'
        self.indexUrls = indexUrls if indexUrls is not None else pipDefaultIndexes()
        self.indexTTL = indexTTL if indexTTL is not None else timedelta(days = 7)


    def getPackageIndex(self, ctx, packageName):

        # Read mongo index
        with MongoClient(self.mongoUri) as mclient:
            mdb = mclient[self.mongoDatabase]
            mix = mdb[self.indexCollection]

            # Get the package index entries
            localIndex = [MongoIndexEntry(name = x['name'],
                                          version = x['version'],
                                          filename = x['filename'],
                                          hash = x['hash'],
                                          hash_name = x['hash_name'],
                                          url = x['url'],
                                          datetime = x['datetime'])
                          for x in mix.find({'name': packageName})]
            localIndexExists = len(localIndex) != 0

            # Index out-of-date?
            now = datetime.now()
            if (not localIndexExists or
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
                    mix.insert(x._asdict() for x in remoteIndex)

        return localIndex if localIndexExists else None


    def getPackageStream(self, ctx, packageName, version, filename):

        # Find the package index entry
        packageEntry = next((pe for pe in self.getPackageIndex(ctx, packageName) if pe.version == version), None)
        if packageEntry is None or packageEntry.filename != filename:
            return None

        # File stream...
        def packageStream():

            # Open the gridfs
            with MongoClient(self.mongoUri) as mclient:
                mdb = mclient[self.mongoDatabase]
                mfs = gridfs.GridFS(mdb, collection = self.fsCollection)

                # Package file not exist?
                mfsFilename = posixpath.join(packageEntry.name, packageEntry.version)
                if not mfs.exists(filename = mfsFilename):

                    # Download the file
                    assert packageEntry.url, 'Attempt to add package index entry without URL!!'
                    ctx.log.info('Downloading package (%s, %s) from "%s"', packageEntry.name, packageEntry.version, packageEntry.url)
                    req = urllib2.Request(url = packageEntry.url)
                    reqf = urllib2.urlopen(req)
                    try:
                        content = reqf.read()
                    finally:
                        reqf.close()

                    # Add the file
                    ctx.log.info('Adding package (%s, %s) (%d bytes)', packageEntry.name, packageEntry.version, len(content))
                    with mfs.new_file(filename = mfsFilename) as mf:
                        mf.write(content)

                # Stream the file chunks
                with mfs.get_last_version(filename = mfsFilename) as mf:
                    while True:
                        data = mf.read(self.STREAM_CHUNK_SIZE)
                        if not data:
                            break
                        yield data

        return packageStream


    def addPackage(self, ctx, packageName, version, filename, content):

        # Create the package index entry object
        packageEntry = MongoIndexEntry(name = packageName,
                                       version = version,
                                       filename = filename,
                                       hash = md5.new(content).hexdigest(),
                                       hash_name = 'md5',
                                       url = None,
                                       datetime = datetime.now())

        # Open the gridfs
        with MongoClient(self.mongoUri) as mclient:
            mdb = mclient[self.mongoDatabase]
            mix = mdb[self.indexCollection]
            mfs = gridfs.GridFS(mdb, collection = self.fsCollection)

            # Index exist?
            packageIndex = self.getPackageIndex(ctx, packageName) or ()
            packageExisting = next((pe for pe in packageIndex if pe.version == packageEntry.version), None)
            if packageExisting is not None:
                ctx.log.error('Attempt to add package index (%s, %s) that already exists!', packageEntry.name, packageEntry.version)
                return False

            # File exist?
            mfsFilename = posixpath.join(packageEntry.name, packageEntry.version)
            if mfs.exists(filename = mfsFilename):
                ctx.log.error('Attempt to add package file (%s, %s) that already exists!', packageEntry.name, packageEntry.version)
                return False

            # Add the index
            ctx.log.info('Adding package index (%s, %s)', packageEntry.name, packageEntry.version)
            mix.insert(packageEntry._asdict())

            # Add the file
            ctx.log.info('Adding package file (%s, %s) (%d bytes)', packageEntry.name, packageEntry.version, len(content))
            with mfs.new_file(filename = mfsFilename) as mf:
                mf.write(content)

            return True
