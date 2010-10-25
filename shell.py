#!/usr/bin/python

#------------------------------------------------------------------------------#
#   shell.py                                                                   #
#                                                                              #
#   Copyright (c) 2009-2010, Code A La Mode, original authors.                 #
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

Some of this code was written by Nick Johnson and swiftly yoinked by Raj Shah.
See:
    http://code.google.com/appengine/articles/remote_api.html
"""


import code
import getpass
import optparse
import os
import sys


def main():
    """Launch a Python console able to interact with imi-imi's datastore."""
    # Parse the command-line arguments:
    parser = _config_parser()
    app_id, host, auth_domain, email, base_dir = _parse_args(parser)

    # Set the environment variables required to authenticate in order to do
    # anything "interesting" with/to the datastore:
    os.environ['AUTH_DOMAIN'], os.environ['USER_EMAIL'] = auth_domain, email

    # Get the necessary local Google App Engine modules:
    remote_api_stub = _import_modules(parser, base_dir)

    # Connect to the remote datastore:
    remote_api_stub.ConfigureRemoteDatastore(app_id, '/remote_api', _auth, host)

    # Finally, launch the interactive console:
    code.interact('%s shell' % app_id, None, locals())


def _config_parser():
    """Configure the command-line argument parser."""
    usage = '%prog [--host=app-id.appspot.com] [--auth_domain=gmail.com] '
    usage += '[--email=brainix@gmail.com] '
    usage += '[--base_dir=/usr/local/google_appengine] app-id'
    parser = optparse.OptionParser(description=__doc__, usage=usage)
    parser.add_option('--host', dest='host', default=None,
                      help='Google App Engine app host name')
    parser.add_option('--auth_domain', dest='auth_domain', default='gmail.com',
                      help='authentication domain')
    parser.add_option('--email', dest='email', default='brainix@gmail.com',
                      help='email address')
    parser.add_option('--base_dir', dest='base_dir', default=_base_dir(),
                      help='directory where Google App Engine SDK installed')
    return parser


def _base_dir():
    """Return the default base (top-level) directory containing the GAE SDK."""
    if sys.platform == 'win32':
        base_dir = os.path.join('C:\\', 'Program Files', 'Google',
                                'google_appengine')
    else:
        base_dir = os.path.join('/', 'usr', 'local', 'google_appengine')
    return base_dir


def _parse_args(parser):
    """Parse the command-line arguments.

    If the user provided incorrect or insufficient command-line arguments, then
    print usage information and exit the shell.
    """
    opts, args = parser.parse_args(sys.argv[1:])
    if len(args) != 1:
        parser.error('exactly one argument required: Google App Engine app ID')
    app_id = args[0]
    host = opts.host if opts.host is not None else app_id + '.appspot.com'
    auth_domain, email, base_dir = opts.auth_domain, opts.email, opts.base_dir
    if not os.path.isdir(base_dir):
        parser.error('%s not a directory containing Google App Engine SDK' %
                     base_dir)
    return app_id, host, auth_domain, email, base_dir


def _import_modules(parser, base_dir):
    """Import and return the necessary local Google App Engine modules.

    This is a little bit tricky because the Google App Engine SDK directories
    are not in the Python path.
    """
    # Enumerate the directories containing the Google App Engine modules:
    google_app_engine_dirs = (
        base_dir,
        os.path.join(base_dir, 'lib', 'fancy_urllib'),
        os.path.join(base_dir, 'lib', 'yaml', 'lib'),
    )

    # Add those directories to the Python path:
    for dir in google_app_engine_dirs:
        if not dir in sys.path:
            sys.path.append(dir)

    # Finally, we can import the Google App Engine modules:
    try:
        from google.appengine.ext.remote_api import remote_api_stub
    except ImportError:
        parser.error('%s not a directory containing Google App Engine SDK' %
                     base_dir)
    return remote_api_stub


def _auth():
    """Get and return a username and password.

    This function gets called the first time the user attempts some datastore
    operation that requires authentication.
    """
    return raw_input('username: '), getpass.getpass('password: ')


if __name__ == '__main__':
    main()
