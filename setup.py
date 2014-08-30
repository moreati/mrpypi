#
# Copyright (C) 2014 Craig Hobbs
#

from setuptools import setup

setup(
    name = 'mrpypi',
    version = '0.1.2',
    author = 'Craig Hobbs',
    author_email = 'craigahobbs@gmail.com',
    description = 'Simple, reliable local pypy cache.',
    keywords = 'pypi mirror',
    url = 'https://github.com/craigahobbs/mrpypi',
    license = 'MIT',
    classifiers = [
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    packages = ['mrpypi'],
    test_suite='mrpypi.tests',
    install_requires = [
        'chisel >= 0.8.3',
        'pymongo >= 2.6',
    ],
)
