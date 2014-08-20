#
# Copyright (C) 2014 Craig Hobbs
#

from collections import namedtuple
import posixpath

import pip
import pip.req


# Pip utilities
PipPackage = namedtuple('PipPackageVersion', ('versionKey', 'link', 'version'))

def pipDefaultIndexes():
    return (pip.cmdoptions.index_url.kwargs['default'],)

def pipPackageVersions(index, package):
    finder = pip.index.PackageFinder([], [index], use_wheel = False,
                                     allow_external = [package], allow_unverified = [package])
    packageReq = pip.req.InstallRequirement(package, None)
    packageLink = pip.req.Link(posixpath.join(index, packageReq.url_name, ''), trusted = True)
    packageVersions = []
    packageExists = False
    for packagePage in finder._get_pages([packageLink], packageReq):
        packageExists = True
        packageVersions.extend(PipPackage(*pv) for pv in
                               finder._package_versions(packagePage.links, packageReq.name.lower()))
    return packageVersions if packageExists else None
