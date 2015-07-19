#
# Copyright (C) 2014 Craig Hobbs
#

from setuptools import setup

tests_require = []

setup(
    name = 'mrpypi',
    version = '0.2.0',
    author = 'Craig Hobbs',
    author_email = 'craigahobbs@gmail.com',
    description = 'Simple, reliable local pypy cache.',
    keywords = 'pypi mirror',
    url = 'https://github.com/craigahobbs/mrpypi',
    license = 'MIT',
    classifiers = [
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    packages = ['mrpypi'],
    install_requires = [
        'chisel >= 0.8.25',
        'pymongo >= 2.6',
        'pip >= 7.1',
    ],
    test_suite='mrpypi.tests',
    tests_require = tests_require,
    extras_require = {
        'tests': tests_require,
    },
)
