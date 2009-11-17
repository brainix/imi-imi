#------------------------------------------------------------------------------#
#   decorators.py                                                              #
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

"""Decorators to alter the behavior of request handler methods."""


import functools
import logging

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db

from config import DEFAULT_CACHE_SECS


_log = logging.getLogger(__name__)


def require_login(method):
    """Require that the user be logged in to access the request handler method.
    
    Google App Engine provides similar functionality:

        from google.appengine.ext.webapp.util import login_required

    But Google's decorator only seems to work for GET request handler methods.
    """
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        if not users.get_current_user():
            # The user isn't logged in.  Redirect to a login page that redirects
            # back to the current URL (corresponding to the decorated method).
            self.redirect(users.create_login_url(self.request.uri))
        else:
            # The user is logged in.  Fall through to the decorated method.
            return method(self, *args, **kwds)
    return wrap


def memcache_results(method):
    """Decorate a method with the memcache pattern.

    This is a convenient decorator to use on an expensive method that doesn't
    always need to return live results.  Conceptually, we check the memcache
    for the results of a method call.  If those results have already been
    computed and cached, we simply return them.  Otherwise, we call the method
    to compute the results, cache the results (so that future calls will hit
    the cache), then return the results.

    We take into account the module, class, and method names, positional
    argument values, and keyword argument names and values when computing the
    memcache key for the method call.  This eliminates the possibility of a
    false positive memcache hit.
    """
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
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
                success = memcache.set(key, results, time=DEFAULT_CACHE_SECS)
            except MemoryError:
                success = False
            if success:
                _log.debug('cached results for %s' % key)
            else:
                _log.error("couldn't cache results for %s" % key)
        return results
    return wrap


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
    """Transactionally execute a method.

    If we can't execute the method transactionally, just run it
    non-transactionally.
    """
    @functools.wraps(method)
    def wrap(*args, **kwds):
        method_name = method.func_name
        _log.debug('transactionally executing %s' % method_name)
        try:
            return_value = db.run_in_transaction(method, *args, **kwds)
        except (db.BadRequestError, db.TransactionFailedError,):
            # Oops.  We couldn't execute the method transactionally.  Just run
            # it non-transactionally.
            _log.warning('could not transactionally execute %s' % method_name)
            return_value = method(*args, **kwds)
        else:
            _log.debug('transactionally executed %s' % method_name)
        return return_value
    return wrap


def batch_put_and_delete(method):
    """Batch put / delete all of the entities modified in the specified method.

    Rather than getting / putting / deleting a bunch of entities one at a time,
    if possible, it's more efficient to perform these datastore operations on
    the entities as a batch.  In order to accomplish this task, this decorator
    requires the decorated method to return a tuple like so:

        (entities_to_put, entities_to_delete, return_value)

    This decorator puts and deletes the specified entities as batches, then
    returns only the aforementioned return value.
    """
    @functools.wraps(method)
    def wrap(*args, **kwds):
        method_name = method.func_name
        _log.debug('batch putting and deleting results of %s' % method_name)
        to_put, to_delete, return_value = method(*args, **kwds)
        db.put(to_put)
        db.delete(to_delete)
        _log.debug('batch put and deleted results of %s' % method_name)
        return return_value
    return wrap


def no_browser_cache(method):
    """Set the response headers to disallow browser-side caching."""
    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        self.response.headers['Cache-Control'] = 'no-store'
        self.response.headers['Pragma'] = 'no-cache'
        return method(self, *args, **kwds)
    return wrap
