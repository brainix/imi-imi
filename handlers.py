#------------------------------------------------------------------------------#
#   handlers.py                                                                #
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

"""Request handlers."""


import cgi
import datetime
import logging
import operator
import os
import traceback
import urllib

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

import packages
import simplejson

from config import DATETIME_FORMAT, DEBUG, HTTP_CODE_TO_TITLE, LIVE_SEARCH_URL
from config import NUM_POPULAR_BOOKMARKS, NUM_POPULAR_TAGS, POPULAR_CACHE_SECS
from config import RSS_NUM_ITEMS, SEARCH_CACHE_SECS, TEMPLATES
import decorators
import index
import models
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
            active_tab = 'imi-imi'
        else:
            active_tab = ''
        if page not in ('home', 'rss',) and current_user is not None:
            self.redirect('/users/' + current_user.email())
        rss_url = self._get_rss_url()
        if page == 'rss':
            references, more = self._get_bookmarks(references=True,
                                                   per_page=RSS_NUM_ITEMS)
            return self._serve_rss(rss_url=rss_url, references=references,
                                   saved_by='everyone')
        bookmarks, tags = self._popular_bookmarks(), self._popular_tags()
        values = {'title': 'social bookmarking', 'rss_url': rss_url,
            'login_url': login_url, 'current_user': current_user,
            'logout_url': logout_url, 'active_tab': active_tab,
            'bookmarks': bookmarks, 'tags': tags, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))

    @decorators.memcache_results(POPULAR_CACHE_SECS)
    def _popular_bookmarks(self):
        """ """
        bookmarks = models.Bookmark.all().filter('public =', True)
        bookmarks = bookmarks.order('-popularity').order('-updated')
        bookmarks = bookmarks.fetch(NUM_POPULAR_BOOKMARKS)
        return bookmarks

    @decorators.memcache_results(POPULAR_CACHE_SECS)
    def _popular_tags(self):
        """ """
        tags = models.Keychain.all().filter('public =', True)
        tags = tags.order('-popularity').order('-updated')
        tags = tags.fetch(NUM_POPULAR_TAGS)
        max_popularity = tags[0].popularity
        for tag in tags:
            tag.popularity /= max_popularity
        tags = sorted(tags, key=operator.attrgetter('word'))
        return tags


class Users(index.RequestHandler, search.RequestHandler, rss.RequestHandler,
            _RequestHandler):
    """Request handler to serve /users pages."""

    @decorators.no_browser_cache
    def get(self, target_email=None, before=None):
        """Show the specified user's bookmarks."""
        snippet = bool(before)
        file_name = 'index.html' if not snippet else 'references.html'
        path = os.path.join(TEMPLATES, 'bookmarks', file_name)
        login_url, current_user, logout_url = self._get_user()
        rss_url = self._get_rss_url()
        if not target_email:
            return self._serve_error(404)
        target_email = target_email.replace('%40', '@')
        active_tab = current_user and current_user.email() == target_email
        active_tab = 'imi-imi' if active_tab else ''
        target_user = users.User(email=target_email)
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
        references, more = self._get_bookmarks(references=True,
                                               query_users=[target_user],
                                               before=before)
        if more:
            earliest_so_far = references[-1].updated.strftime(DATETIME_FORMAT)
            more_url = '/users/' + target_email + '/' + earliest_so_far
        else:
            more_url = None
        values = {'snippet': snippet, 'title': title, 'rss_url': rss_url,
            'login_url': login_url, 'current_user': current_user,
            'logout_url': logout_url, 'active_tab': active_tab,
            'target_user': target_user, 'references': references,
            'more_url': more_url, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))

    @decorators.no_browser_cache
    @decorators.require_login
    def post(self):
        """Create, update, or delete a bookmark."""
        current_user = target_user = users.get_current_user()
        url_to_create = self.request.get('url_to_create')
        bookmark_key = self.request.get('bookmark_key')
        reference_key_to_update = self.request.get('reference_key_to_update')
        reference_key_to_delete = self.request.get('reference_key_to_delete')

        if url_to_create or bookmark_key and reference_key_to_update:
            path = os.path.join(TEMPLATES, 'bookmarks', 'references.html')
            if url_to_create:
                reference = self._create_bookmark(url_to_create, True)
            else:
                reference = self._update_bookmark(bookmark_key,
                                                  reference_key_to_update, True)
            references = [reference] if reference is not None else []
            values = {'snippet': True, 'current_user': current_user,
                'target_user': target_user, 'references': references,}
            self.response.out.write(template.render(path, values, debug=DEBUG))
        elif bookmark_key and reference_key_to_delete:
            self._delete_bookmark(bookmark_key, reference_key_to_delete)
        else:
            _log.error('/users got POST request but no bookmark to create, '
                       'update, or delete')


class LiveSearch(search.RequestHandler, _RequestHandler):
    """Request handler to serve /live_search pages."""

    def get(self):
        """Someone is typing a search query.  Provide some live search results.

        This method gets called every time anyone types a single letter in the
        search box.  Keep this method as efficient as possible and aggressively
        cache its results.
        """
        query = self.request.get('query').replace(' ', '%20').lower()
        html = self._live_search(query)
        self.response.out.write(html)

    @decorators.memcache_results(SEARCH_CACHE_SECS)
    def _live_search(self, query):
        path = os.path.join(TEMPLATES, 'common', 'live_search.html')
        url = LIVE_SEARCH_URL % query
        url, status_code, mime_type, suggestions = utils.fetch_content(url)
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
        return html


class Search(search.RequestHandler, _RequestHandler):
    """Request handler to serve /search pages."""

    @decorators.no_browser_cache
    def get(self):
        """Given a search query, show related bookmarks, sorted by relevance."""
        try:
            query_user, query_users, query_words, page = self._parse_query()
        except ValueError:
            return self._serve_error(404)
        snippet = page != 0
        file_name = 'index.html' if not snippet else 'bookmarks.html'
        path = os.path.join(TEMPLATES, 'bookmarks', file_name)
        login_url, current_user, logout_url = self._get_user()

        if not query_words:
            # This is an Easter egg, but an intentional and a useful one.  If we
            # got a blank search query, show all of the bookmarks sorted reverse
            # chronologically.
            title = 'all bookmarks'
            bookmarks, more = self._get_bookmarks(page=page)
        else:
            title = 'bookmarks'
            if query_user:
                title += ' saved by' + query_user.nickname()
            if query_words:
                title += ' related to' + ' '.join(query_words)
            bookmarks, more = self._search_bookmarks(query_users=query_users,
                                                     query_words=query_words,
                                                     page=page)
        more_url = self._compute_more_url() if more else None

        values = {'snippet': snippet, 'title': title, 'login_url': login_url,
            'current_user': current_user, 'logout_url': logout_url,
            'target_words': query_words, 'bookmarks': bookmarks,
            'more_url': more_url, 'debug': DEBUG,}
        self.response.out.write(template.render(path, values, debug=DEBUG))

    def _parse_query(self):
        """ """
        query_user = self.request.get('user')
        query_user = users.User(email=query_user) if query_user else query_user
        query_users = [query_user] if query_user else []
        query_words = self.request.get('query')
        query_words = query_words.replace('+', ' ')
        query_words = query_words.replace('%20', ' ')
        query_words = utils.extract_words_from_string(query_words)
        page = self.request.get('page', default_value='0')
        page = int(page)
        return query_user, query_users, query_words, page

    def _compute_more_url(self):
        """ """
        path, query = self.request.path, self.request.query
        query, index = cgi.parse_qsl(query), 0
        for index in range(len(query)):
            if query[index][0] == 'page':
                break
        page = int(query[index][1]) if index < len(query) else 0
        if index < len(query):
            query.remove(index)
        query.insert(index, ('page', str(page + 1)))
        query = urllib.urlencode(query)
        more_url = path + '?' + query
        return more_url


class API(index.RequestHandler, search.RequestHandler, _RequestHandler):
    """Request handler to expose imi-imi's functionality through an API.
    
    imi-imi exposes RESTful API calls which return JSON data.  This is similar
    to Twitter's API, and following Twitter's API design decisions is probably a
    safe bet.  ;-)
    """

    @decorators.no_browser_cache
    def get(self):
        """ """
        method = self.request.get('method')
        self.response.headers['Content-Type'] = 'application/json'
        if method == 'normalize-url':
            obj = self._normalize_url()
        if method == 'auto-tag':
            obj = self._auto_tag()
        else:
            obj = self._serve_error(404, 'Unrecognized method "%s".' % method)
        self.response.out.write(simplejson.dumps(obj))

    def _normalize_url(self):
        """ """
        url = self.request.get('url')
        if not url:
            return self._serve_error(406, '"url" parameter not specified.')
        return utils.normalize_url(url)

    def _auto_tag(self):
        """ """
        url = self.request.get('url')
        html = self.request.get('html')
        if not url and not html:
            return self._serve_error(406, 'Both "url" and "html" parameters specified.')
        if url and html:
            return self._serve_error(406, 'Neither "url" nor "html" parameter specified.')
        if url:
            url, mime_type, title, words, html_hash = utils.tokenize_url(url)
        elif html:
            title, words, hash = utils.tokenize_html(html)
        stop_words, stop_words_hash = utils.read_stop_words()
        tags = utils.auto_tag(words, stop_words)
        return tags

    def _serve_error(self, error_code, error_message):
        """Houston, we have a problem...  Serve an error page."""
        if not error_code in HTTP_CODE_TO_TITLE:
            error_code = 500
        error_message = HTTP_CODE_TO_TITLE[error_code] + ': ' + error_message
        self.error(error_code)
        return error_message
