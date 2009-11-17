#------------------------------------------------------------------------------#
#   rss.py                                                                     #
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

"""RSS functionality."""


import cStringIO
import datetime
import functools
import logging
import operator

from google.appengine.api import memcache
from google.appengine.ext import webapp

import packages
from pyrss2gen import PyRSS2Gen

from config import RSS_NUM_ITEMS, RSS_NUM_TAGS, RSS_CACHE_SECS


_log = logging.getLogger(__name__)


def _cache_rss(method):
    """Decorate an RSS request - cache and serve its resulting XML.
    
    While trolling through grab-it's Google App Engine dashboard
    (http://appengine.google.com/dashboard?&app_id=grab-it), I discovered
    that computing RSS feeds is pretty expensive.  It's probably worth caching
    computed RSS feeds.
    """
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        method_name = method.func_name
        rss_url = kwds.get('rss_url')
        if rss_url.endswith('/'):
            rss_url = rss_url[:-1]
        key = method_name + ' url: ' + rss_url
        _log.debug("trying to retrieve cached XML for RSS '%s'" % key)
        xml = memcache.get(key)
        if xml is not None:
            _log.debug("retrieved cached XML for RSS '%s'" % key)
        else:
            _log.debug("couldn't retrieve cached XML for RSS '%s'" % key)
            _log.debug("caching XML for RSS '%s'" % key)
            xml = method(self, *args, **kwds)
            try:
                success = memcache.set(key, xml, time=RSS_CACHE_SECS)
            except MemoryError:
                success = False
            if success:
                _log.debug("cached XML for RSS '%s'" % key)
            else:
                _log.error("couldn't cache XML for RSS '%s'" % key)
        self.response.headers['Content-Type'] = 'application/rss+xml'
        self.response.out.write(xml)
    return wrap


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

    @_cache_rss
    def _serve_rss(self, rss_url=None, saved_by='everyone', bookmarks=tuple(),
                   query_users=tuple(), num_rss_items=RSS_NUM_ITEMS,
                   num_rss_tags=RSS_NUM_TAGS):
        """Return the XML for an RSS feed for the specified users' bookmarks."""
        title = 'grab-it - bookmarks saved by %s' % saved_by
        link = self.request.uri.rsplit('/rss', 1)[0]
        if not bookmarks:
            bookmarks, more = self._get_bookmarks(query_users=query_users,
                                                  per_page=num_rss_items)
        items = []
        for bookmark in bookmarks:
            tags = []
            for word, count in zip(bookmark.words, bookmark.counts):
                tags.append({'word': word, 'count': count,})
            tags = sorted(tags, key=operator.itemgetter('count'), reverse=True)
            tags = tags[:num_rss_tags]
            description = ' '.join([tag['word'] for tag in tags])
            item = PyRSS2Gen.RSSItem(title=bookmark.title,
                                     link=bookmark.url,
                                     author=bookmark.user.nickname(),
                                     description=description,
                                     pubDate=bookmark.updated)
            items.append(item)
        rss = PyRSS2Gen.RSS2(title=title, link=link, description=title,
                             lastBuildDate=datetime.datetime.now(), items=items)
        stream = cStringIO.StringIO()
        rss.write_xml(stream)
        xml = stream.getvalue()
        stream.close()
        return xml
