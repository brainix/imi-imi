#------------------------------------------------------------------------------#
#   rss.py                                                                     #
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
"""RSS functionality."""


import cStringIO
import datetime
import logging
import operator

from google.appengine.ext import webapp

import packages
from pyrss2gen import PyRSS2Gen

from config import RSS_NUM_ITEMS, RSS_NUM_TAGS, RSS_CACHE_SECS
import decorators


_log = logging.getLogger(__name__)


class RequestHandler(webapp.RequestHandler):
    """Base request handler, from which other request handlers inherit."""

    def _get_rss_url(self):
        """Compute the URL to the RSS feed corresponding to the current page."""
        uri = self.request.uri
        if uri.endswith('/'):
            uri = uri.rsplit('/', 1)[0]
        if uri.endswith('/rss'):
            # Oops.  The current page *is* an RSS feed.  Just return the current
            # page's URL (to prevent recursive RSS feeds - an RSS feed's RSS
            # feed).
            rss_url = uri
        elif uri.endswith('/home'):
            rss_url = uri.rsplit('/home', 1)[0] + '/rss'
        else:
            rss_url = uri + '/rss'
        return rss_url

    def _serve_rss(self, *args, **kwds):
        """Serve the XML for an RSS feed for the given users' bookmarks."""
        xml = self._compute_rss(**kwds)
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(xml)

    @decorators.memcache_results(cache_secs=RSS_CACHE_SECS)
    def _compute_rss(self, saved_by='everyone', query_users=tuple(),
                     num_rss_items=RSS_NUM_ITEMS, num_rss_tags=RSS_NUM_TAGS):
        """Compute the XML for an RSS feed for the given users' bookmarks."""
        title = 'imi-imi - bookmarks saved by %s' % saved_by
        link, items = self.request.uri.rsplit('/rss', 1)[0], []
        kwds = {'references': True, 'query_users': query_users,
                'per_page': num_rss_items}
        num_bookmarks, references, more = self._get_bookmarks(**kwds)
        for reference in references:
            bookmark, tags = reference.bookmark, []
            for word, count in zip(bookmark.words, bookmark.counts):
                tags.append({'word': word, 'count': count,})
            tags = sorted(tags, key=operator.itemgetter('count'), reverse=True)
            tags = tags[:num_rss_tags]
            description = ' '.join([tag['word'] for tag in tags])
            item = PyRSS2Gen.RSSItem(title=bookmark.title,
                                     link=bookmark.url,
                                     author=reference.user.nickname(),
                                     description=description,
                                     pubDate=reference.updated)
            items.append(item)
        rss = PyRSS2Gen.RSS2(title=title, link=link, description=title,
                             lastBuildDate=datetime.datetime.now(), items=items)
        stream = cStringIO.StringIO()
        rss.write_xml(stream)
        xml = stream.getvalue()
        stream.close()
        return xml
