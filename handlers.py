#------------------------------------------------------------------------------#
#   handlers.py                                                                #
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
"""Request handlers."""


import cgi
import datetime
import logging
import os
import traceback
import urllib

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

import packages
import simplejson

from config import DATETIME_FORMAT, DEBUG, HTTP_CODE_TO_TITLE, LIVE_SEARCH_URL
from config import NUM_POPULAR_BOOKMARKS, NUM_POPULAR_TAGS, POPULAR_CACHE_SECS
from config import RSS_NUM_ITEMS, SEARCH_CACHE_SECS, TEMPLATES
import auto_tag
import decorators
import emails
import fetch
import index
import models
import rss
import search


_log = logging.getLogger(__name__)


class _CommonRequestHandler(emails.RequestHandler, rss.RequestHandler,
                            index.RequestHandler, search.RequestHandler):
    """ """

    def handle_exception(self, exception, debug_mode):
        """Houston, we have a problem...  Handle an uncaught exception.

        This method overrides the webapp.RequestHandler class's
        handle_exception method.  This method gets called whenever there's an
        uncaught exception anywhere in the imi-imi code.
        """
        # Get and log the traceback.
        error_message = traceback.format_exc()
        _log.critical(error_message)

        # Determine the error code.
        if isinstance(exception, CapabilityDisabledError):
            # The only time this exception is thrown is when the datastore is
            # read-only for maintenance.  Gracefully degrade - throw a 503
            # error.  For more info, see: http://code.google.com/appengine/docs/python/howto/maintenance.html
            error_code = 503
        else:
            error_code = 500

        # Serve the error page.
        self._serve_error(error_code)                                                   # Serve the 500 error page.

    def _serve_error(self, error_code):
        """Houston, we have a problem...  Serve an error page."""
        if not error_code in HTTP_CODE_TO_TITLE:
            error_code = 500
        path, debug = os.path.join(TEMPLATES, 'home', 'error.html'), DEBUG
        title = HTTP_CODE_TO_TITLE[error_code].lower()
        login_url, current_user, current_account, logout_url = self._get_user()
        error_url = self.request.url.split('//', 1)[-1]
        self.error(error_code)
        self.response.out.write(template.render(path, locals(), debug=DEBUG))

    def _get_user(self):
        """Return a login URL, the current user, and a logout URL."""
        login_url = users.create_login_url('/')
        current_user = users.get_current_user()
        current_account = self._user_to_account(current_user)
        logout_url = users.create_logout_url('/')
        return login_url, current_user, current_account, logout_url

    def _user_to_account(self, user):
        """Given a user object, return its corresponding account object."""
        try:
            account_key = models.Account.key_name(user.email())
        except AttributeError:
            account = None
        else:
            account = models.Account.get_by_key_name(account_key)
        return account

    def _user_bookmarks(self, target_email=None, before=None, friends=False):
        """Show the specified user's bookmarks."""
        snippet = bool(before)
        file_name = 'index.html' if not snippet else 'references.html'
        path, debug = os.path.join(TEMPLATES, 'bookmarks', file_name), DEBUG
        rss_url = self._get_rss_url()
        login_url, current_user, current_account, logout_url = self._get_user()
        if not target_email:
            return self._serve_error(404)
        target_email = target_email.replace('%40', '@')
        target_user = users.User(email=target_email)
        target_account = self._user_to_account(target_user)
        if target_account is None:
            return self._serve_error(404)
        active_tab, saved_by = '', target_user.nickname()
        query_users = [target_user]
        if friends:
            if current_user == target_user:
                active_tab = 'imi-imi'
            saved_by += ' & friends'
            query_users.extend(target_account.following)
        title = 'bookmarks saved by ' + saved_by
        if before == 'rss':
            return self._serve_rss(saved_by=saved_by, query_users=query_users)
        try:
            before = datetime.datetime.strptime(before, DATETIME_FORMAT)
        except (TypeError, ValueError):
            if before is not None:
                return self._serve_error(404)
        kwds = {'references': True, 'query_users': query_users,
                'before': before}
        num_bookmarks, references, more = self._get_bookmarks(**kwds)
        if more:
            earliest_so_far = references[-1].updated.strftime(DATETIME_FORMAT)
            more_url = '/users/' + target_email + '/' + earliest_so_far
        else:
            more_url = None
        self.response.out.write(template.render(path, locals(), debug=DEBUG))


class _BaseRequestHandler(_CommonRequestHandler):
    """Abstract base class request handler."""

    def get(self, nonsense=''):
        """Abstract method to handle GET requests."""
        raise NotImplementedError

    def post(self, nonsense=''):
        """Abstract method to handle POST requests."""
        raise NotImplementedError


class Maintenance(_BaseRequestHandler):
    """Request handler to serve all requests when in maintenance mode."""

    def get(self, nonsense=''):
        """The site is under maintenance.  Serve a polite "bugger off" page."""
        path, debug = os.path.join(TEMPLATES, 'home', 'maintenance.html'), DEBUG
        title, in_maintenance = 'in surgery', True
        login_url, current_user, current_account, logout_url = self._get_user()
        self.response.out.write(template.render(path, locals(), debug=DEBUG))

    def post(self, nonsense=''):
        """ """
        pass


class NotFound(_BaseRequestHandler):
    """Request handler to serve a 404: Not Found error page."""

    def get(self, nonsense=''):
        """ """
        return self._serve_error(404)


class Home(_BaseRequestHandler):
    """Request handler to serve the homepage."""

    @decorators.no_browser_cache
    @decorators.create_account
    def get(self):
        """Serve a get request for / or /about.
        
        If an anonymous user requested /, then serve the homepage.  If a logged
        in user requested /, then redirect to that user's bookmarks page.  If
        either an anonymous user or a logged in user requested /about, then
        serve the homepage.
        """
        if self.request.path not in ('/', '/about',):
            return self._serve_error(404)
        path, debug = os.path.join(TEMPLATES, 'home', 'index.html'), DEBUG
        title = 'social bookmarking'
        rss_url = self._get_rss_url()
        login_url, current_user, current_account, logout_url = self._get_user()
        active_tab = 'imi-imi' if current_user is None else ''
        if self.request.path == '/' and current_user is not None:
            return self._user_bookmarks(target_email=current_user.email(),
                                        friends=True)
        self.response.out.write(template.render(path, locals(), debug=DEBUG))


class RSS(_BaseRequestHandler):
    """Request handler to serve the site-wide RSS feed."""

    @decorators.no_browser_cache
    def get(self):
        """ """
        return self._serve_rss()


class Users(_BaseRequestHandler):
    """Request handler to serve users' pages and perform CRUD on bookmarks."""

    @decorators.no_browser_cache
    def get(self, target_email=None, before=None):
        """Show the specified user's bookmarks."""
        return self._user_bookmarks(target_email=target_email, before=before,
                                    friends=False)

    @decorators.no_browser_cache
    @decorators.require_login
    @decorators.create_account
    def post(self):
        """Create, update, or delete a bookmark or following."""
        url_to_create = self.request.get('url_to_create')
        key = self.request.get('bookmark_key')
        bookmark = models.Bookmark.get_by_key_name(key) if key else None
        key = self.request.get('reference_key_to_update')
        reference_to_update = models.Reference.get_by_key_name(key, parent=bookmark) if key else None
        key = self.request.get('reference_key_to_delete')
        reference_to_delete = models.Reference.get_by_key_name(key, parent=bookmark) if key else None
        email_to_follow = self.request.get('email_to_follow')
        email_to_unfollow = self.request.get('email_to_unfollow')
        method, args, return_value = None, None, None

        if url_to_create or reference_to_update or reference_to_delete:
            method = self._crud_bookmark
            args = [url_to_create, reference_to_update, reference_to_delete]
        elif email_to_follow or email_to_unfollow:
            method = self._crud_following
            args = [email_to_follow, email_to_unfollow]
        else:
            _log.error('/users got POST request but no bookmark to create, '
                       'update, or delete and no user to follow or unfollow')

        if method is not None:
            return_value = method(*args)
        return return_value

    def _crud_bookmark(self, url_to_create, reference_to_update,
                       reference_to_delete):
        """Create, update, or delete a bookmark."""
        snippet = True
        current_user = target_user = users.get_current_user()
        if url_to_create or reference_to_update is not None:
            path = os.path.join(TEMPLATES, 'bookmarks', 'references.html')
            if url_to_create:
                reference = self._create_bookmark(url_to_create)
            elif reference_to_update.user == current_user:
                reference = self._update_bookmark(reference_to_update)
                reference.updated = datetime.datetime.now()
            else:
                reference = None
                _log.error("couldn't update reference (insufficient privileges")
            references = [reference] if reference is not None else []
            self.response.out.write(template.render(path, locals(),
                                                    debug=DEBUG))
        elif reference_to_delete is not None:
            if reference_to_delete.user == current_user:
                self._delete_bookmark(reference_to_delete)
            else:
                _log.error("couldn't delete reference (insufficient privileges")

    def _crud_following(self, email_to_follow, email_to_unfollow):
        """Create or delete a following."""
        path = os.path.join(TEMPLATES, 'bookmarks', 'follower.html')
        current_user = users.get_current_user()
        if current_user is None:
            _log.error("current user can't follow - not logged in?")
            return
        current_email = current_user.email()
        current_account = self._user_to_account(current_user)
        if current_account is None:
            _log.error("%s can't follow - has no imi-imi account" % current_email)
            return

        # From the Google App Engine API documentation:
        #   The email address is not checked for validity when the User object
        #   is created.  A User object with an email address that doesn't
        #   correspond to a valid Google account can be stored in the
        #   datastore, but will never match a real user.
        #
        # In other words, there's no meaningful error checking that we can do
        # on other_user.  For more information, see:
        #   http://code.google.com/appengine/docs/python/users/userclass.html#User
        other_email = email_to_follow if email_to_follow else email_to_unfollow
        other_user = users.User(email=other_email)
        if other_user is None:
            _log.error("can't follow %s - has no Google account" % other_email)
            return
        other_account = self._user_to_account(other_user)
        if other_account is None:
            _log.error("can't follow %s - has no imi-imi account" % other_email)
            return

        if email_to_follow:
            self._follow(current_email, current_user, current_account,
                         other_email, other_user, other_account)
        elif email_to_unfollow:
            self._unfollow(current_email, current_user, current_account,
                           other_email, other_user, other_account)

        other_account.popularity = len(other_account.followers)
        db.put([current_account, other_account])
        self.response.out.write(template.render(path, locals(), debug=DEBUG))

    def _follow(self, current_email, current_user, current_account,
                other_email, other_user, other_account):
        """ """
        created_following = False
        if other_user in current_account.following:
            _log.error('%s already following %s' % (current_email, other_email))
        else:
            current_account.following.append(other_user)
            created_following = True
        if current_user in other_account.followers:
            _log.error('%s already followed by %s' %
                       (other_email, current_email))
        else:
            other_account.followers.append(current_user)
            created_following = True

        # if created_following:
        #     self._email_following(current_account, other_account)

    def _unfollow(self, current_email, current_user, current_account,
                  other_email, other_user, other_account):
        """ """
        if not other_user in current_account.following:
            _log.error('%s already not following %s' %
                       (current_email, other_email))
        while other_user in current_account.following:
            current_account.following.remove(other_user)
        if not current_user in other_account.followers:
            _log.error('%s already not followed by %s' %
                       (other_email, current_email))
        while current_user in other_account.followers:
            other_account.followers.remove(current_user)


class LiveSearch(_BaseRequestHandler):
    """Request handler to serve live search HTML snippets."""

    def get(self):
        """Someone is typing a search query.  Provide some live search results.

        This method gets called every time anyone types a single letter in the
        search box.  Keep this method as efficient as possible.
        """
        query = self.request.get('query').replace(' ', '%20').lower()
        html = self._live_search(query)
        self.response.out.write(html)

    @decorators.memcache_results(cache_secs=SEARCH_CACHE_SECS)
    def _live_search(self, query):
        """Fetch & render HTML for the live search results for the given query.

        This method potentially gets called every time anyone types a single
        letter in the search box.  Keep this method as efficient as possible
        and aggressively cache its results.

        Google Suggest exposes a nice RESTful API.  To fetch suggestions for
        the query "raj", one would visit the URL:
            http://suggestqueries.google.com/complete/search?output=firefox&qu=raj

        And Google's suggestions would be returned in the form:
            '["raj",["rajaan bennett","rajon rondo","rajiv shah","raj kundra","raj rajaratnam","rajshri","raja bell","rajah","raj kundra wikipedia","raj patel"]]'

        """
        path = os.path.join(TEMPLATES, 'common', 'live_search.html')
        url = LIVE_SEARCH_URL % query
        url, status_code, mime_type, suggestions = fetch.Factory().fetch(url)
        if suggestions is not None:
            suggestions = suggestions[1:]                           # '"raj",["rajaan bennett","rajon rondo","rajiv shah","raj kundra","raj rajaratnam","rajshri","raja bell","rajah","raj kundra wikipedia","raj patel"]]'
            suggestions = suggestions[suggestions.index('[')+2:]    # 'rajaan bennett","rajon rondo","rajiv shah","raj kundra","raj rajaratnam","rajshri","raja bell","rajah","raj kundra wikipedia","raj patel"]]'
            suggestions = suggestions[:-2]                          # 'rajaan bennett","rajon rondo","rajiv shah","raj kundra","raj rajaratnam","rajshri","raja bell","rajah","raj kundra wikipedia","raj patel"'
            suggestions = suggestions.replace('"', '')              # 'rajaan bennett,rajon rondo,rajiv shah,raj kundra,raj rajaratnam,rajshri,raja bell,rajah,raj kundra wikipedia,raj patel'
            suggestions = suggestions.split(',')                    # ['rajaan bennett', 'rajon rondo', 'rajiv shah', 'raj kundra', 'raj rajaratnam', 'rajshri', 'raja bell', 'rajah', 'raj kundra wikipedia', 'raj patel']
            suggestions = [s for s in suggestions if s]             # ['rajaan bennett', 'rajon rondo', 'rajiv shah', 'raj kundra', 'raj rajaratnam', 'rajshri', 'raja bell', 'rajah', 'raj kundra wikipedia', 'raj patel']

            suggestions = [{'url': '/search?query=' + s.replace(' ', '+'),
                            'text': s,
                            'has_results': bool(self._num_relevant_results(s)),}
                           for s in suggestions]
        html = template.render(path, locals(), debug=DEBUG)
        return html


class Search(_BaseRequestHandler):
    """Request handler to serve search results pages."""

    @decorators.no_browser_cache
    def get(self):
        """Given a search query, show related bookmarks, sorted by relevance.

        We don't actually "paginate" search results.  (What right-thinking,
        red-blooded American would issue a search query and then immediately
        click on result page 7?)  Instead, every time the user clicks the "more
        results" button, we use AJAX to serve up an HTML snippet to dynamically
        grow the results page.
        
        In order to implement this scheme, every requested URL that *doesn't*
        specify a page number query parameter gets a full HTML page response;
        every URL that *does* gets only an HTML snippet.
        """
        try:
            target_user, target_users, target_words, page = self._parse_query()
        except ValueError:
            # The "page" query parameter's value isn't an integer.
            # Congratulations, enjoy your 404.
            return self._serve_error(404)
        snippet = page != 0
        file_name = 'index.html' if not snippet else 'bookmarks.html'
        path, debug = os.path.join(TEMPLATES, 'bookmarks', file_name), DEBUG
        login_url, current_user, current_account, logout_url = self._get_user()
        if not target_words and not target_user:
            # This is an Easter egg, but an intentional and a useful one.  If
            # we got a blank search query, then show all of the bookmarks
            # sorted reverse chronologically.
            title = 'all bookmarks'
            num_bookmarks, bookmarks, more = self._get_bookmarks(page=page)
        else:
            title = 'bookmarks'
            if target_user:
                title += ' saved by ' + target_user.nickname()
            if target_words:
                if target_user:
                    title += ','
                title += ' related to ' + ' '.join(target_words)
            kwds = {'query_users': target_users, 'query_words': target_words,
                    'page': page}
            num_bookmarks, bookmarks, more = self._search_bookmarks(**kwds)
        try:
            more_url = self._compute_more_url() if more else None
        except ValueError:
            # The "page" query parameter's value isn't an integer.
            # Congratulations, enjoy your 404.
            return self._serve_error(404)
        self.response.out.write(template.render(path, locals(), debug=DEBUG))

    def _parse_query(self):
        """From the URL query parameter, parse the features to search on."""
        query_user = self.request.get('user')
        query_user = users.User(email=query_user) if query_user else query_user
        query_users = [query_user] if query_user else []
        query_words = self.request.get('query')
        query_words = query_words.replace('+', ' ')
        query_words = query_words.replace('%20', ' ')
        query_words = auto_tag.extract_words_from_string(query_words)
        page = self.request.get('page', default_value='0')
        # This next line might throw a ValueError exception, but the caller
        # catches it and serves a 404.
        page = int(page)
        return query_user, query_users, query_words, page

    def _compute_more_url(self):
        """Compute the URL for the next search results page."""
        path, query = self.request.path, self.request.query
        query, index, success = cgi.parse_qsl(query), 0, False
        for index in range(len(query)):
            if query[index][0] == 'page':
                # This next line might throw a ValueError exception, but the
                # caller catches it and serves a 404.
                page = str(int(query[index][1]) + 1)
                query[index], success = ('page', page), True
                break
        if not success:
            query.append(('page', '1'))
        query = urllib.urlencode(query)
        more_url = path + '?' + query
        return more_url


class API(_BaseRequestHandler):
    """Request handler to expose imi-imi's functionality through an API.
    
    imi-imi exposes ReSTful API calls which return JSON data.  This is similar
    to Twitter's API, and following Twitter's API design decisions is probably
    a safe bet.  ;-)
    """

    @decorators.no_browser_cache
    def get(self):
        """Someone has made an API GET request.  Service it."""
        method = self.request.get('method')
        self.response.headers['Content-Type'] = 'application/json'
        if method == 'normalize-url':
            obj = self._normalize_url()
        elif method == 'auto-tag':
            obj = self._auto_tag()
        else:
            obj = self._serve_error(404, 'Unrecognized method "%s".' % method)
        self.response.out.write(simplejson.dumps(obj))

    def _normalize_url(self):
        """Normalize the specified URL."""
        url = self.request.get('url')
        if not url:
            return self._serve_error(406, '"url" parameter not specified.')
        return fetch.normalize_url(url)

    def _auto_tag(self):
        """Auto-tag the specified URL or HTML / text snippet."""
        url = self.request.get('url')
        html = self.request.get('html')
        if not url and not html:
            error_message = 'Neither "url" nor "html" parameter specified.'
            return self._serve_error(406, error_message)
        if url and html:
            error_message = 'Both "url" and "html" parameters specified.'
            return self._serve_error(406, error_message)
        if url:
            url, mime_type, title, words, html_hash = auto_tag.tokenize_url(url)
        elif html:
            title, words, hash = auto_tag.tokenize_html(html)
        stop_words, stop_words_hash = auto_tag.read_stop_words()
        tags = auto_tag.auto_tag(words, stop_words)
        return tags

    def _serve_error(self, error_code, error_message):
        """Houston, we have a problem...  Serve an error page."""
        if not error_code in HTTP_CODE_TO_TITLE:
            error_code = 500
        error_message = HTTP_CODE_TO_TITLE[error_code] + ': ' + error_message
        self.error(error_code)
        return error_message
