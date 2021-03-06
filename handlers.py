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
import urllib

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from config import DEBUG, LIVE_SEARCH_URL, SEARCH_CACHE_SECS, TEMPLATES
import auto_tag
import base
import decorators
import fetch
import models


_log = logging.getLogger(__name__)


class Maintenance(base.RequestHandler):
    """Request handler to serve all requests when in maintenance mode."""

    def get(self, *args, **kwds):
        """The site is under maintenance.  Serve a polite "bugger off" page."""
        path, debug = os.path.join(TEMPLATES, 'home', 'maintenance.html'), DEBUG
        title, in_maintenance = 'in surgery', True
        login_url, current_user, current_account, logout_url = self._get_user()
        self.error(503)
        self.response.out.write(template.render(path, locals(), debug=DEBUG))

    def post(self, *args, **kwds):
        """ """
        self.error(503)

    trace = delete = options = head = put = post


class NotFound(base.RequestHandler):
    """Request handler to serve a 404: Not Found error page."""

    def get(self, *args, **kwds):
        """ """
        return self._serve_error(404)

    def post(self, *args, **kwds):
        """ """
        self.error(404)

    trace = delete = options = head = put = post


class Home(base.RequestHandler):
    """Request handler to serve the homepage."""

    @decorators.no_browser_cache
    @decorators.create_account
    def get(self):
        """Serve a get request for /, /about, or /rss.
        
        If an anonymous user requested /, then serve the homepage.  If a logged
        in user requested /, then redirect to that user's bookmarks page.  If
        either an anonymous user or a logged in user requested /about, then
        serve the homepage.

        If a user requested /rss, then serve the site-wide RSS feed.
        """
        if self.request.path not in ('/', '/about', '/rss'):
            return self._serve_error(404)

        login_url, current_user, current_account, logout_url = self._get_user()
        if self.request.path == '/' and current_user is not None:
            return self._user_bookmarks(target_email=current_user.email(),
                                        friends=True)
        elif self.request.path == '/rss':
            return self._serve_rss()

        path, debug = os.path.join(TEMPLATES, 'home', 'index.html'), DEBUG
        title = 'social bookmarking'
        rss_url = self._get_rss_url()
        active_tab = 'imi-imi' if current_user is None else ''
        self.response.out.write(template.render(path, locals(), debug=DEBUG))


class Users(base.RequestHandler):
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


class LiveSearch(base.RequestHandler):
    """Request handler to serve live search HTML snippets."""

    def get(self):
        """Someone is typing a search query.  Provide some live search results.

        This method gets called every time anyone types a single letter in the
        search box.  Keep this method as efficient as possible.
        """
        query = urllib.quote_plus(self.request.get('query')).lower()
        html = self._live_search(query)
        self.response.out.write(html)

    @decorators.memcache_results(cache_secs=SEARCH_CACHE_SECS)
    def _live_search(self, query):
        """Fetch & render HTML for the live search results for the given query.

        This method potentially gets called every time anyone types a single
        letter in the search box.  Keep this method as efficient as possible
        and aggressively cache its results.

        Google Suggest exposes a nice ReSTful API.  To fetch suggestions for
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


class Search(base.RequestHandler):
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
        query_words = urllib.unquote_plus(self.request.get('query'))
        query_words = auto_tag.extract_words_from_string(query_words)
        # This next line might throw a ValueError exception, but the caller
        # catches it and serves a 404.
        page = int(self.request.get('page', default_value='0'))
        return query_user, query_users, query_words, page

    def _compute_more_url(self):
        """Compute the URL for the next search results page."""
        path, query = self.request.path, cgi.parse_qsl(self.request.query)
        success = False
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
