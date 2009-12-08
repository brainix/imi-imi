#!/usr/bin/python

#------------------------------------------------------------------------------#
#   shell.py                                                                   #
#                                                                              #
#   Copyright (c) 2009, Code A La Mode, original authors.                      #
#                                                                              #
#       This file is part of imi-imi.                                          #
#                                                                              #
#       imi-imi is free software; you can redistribute it and/or modify        #
#       it under the terms of the GNU General Public License as published by   #
#       the Free Software Foundation, either version 3 of the License, or      #
#       (at your option) any later version.                                    #
#                                                                              #
#       imi-imi is distributed in the hope that it will be useful,             #
#       but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#       GNU General Public License for more details.                           #
#                                                                              #
#       You should have received a copy of the GNU General Public License      #
#       along with imi-imi.  If not, see <http://www.gnu.org/licenses/>.       #
#------------------------------------------------------------------------------#

"""Launch an interactive Python console with access to imi-imi's datastore.

This code was written by Nick Johnson and swiftly yoinked by Raj Shah.  See:
    http://code.google.com/appengine/articles/remote_api.html
"""


import code
import getpass
import optparse
import os
import sys

# Set the environment variables required to authenticate in order to do anything
# "interesting" to the datastore:
os.environ['AUTH_DOMAIN'] = 'gmail.com'
os.environ['USER_EMAIL'] = 'brainix@gmail.com'

# Enumerate the directories containing the Google App Engine modules on
# Unix-like operating systems:
GOOGLE_APP_ENGINE_DIRS = (
    os.path.join('/', 'usr', 'local', 'google_appengine'),
    os.path.join('/', 'usr', 'local', 'google_appengine', 'lib', 'yaml', 'lib'),
)

# Enumerate the directories containing the Google App Engine modules on Windows
# operating systems:
"""
GOOGLE_APP_ENGINE_DIRS = (
    os.path.join('C:\\', 'Program Files', 'Google', 'google_appengine'),
    os.path.join('C:\\', 'Program Files', 'Google', 'google_appengine', 'lib', 'yaml', 'lib'),
)
"""

# Add the directories containing the Google App Engine modules to the Python
# path:
for dir in GOOGLE_APP_ENGINE_DIRS:
    if not dir in sys.path:
        sys.path.append(dir)

from google.appengine.ext import db
from google.appengine.ext.remote_api import remote_api_stub


def main():
    """Launch a Python console able to interact with imi-imi's datastore."""
    app_id, host = parse_args()
    remote_api_stub.ConfigureRemoteDatastore(app_id, '/remote_api', auth, host)
    code.interact('%s shell' % app_id, None, locals())


def parse_args():
    """Parse the command-line arguments for the app ID and the host.

    If the user provided incorrect or insufficient command-line arguments, print
    usage information and exit the shell.
    """
    usage = '%prog [--host=app_id.appspot.com] app_id'
    parser = optparse.OptionParser(description=__doc__, usage=usage)
    parser.add_option('--host', dest='host', default=None,
                      help='Google App Engine app host name')
    opts, args = parser.parse_args(sys.argv[1:])
    try:
        app_id = args[0]
    except IndexError:
        parser.error('argument required: Google App Engine app ID')
    if len(args) > 1:
        parser.error('only one argument allowed: Google App Engine app ID')
    host = opts.host if opts.host is not None else app_id + '.appspot.com'
    return app_id, host


def auth():
    """Get and return a username and password.

    This function gets called the first time the user attempts some datastore
    operation that requires authentication.
    """
    return raw_input('username: '), getpass.getpass('password: ')


if __name__ == '__main__':
    main()
