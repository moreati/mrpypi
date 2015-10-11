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

from argparse import ArgumentParser
from wsgiref.simple_server import make_server

from . import MrPyPi, MemoryIndex, MongoIndex
from .index_util import DEFAULT_PIP_INDEX
from .mongo_index import DEFAULT_MONGO_URI


def main():

    # Command line options
    parser = ArgumentParser(prog='mrpypi')
    parser.add_argument('-p', dest='port', type=int, default=8000, help='Server port number (default is 8000)')
    parser.add_argument('--index', dest='index_url', default=DEFAULT_PIP_INDEX, metavar='URL',
                        help='Specify the upstream pypi index URL (default is "{0}")'.format(DEFAULT_PIP_INDEX))
    parser.add_argument('--no-index', dest='index_url', action='store_const', const=None,
                        help='Don\'t use an upstream pypi index')
    parser.add_argument('--mongo', dest='mongo', action='store_true',
                        help='Use mongo database index')
    parser.add_argument('--mongo-uri', dest='mongo_uri', type=str, default=DEFAULT_MONGO_URI, metavar='URI',
                        help='Mongo database URI (default is "{0}")'.format(DEFAULT_MONGO_URI))
    args = parser.parse_args()

    # Create the index
    print('Upstream pypi index URL: {0}'.format(args.index_url))
    if args.mongo:
        print('Mongo index with URI: {0}'.format(args.mongo_uri))
        index = MongoIndex(index_url=args.index_url, mongo_uri=args.mongo_uri)
    else:
        print('Using memory index')
        index = MemoryIndex(index_url=args.index_url)

    # Start the application
    print('Serving on port {0}...'.format(args.port))
    make_server('', args.port, MrPyPi(index)).serve_forever()


if __name__ == '__main__':
    main()
