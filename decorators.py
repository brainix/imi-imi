#------------------------------------------------------------------------------#
#   decorators.py                                                              #
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
"""Decorators to alter the behavior of request handler methods."""


import functools
import logging

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db

from config import DEFAULT_CACHE_SECS
import models


_log = logging.getLogger(__name__)


def require_login(method):
    """Require that the user be logged in to access the request handler method.
    
    Google App Engine provides similar functionality:
        from google.appengine.ext.webapp.util import login_required

    But Google's decorator only seems to work for GET request handler methods.
    """
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        if users.get_current_user() is None:
            # The user isn't logged in.
            method_name = method.func_name
            if method_name == 'get':
                # The anonymous user issued a GET request.  Redirect to a login
                # page that redirects back to the current URL (corresponding to
                # the decorated method).
                self.redirect(users.create_login_url(self.request.url))
            else:
                # The anonymous user issued a PUT request.  Log it and ignore
                # the request.
                message = 'anonymous user issued %s request on URL %s; ignoring'
                _log.info(message % (method_name.upper(), self.request.url))
        else:
            # The user is logged in.  Fall through to the decorated method.
            return method(self, *args, **kwds)
    return wrap


def create_account(method):
    """If the user is logged in but doesn't have an account, create an account.

    This is a little confusing, because we use Google accounts for login, but
    we also manage our own user accounts.
    """
    @functools.wraps(method)
    def wrap(*args, **kwds):
        user = users.get_current_user()
        if user is not None:
            email = user.email()
            key_name = models.Account.key_name(email)
            account = models.Account.get_or_insert(key_name=key_name)
            account.put()
            _log.debug('created or updated user account %s' % email)
        return method(*args, **kwds)
    return wrap


def memcache_results(cache_secs=DEFAULT_CACHE_SECS):
    """Decorate a method with the memcache pattern.

    Technically, the memcache_results function isn't a decorator.  It's a
    function that returns a decorator.  We have to jump through these hoops
    because we want to pass an argument to the decorator - how long to cache
    the results.  But a decorator can only accept one argument - the method to
    be decorated.  So instead, we use a closure.  (This is a closure, right?)

    memcache_results is convenient to use on an expensive method that doesn't
    always need to return live results.  Conceptually, we check the memcache
    for the results of a method call.  If those results have already been
    computed and cached, then we simply return them.  Otherwise, we call the
    method to compute the results, cache the results (so that future calls will
    hit the cache), then return the results.
    """
    def wrap1(method):
        @functools.wraps(method)
        def wrap2(self, *args, **kwds):
            key = _compute_memcache_key(self, method, *args, **kwds)
            _log.debug('trying to retrieve cached results for %s' % key)
            results = memcache.get(key)
            if results is not None:
                _log.debug('retrieved cached results for %s' % key)
            else:
                _log.debug("couldn't retrieve cached results for %s" % key)
                _log.debug('caching results for %s' % key)
                results = method(self, *args, **kwds)
                try:
                    success = memcache.set(key, results, time=cache_secs)
                except MemoryError:
                    success = False
                if success:
                    _log.debug('cached results for %s' % key)
                else:
                    _log.error("couldn't cache results for %s" % key)
            return results
        return wrap2
    return wrap1


def _compute_memcache_key(self, method, *args, **kwds):
    """Convert a method call into a readable string suitable as a memcache key.

    Take into account the module, class, and method names, positional argument
    values, and keyword argument names and values in order to eliminate the
    possibility of a false positive memcache hit.
    """

    def stringify(arg):
        """ """
        quote = "'" if isinstance(arg, str) else ''
        s = quote + str(arg) + quote
        return s

    memcache_key = str(type(self)).split("'")[1] + '.' + method.func_name + '('
    memcache_key += ', '.join([stringify(arg) for arg in args])
    if args and kwds:
        memcache_key += ', '
    memcache_key += ', '.join([str(key) + '=' + stringify(kwds[key])
                               for key in kwds]) + ')'
    return memcache_key


def run_in_transaction(method):
    """Transactionally execute a method."""
    @functools.wraps(method)
    def wrap(*args, **kwds):
        method_name = method.func_name
        _log.debug('transactionally executing %s' % method_name)
        return_value = db.run_in_transaction(method, *args, **kwds)
        _log.debug('transactionally executed %s' % method_name)
        return return_value
    return wrap


def no_browser_cache(method):
    """Set the response headers to disallow browser-side caching."""
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        self.response.headers['Cache-Control'] = 'no-store'
        self.response.headers['Expires'] = '-1'
        self.response.headers['Pragma'] = 'no-cache'
        return method(self, *args, **kwds)
    return wrap
