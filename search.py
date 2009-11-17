#------------------------------------------------------------------------------#
#   search.py                                                                  #
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

"""Bookmark search logic."""


import functools
import logging

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp

from config import SEARCH_CACHE_SECS, SEARCH_PER_PAGE
import decorators
import errors
import models
import utils


_log = logging.getLogger(__name__)


def _cache_search(method):
    """Decorate a search method - cache its results."""

    @functools.wraps(method)
    def wrap(self, *args, **kwds):
        method_name = method.func_name
        query_users = kwds.get('query_users', [])
        query_words = kwds.get('query_words', [])
        key = self._compute_key(method_name, query_users, query_words)
        user_query = method_name == '_search_bookmarks_generic' and query_users
        blow_away = user_query and not kwds.get('before')

        # Check if we've already computed and cached results for this query.
        _log.debug("trying to retrieve cached results for query '%s'" % key)
        results = memcache.get(key) if not blow_away else None
        if results is not None:
            # Yes we have - use the previously computed and cached results.
            _log.debug("retrieved cached results for query '%s'" % key)
        else:
            # No we haven't - compute and cache the results for this query.
            _log.debug("couldn't retrieve cached results for query '%s'" % key)
            _log.debug("caching results for query '%s'" % key)
            results = method(self, *args, **kwds)

            # XXX: Combine the two most robust technologies invented by man,
            # Google App Engine and memcache, and you end up with random 500s,
            # most of the time without tracebacks.  Yay!  :-(
            cache_secs = 0 if user_query else SEARCH_CACHE_SECS
            try:
                success = memcache.set(key, results, time=cache_secs)
            except MemoryError:
                success = False
            if success:
                _log.debug("cached results for query '%s'" % key)
            else:
                _log.error("couldn't cache results for query '%s'" % key)
        return results
    return wrap


class RequestHandler(webapp.RequestHandler):
    """Base request handler, from which other request handlers inherit."""

    @decorators.memcache_results
    def _num_relevant_results(self, query_string):
        """Return the number of bookmarks that are relevant to a query string.

        We can call this method up to 10 times for every letter that anyone
        types into the query search bar (for the live search results), so
        please keep this method as efficient as possible.
        """
        query_words = query_string.split()
        query_stems = self._query_words_to_stems(query_words)
        bookmark_keys = None if query_stems else set()
        for s in query_stems:
            k = set(self._query_stems_to_bookmark_keys([s]))
            bookmark_keys = k if bookmark_keys is None else bookmark_keys & k
            if not bookmark_keys:
                break
        return len(bookmark_keys)

    def _get_bookmarks(self, query_users=tuple(), before=None, page=0,
                       per_page=SEARCH_PER_PAGE):
        """Return a list of bookmarks that match some given criteria."""
        _log.debug('computing bookmarks for user(s): %s' % str(query_users))
        bookmarks = models.Bookmark.all()
        if query_users:
            bookmarks.filter('user IN', query_users)
        if len(query_users) != 1 or query_users[0] != users.get_current_user():
            bookmarks = bookmarks.filter('public =', True)
        if before is not None:
            bookmarks = bookmarks.filter('updated <', before)
        bookmarks = bookmarks.order('-updated')
        bookmarks = bookmarks.fetch(per_page+1, offset=page*per_page)
        more = len(bookmarks) == per_page + 1
        if more:
            bookmarks = bookmarks[:per_page]
        _log.debug('computed bookmarks for user(s): %s' % str(query_users))
        return bookmarks, more

    def _search_bookmarks(self, *args, **kwds):
        """Return a list of bookmarks that match some given criteria."""
        kwds['before'] = kwds.get('before')
        kwds['page'] = kwds.get('page', 0)
        kwds['per_page'] = kwds.get('per_page', SEARCH_PER_PAGE)
        try:
            bookmarks = self._search_bookmarks_generic(**kwds)
        except (errors.SearchError,), e:
            if e.msg in ('no query', 'generic query'):
                del kwds['query_words']
                bookmarks, more = self._get_bookmarks(**kwds)
            else:
                raise e
        else:
            bookmarks, more = self._search_bookmarks_specific(bookmarks, **kwds)
        return bookmarks, more

    @_cache_search
    def _search_bookmarks_generic(self, query_users=tuple(),
                                  query_words=tuple(), before=None, page=0,
                                  per_page=SEARCH_PER_PAGE):
        """Return a list of bookmarks that match some given criteria.
        
        The sort order is implicit in the criteria.  If search terms are
        specified, the bookmarks should be sorted by relevance.  Otherwise, they
        should be sorted in reverse chronological order.

        If there's some problem with the search criteria, raise a SearchError
        exception.
        """
        query_key = self._compute_key('_search_bookmarks_generic', query_users,
                                      query_words)
        _log.debug("computing bookmarks for query '%s'" % query_key)
        if not query_users and not query_words:
            _log.warning("couldn't compute bookmarks - no query")
            raise errors.SearchError(msg='no query')
        if query_words:
            query_stems = self._query_words_to_stems(query_words)
            if not query_stems:
                _log.warning("couldn't compute bookmarks - generic query")
                raise errors.SearchError(msg='generic query')
            bookmark_keys = self._query_stems_to_bookmark_keys(query_stems)
            bookmarks = db.get(bookmark_keys)
            if query_users:
                bookmarks = [b for b in bookmarks if b.user in query_users]
        else:
            bookmarks = models.Bookmark.all()
            if query_users:
                bookmarks.filter('user IN', query_users)
            bookmarks = bookmarks.order('-updated')
            bookmarks = self._bookmarks_to_list(bookmarks)
        if query_words:
            bookmarks.sort(cmp=lambda x, y: self._cmp(query_stems, x, y))
        _log.debug("computed bookmarks for query '%s'" % query_key)
        return bookmarks

    def _search_bookmarks_specific(self, bookmarks, query_users=tuple(),
                                   query_words=tuple(), before=None, page=0,
                                   per_page=SEARCH_PER_PAGE):
        """Return a list of bookmarks that match some given criteria.

        Up to this point, our resulting bookmarks could've been cached, perhaps
        by a different user and long ago, so we haven't made any assumptions
        about the current situation.  Now, take into account the current
        situation - only return the bookmarks the current user has permission to
        see, and only the bookmarks that should appear on the requested results
        page, etc.

        This method's results can't be cached, so please keep this method as
        efficient as reasonable.
        """
        query_key = self._compute_key('_search_bookmarks_specific', query_users,
                                      query_words)
        _log.debug("computing bookmarks for query '%s'" % query_key)
        bookmarks = self._apply_fig_leaf(bookmarks)
        if before is not None:
            bookmarks = self._filter_before(bookmarks, before)
        if per_page:
            this_page = page * per_page
            next_page = this_page + per_page
            more = len(bookmarks) > next_page
            bookmarks = bookmarks[this_page:next_page]
        else:
            more = False
        _log.debug("computed bookmarks for query '%s'" % query_key)
        return bookmarks, more

    def _compute_key(self, prefix, query_users, query_words):
        """Compute a string for a computation for use as a cache key."""
        key = prefix
        if query_users:
            key += ' users: ' + ' '.join([user.email() for user in query_users])
        if query_words:
            key += ' words: ' + ' '.join(query_words)
        return key

    def _query_words_to_stems(self, query_words):
        """ """
        stop_words, stop_words_hash = utils.read_stop_words()
        query_words = [w for w in query_words if not w in stop_words]
        query_words = list(set(query_words))
        query_stems = [utils.stemmer.stem(w) for w in query_words]
        query_stems = list(set(query_stems))
        return query_stems

    def _query_stems_to_bookmark_keys(self, query_stems):
        """ """
        bookmark_keys = []
        for stem in query_stems:
            keychain_key_name = models.Keychain.stem_to_key_name(stem)
            keychain = models.Keychain.get_by_key_name(keychain_key_name)
            if keychain is not None:
                bookmark_keys.extend(keychain.keys)
        bookmark_keys = list(set(bookmark_keys))
        return bookmark_keys

    def _bookmarks_to_list(self, bookmarks):
        """Convert a bookmark query object into a list of bookmark objects."""
        _log.debug('reading bookmarks from query into list')
        l = []
        try:
            for bookmark in bookmarks:
                l.append(bookmark)
        except (MemoryError, db.Timeout,):
            _log.warning('reading bookmarks from query into list timed out :-(')
        else:
            _log.debug('read bookmarks from query object into list')
        return l

    def _cmp(self, stems, x, y):
        """Determine which bookmark is more relevant to the given stems."""

        def get_count(stem, z):
            """Determine a bookmark's relevance to the given stem."""
            try:
                index = z.stems.index(stem)
            except ValueError:
                count = 0
            else:
                count = z.counts[index]
            return count

        x_val = len(set(stems) & set(x.stems))
        y_val = len(set(stems) & set(y.stems))
        if x_val == y_val:
            x_val = sum(map(lambda stem: get_count(stem, x), stems))
            y_val = sum(map(lambda stem: get_count(stem, y), stems))
            if x_val == y_val:
                # The bookmarks are equally relevant to the given stems, so pick
                # the one updated more recently.
                x_val, y_val = x.updated, y.updated
        return 1 if x_val <= y_val else -1

    def _apply_fig_leaf(self, bookmarks):
        """Return only the public or current user's bookmarks."""
        current_user = users.get_current_user()
        bookmarks = [b for b in bookmarks if b.public or b.user == current_user]
        return bookmarks

    def _filter_before(self, bookmarks, before):
        """Return only the bookmarks updated before the specified date/time."""
        bookmarks = [b for b in bookmarks if b.updated < before]
        return bookmarks
