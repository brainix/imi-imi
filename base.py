#------------------------------------------------------------------------------#
#   base.py                                                                    #
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


import datetime
import logging
import os
import traceback
import urllib

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

from config import DATETIME_FORMAT, DEBUG, HTTP_CODE_TO_TITLE, TEMPLATES
import emails
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
            # in read-only mode for maintenance.  Gracefully degrade - throw a
            # 503 error.  For more info, see:
            # http://code.google.com/appengine/docs/python/howto/maintenance.html
            error_code = 503
        else:
            error_code = 500

        # Serve the error page.
        self._serve_error(error_code)

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
        target_email = urllib.unquote(target_email)
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


class RequestHandler(_CommonRequestHandler):
    """Abstract base class request handler."""

    def get(*args, **kwds):
        """Abstract method to handle requests."""
        raise NotImplementedError

    trace = delete = options = head = put = post = get
