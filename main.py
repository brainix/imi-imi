#------------------------------------------------------------------------------#
#   main.py                                                                    #
#                                                                              #
#   Copyright (c) 2009, Code A La Mode, original authors.                      #
#                                                                              #
#       This file is part of grab-it.                                          #
#                                                                              #
#       grab-it is free software; you can redistribute it and/or modify        #
#       it under the terms of the GNU General Public License as published by   #
#       the Free Software Foundation, either version 3 of the License, or      #
#       (at your option) any later version.                                    #
#                                                                              #
#       grab-it is distributed in the hope that it will be useful,             #
#       but WITHOUT ANY WARRANTY; without even the implied warranty of         #
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          #
#       GNU General Public License for more details.                           #
#                                                                              #
#       You should have received a copy of the GNU General Public License      #
#       along with grab-it.  If not, see <http://www.gnu.org/licenses/>.       #
#------------------------------------------------------------------------------#

"""It's time for the dog and pony show..."""


import cProfile
import cStringIO
import logging
import pstats

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from config import DEBUG
import handlers


_log = logging.getLogger(__name__)


def main():
    """It's time for the dog and pony show..."""
    logging.getLogger().setLevel(logging.DEBUG)
    template.register_template_library('filters')

    # This URL mapping operates by a "first-fit" model (rather than by a "best-
    # fit" model).  Therefore, keep these URL maps ordered from most specific to
    # most general.
    #
    # We don't actually paginate.  (Who in the hell would issue a search query
    # and then immediately click on result page 7?)  Instead, every time the
    # user clicks the "more results" button, we use AJAX to serve up an HTML
    # snippet to dynamically grow the results page.  In order to implement this
    # scheme, every URL that doesn't specify a page number serves up a full HTML
    # page, and every URL that does serves up only an HTML snippet.
    #
    # The final URL map matches every URL that none of the preceding maps match.
    # If the URL "falls through" to the final map, and if the URL is exactly
    # "/", we serve up the homepage.  However, if the URL is anything other than
    # "/", we serve up the 404 page.
    url_mapping = (
        ('/api/(.*)',           handlers.API),        # /api/method
        ('/api',                handlers.API),        # /api
        ('/search/(.*)/(.*)',   handlers.Search),     # /search/query/page_num
        ('/search/(.*)',        handlers.Search),     # /search/query
        ('/search',             handlers.Search),     # /search
        ('/live_search',        handlers.LiveSearch), # /search
        ('/users/(.*)/(.*)',    handlers.Users),      # /users/email@addr.com/page_num
        ('/users/(.*)',         handlers.Users),      # /users/email@addr.com
        ('/users',              handlers.Users),      # /users
        ('/(.*)',               handlers.Home),       # /
    )

    app = webapp.WSGIApplication(url_mapping, debug=DEBUG)
    util.run_wsgi_app(app)


def profile(output='log', sort_by='time', num_stats=80,
            callees=False, callers=False):
    """Profile grab-it's performance."""
    if not output in ('log', 'html',):
        _log.critical('unintelligible profile output spec: %s' % output)
        main()
    if not sort_by in ('time', 'cumulative',):
        _log.critical('unintelligible profile sort order spec: %s' % sort_by)
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
    main()
