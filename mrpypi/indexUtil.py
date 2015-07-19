#
# Copyright (C) 2014-2015 Craig Hobbs
#

from collections import namedtuple

from pip.cmdoptions import index_url
from pip.download import PipSession
from pip.index import FormatControl, PackageFinder


PipPackage = namedtuple('PipPackageVersion', ('version', 'link'))


def pipDefaultIndexes():
    return (index_url.keywords['default'],)


# pylint: disable=no-member,protected-access,unexpected-keyword-arg
def pipPackageVersions(index, package):
    formatControl = FormatControl(no_binary=(':all:'), only_binary=())
    session = PipSession()
    finder = PackageFinder([], [index], format_control=formatControl, session=session,
                           allow_external=[package], allow_unverified=[package])
    return [PipPackage(str(pv.version), pv.location) for pv in finder._find_all_versions(package)]
