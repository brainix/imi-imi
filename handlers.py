#------------------------------------------------------------------------------#
#   handlers.py                                                                #
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

"""Request handlers."""


import cgi
import datetime
import functools
import logging
import os
import traceback

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import packages
import simplejson

from config import DATETIME_FORMAT, DEBUG, FETCH_GOOD_STATUSES
from config import HTTP_CODE_TO_TITLE, LIVE_SEARCH_URL, RSS_NUM_ITEMS
from config import SEARCH_CACHE_SECS, TEMPLATES
import decorators
import index
import rss
import search
import utils


_log = logging.getLogger(__name__)


class _RequestHandler(webapp.RequestHandler):
    """Base request handler, from which other request handlers inherit."""

    def handle_exception(self, exception, debug_mode):
        """Houston, we have a problem...  Handle a 500 internal server error."""
        error_message = traceback.format_exc()  # Get the traceback.
        _log.critical(error_message)            # Log the traceback.
        self._serve_error(500)                  # Serve the error page.

    def _serve_error(self, error_code):
        """Houston, we have a problem...  Serve an error page."""
        if not error_code in HTTP_CODE_TO_TITLE:
            error_code = 500
        path = os.path.join(TEMPLATES, 'home', 'error.html')
        title = HTTP_CODE_TO_TITLE[error_code].lower()
        login_url, current_user, logout_url = self._get_user()
        error_url = self.request.url.split('//', 1)[-1]
        values = {'title': title, 'login_url': login_url,
            'current_user': current_user, 'logout_url': logout_url,
            'error_code': error_code, 'error_url': error_url, 'debug': DEBUG,}
        self.error(error_code)
        self.response.out.write(template.render(path, values, debug=DEBUG))

    def _get_user(self):
        """Return a login URL, the current user, and a logout URL."""
        login_url = users.create_login_url('/')
        current_user = users.get_current_user()
        logout_url = users.create_logout_url('/')
        return login_url, current_user, logout_url


class Home(search.RequestHandler, rss.RequestHandler, _RequestHandler):
    """Request handler to serve / pages."""

    @decorators.no_browser_cache
    def get(self, page=''):
        """Serve a get request for /.  Serve the homepage or site-wide RSS feed.
        
        This method doubles as a catch-all for URLs that don't map to any other
        request handler.  If we didn't receive a page keyword argument, the user
        requested /, so serve the home page.  If page is 'home' or 'rss', serve
        the home page or site-wide RSS feed, respectively.  If page is anything
        else, the user requested a URL for something that doesn't exist, so
        serve a 404.
        """
        if page.endswith('/'):
            page = page[:-1]
        if page not in ('', 'home', 'rss',):
            return self._serve_error(404)
        path = os.path.join(TEMPLATES, 'home', 'index.html')
        login_url, current_user, logout_url = self._get_user()
        if page in ('', 'home',) and current_user is None:
            active_tab = 'grab-it'
        else:
            active_tab = ''
        if page not in ('home', 'rss',) and current_user is not None:
            self.redirect('/users/' + current_user.email())
        rss_url = self._get_rss_url()
        if page == 'rss':
            bookmarks, more = self._get_bookmarks(per_page=RSS_NUM_ITEMS)
            return self._serve_rss(rss_url=rss_url, bookmarks=bookmarks,
                                   saved_by='everyone')
        values = {'title': 'social bookmarking', 'rss_url': rss_url,
            'login_url': login_url, 'current_user': current_user,
            'logout_url': logout_url, 'active_tab': active_tab, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))


class Users(index.RequestHandler, search.RequestHandler, rss.RequestHandler,
            _RequestHandler):
    """Request handler to serve /users pages."""

    @decorators.no_browser_cache
    def get(self, target_email=None, before=None):
        """Show the specified user's bookmarks."""
        snippet = bool(before)
        file_name = 'index.html' if not snippet else 'bookmarks.html'
        path = os.path.join(TEMPLATES, 'bookmarks', file_name)
        login_url, current_user, logout_url = self._get_user()
        rss_url = self._get_rss_url()
        if not target_email:
            return self._serve_error(404)
        target_email = target_email.replace('%40', '@')
        if current_user is not None and current_user.email() == target_email:
            active_tab = 'grab-it'
        else:
            active_tab = ''
        target_user = users.User(target_email)
        title = 'bookmarks saved by %s' % target_user.nickname()
        if before == 'rss':
            saved_by = target_user.nickname()
            return self._serve_rss(rss_url=rss_url, saved_by=saved_by,
                                   query_users=[target_user])
        try:
            before = datetime.datetime.strptime(before, DATETIME_FORMAT)
        except (TypeError, ValueError):
            if before is not None:
                return self._serve_error(404)
            before = None
        bookmarks, more = self._get_bookmarks(query_users=[target_user],
                                              before=before)
        if more:
            earliest_so_far = bookmarks[-1].updated.strftime(DATETIME_FORMAT)
            more_url = '/users/' + target_email + '/' + earliest_so_far
        else:
            more_url = None
        values = {'snippet': snippet, 'title': title, 'rss_url': rss_url,
            'login_url': login_url, 'current_user': current_user,
            'logout_url': logout_url, 'active_tab': active_tab,
            'target_user': target_user, 'bookmarks': bookmarks,
            'more_url': more_url, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))

    @decorators.no_browser_cache
    @decorators.require_login
    @decorators.run_in_transaction
    def post(self):
        """Create, update, or delete a bookmark."""
        current_user = target_user = users.get_current_user()
        url_to_create = self._get_url('url_to_create')
        key_to_update = self.request.get('key_to_update')
        if key_to_update:
            key_to_update = int(cgi.escape(key_to_update))
        key_to_delete = self.request.get('key_to_delete')
        if key_to_delete:
            key_to_delete = int(cgi.escape(key_to_delete))

        if url_to_create or key_to_update:
            path = os.path.join(TEMPLATES, 'bookmarks', 'bookmarks.html')
            if url_to_create:
                bookmark = self._create_bookmark(url_to_create)
            elif key_to_update:
                bookmark = self._update_bookmark(key_to_update)
            bookmarks = [bookmark] if bookmark is not None else []
            values = {'snippet': True, 'current_user': current_user,
                'target_user': target_user, 'bookmarks': bookmarks,}
            self.response.out.write(template.render(path, values, debug=DEBUG))
        elif key_to_delete:
            self._delete_bookmark(key_to_delete)
        else:
            _log.error('/users got POST request but no bookmark to create, ' +
                       'update, or delete')

    def _get_url(self, url_input_name):
        """Parse and return the URL specified as an input in the request obj."""
        url = self.request.get(url_input_name)
        if url:
            url = cgi.escape(url)
            if not url.startswith(('http://', 'https://',)):
                url = 'http://' + url
        return url


def _cache_live_search(method):
    """Decorate the live search get method - cache its results."""
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        query = self.request.get('query').replace(' ', '%20').lower()
        key = '_live_search query: ' + query
        _log.debug("trying to retrieve cached suggestions for query '%s'" % key)
        html = memcache.get(key)
        if html is not None:
            _log.debug("retrieved cached suggestions for query '%s'" % key)
        else:
            _log.debug("couldn't retrieve cached suggestions for query '%s'" %
                       key)
            _log.debug("caching suggestions for query '%s'" % key)
            success, html = method(self, *args, **kwds)
            if success:
                try:
                    success = memcache.set(key, html, time=SEARCH_CACHE_SECS)
                except MemoryError:
                    success = False
            if success:
                _log.debug("cached suggestions for query '%s'" % key)
            else:
                _log.error("couldn't cache suggestions for query '%s'" % key)
        self.response.out.write(html)
    return wrap


class LiveSearch(search.RequestHandler, _RequestHandler):
    """Request handler to serve /live_search pages."""

    @_cache_live_search
    def get(self):
        """Someone is typing a search query.  Provide some live search results.

        This method gets called every time anyone types a single letter in the
        search box.  Keep this method as efficient as possible and aggressively
        cache its results.
        """
        query = self.request.get('query').replace(' ', '%20').lower()
        path = os.path.join(TEMPLATES, 'common', 'live_search.html')
        url = LIVE_SEARCH_URL % query
        status_code, mime_type, suggestions = utils.fetch_content(url=url)
        success = status_code in FETCH_GOOD_STATUSES
        if suggestions is not None:
            suggestions = suggestions[1:]
            suggestions = suggestions[suggestions.index('[')+2:]
            suggestions = suggestions[:-2]
            suggestions = suggestions.replace('"', '')
            suggestions = suggestions.split(',')
            suggestions = [s for s in suggestions if s]
            suggestions = [{'url': '/search/' + s.replace(' ', '_'),
                            'text': s,
                            'has_results': bool(self._num_relevant_results(s)),}
                           for s in suggestions]
        values = {'suggestions': suggestions,}
        html = template.render(path, values, debug=DEBUG)
        return success, html


class Search(search.RequestHandler, _RequestHandler):
    """Request handler to serve /search pages."""

    @decorators.no_browser_cache
    def get(self, query_url_component='', page='0'):
        """Given a search query, show related bookmarks, sorted by relevance."""
        snippet = page != '0'
        file_name = 'index.html' if not snippet else 'bookmarks.html'
        path = os.path.join(TEMPLATES, 'bookmarks', file_name)
        login_url, current_user, logout_url = self._get_user()
        query_words = utils.extract_words_from_string(query_url_component)
        try:
            page = int(page)
        except ValueError:
            return self._serve_error(404)
        if not query_words:
            # This is an Easter egg, but an intentional and a useful one.  If we
            # got a blank search query, show all of the bookmarks sorted reverse
            # chronologically.
            title = 'all bookmarks'
            bookmarks, more = self._get_bookmarks(page=page)
        else:
            title = 'bookmarks related to %s' % ' '.join(query_words)
            bookmarks, more = self._search_bookmarks(query_words=query_words,
                                                     page=page)
        if more:
            more_url = '/search/' + query_url_component + '/' + str(page + 1)
        else:
            more_url = None
        values = {'snippet': snippet, 'title': title, 'login_url': login_url,
            'current_user': current_user, 'logout_url': logout_url,
            'target_words': query_words, 'bookmarks': bookmarks,
            'more_url': more_url, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))


class API(index.RequestHandler, search.RequestHandler, _RequestHandler):
    """Request handler to expose grab-it's functionality through an API.
    
    grab-it exposes RESTful API calls which return JSON data.  This is similar
    to Twitter's API, and following Twitter's API design decisions is probably a
    safe bet.  ;-)
    """

    @decorators.no_browser_cache
    def get(self, method=None):
        """ """
        self.response.headers['Content-Type'] = 'application/json'
        if method == 'auto-tag':
            obj = self._auto_tag()
        else:
            obj = self._serve_error(404, 'Unrecognized method "%s".' % method)
        self.response.out.write(simplejson.dumps(obj))

    def _auto_tag(self):
        """ """
        url = self.request.get('url')
        html = self.request.get('html')
        if not url and not html:
            return self._serve_error(406, 'Both "url" and "html" parameters specified.')
        if url and html:
            return self._serve_error(406, 'Neither "url" nor "html" parameter specified.')
        if url:
            mime_type, title, tags = self._process_url(url)
        elif html:
            title, words, hash = utils.tokenize_html(html)
            stop_words, stop_words_hash = utils.read_stop_words()
            tags = utils.auto_tag(words=words, stop_words=stop_words)
        return tags

    def _serve_error(self, error_code, error_message):
        """Houston, we have a problem...  Serve an error page."""
        if not error_code in HTTP_CODE_TO_TITLE:
            error_code = 500
        error_message = HTTP_CODE_TO_TITLE[error_code] + ': ' + error_message
        self.error(error_code)
        return error_message
