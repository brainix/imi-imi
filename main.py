#------------------------------------------------------------------------------#
#   main.py                                                                    #
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
"""It's time for the dog and pony show..."""


import cProfile
import cStringIO
import logging
import pstats

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from config import DEBUG, MAINTENANCE, PROFILING
from config import PROFILING_OUTPUT, PROFILING_SORT_BY, PROFILING_NUM_STATS
from config import PROFILING_CALLEES, PROFILING_CALLERS
import handlers


_log = logging.getLogger(__name__)


def main():
    """It's time for the dog and pony show..."""
    logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.INFO)
    template.register_template_library('filters')

    if MAINTENANCE:
        url_mapping = (
            ('(.*)',                handlers.Maintenance),  #
        )
    else:
        # This URL mapping operates by a "first-fit" model (rather than by a
        # "best- fit" model).  Therefore, keep these URL maps ordered from most
        # specific to most general.
        #
        # The final URL map matches every URL that none of the preceding maps
        # match.  If the requested URL "falls through" to the final map, then
        # we serve up a 404: not found page.
        url_mapping = (
            ('/search',             handlers.Search),       # /search
            ('/live_search',        handlers.LiveSearch),   # /live_search
            ('/users/(.*)/(.*)',    handlers.Users),        # /users/email@addr.com/before
            ('/users/(.*)',         handlers.Users),        # /users/email@addr.com
            ('/users',              handlers.Users),        # /users
            ('/rss',                handlers.RSS),          # /rss
            ('/about',              handlers.Home),         # /about
            ('/',                   handlers.Home),         # /
            ('(.*)',                handlers.NotFound),     # 404: Not Found.
        )

    app = webapp.WSGIApplication(url_mapping, debug=DEBUG)
    util.run_wsgi_app(app)


def profile(output='log', sort_by='time', num_stats=80,
            callees=False, callers=False):
    """Profile imi-imi's performance."""
    if not output in ('log', 'html',):
        message = "unintelligible profile output spec: %s " % output
        message += "(must be 'log' or 'html')"
        _log.critical(message)
        main()
    if not sort_by in ('time', 'cumulative',):
        message = "unintelligible profile sort order spec: %s " % sort_by
        message += "(must be 'time' or 'cumulative')"
        _log.critical(message)
        main()
    else:
        profile = cProfile.Profile()
        profile = profile.runctx('main()', globals(), locals())
        if output == 'html':
            print '<pre>'
            stats = pstats.Stats(profile)
        elif output == 'log':
            stream = cStringIO.StringIO()
            stats = pstats.Stats(profile, stream=stream)
        stats.sort_stats(sort_by)
        stats.print_stats(num_stats)
        if callees:
            stats.print_callees()
        if callers:
            stats.print_callers()
        if output == 'html':
            print '</pre>'
        elif output == 'log':
            _log.info("profile data:\n%s", stream.getvalue())


if __name__ == '__main__':
    if PROFILING:
        profile(output=PROFILING_OUTPUT, sort_by=PROFILING_SORT_BY,
                num_stats=PROFILING_NUM_STATS, callees=PROFILING_CALLEES,
                callers=PROFILING_CALLERS)
    else:
        main()
