#------------------------------------------------------------------------------#
#   search.py                                                                  #
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
"""Bookmark search logic."""


import logging

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp

from config import SEARCH_CACHE_SECS, SEARCH_PER_PAGE
import auto_tag
import decorators
import errors
import models


_log = logging.getLogger(__name__)


class RequestHandler(webapp.RequestHandler):
    """Base request handler, from which other request handlers inherit."""

    @decorators.memcache_results(cache_secs=SEARCH_CACHE_SECS)
    def _num_relevant_results(self, query_string):
        """Return the number of bookmarks that are relevant to the query string.

        We can call this method up to 10 times for every letter that anyone
        types into the query search bar (for the live search results), so
        please keep this method as efficient as possible.
        """
        query_words = query_string.split()
        query_stems = self._query_words_to_stems(query_words)
        bookmarks = None if query_stems else set()
        for s in query_stems:
            k = set(self._query_stems_to_bookmark_keys([s]))
            b = set([b.url for b in db.get(k) if b is not None])
            bookmarks = b if bookmarks is None else bookmarks & b
            if not bookmarks:
                break
        return len(bookmarks)

    def _get_bookmarks(self, references=False, query_users=tuple(), before=None,
                       page=0, per_page=SEARCH_PER_PAGE):
        """Return a list of bookmarks or references that match the criteria."""
        entity_type = 'references' if references else 'bookmarks'
        _log.debug('computing %s for user(s): %s' % (entity_type,
                                                     str(query_users)))
        entities = (models.Reference if references else models.Bookmark).all()
        if query_users:
            entities.filter('user IN', query_users)
        if before is not None:
            entities = entities.filter('updated <', before)
        entities.order('-updated')
        entities = entities.fetch(per_page+1, offset=page*per_page)
        more = len(entities) == per_page + 1
        if more:
            entities = entities[:per_page]
        _log.debug('computed %s for user(s): %s' % (entity_type,
                                                    str(query_users)))
        return entities, more

    def _search_bookmarks(self, *args, **kwds):
        """Return a list of bookmarks that match some given criteria."""
        kwds['before'] = kwds.get('before')
        kwds['page'] = kwds.get('page', 0)
        kwds['per_page'] = kwds.get('per_page', SEARCH_PER_PAGE)
        try:
            bookmarks = self._search_bookmarks_generic(**kwds)
        except (errors.SearchError,), e:
            if e.error_message in ('no query', 'generic query'):
                del kwds['query_words']
                bookmarks, more = self._get_bookmarks(**kwds)
            else:
                raise e
        else:
            bookmarks, more = self._search_bookmarks_specific(bookmarks, **kwds)
        return bookmarks, more

    @decorators.memcache_results(cache_secs=SEARCH_CACHE_SECS)
    def _search_bookmarks_generic(self, query_users=tuple(),
                                  query_words=tuple(), before=None, page=0,
                                  per_page=SEARCH_PER_PAGE):
        """Return a list of bookmarks that match some given criteria.
        
        The sort order is implicit in the criteria.  If search terms are
        specified, then the bookmarks should be sorted by relevance.
        Otherwise, they should be sorted in reverse chronological order.

        If there's some problem with the search criteria, then raise a
        SearchError exception.
        """
        query_key = self._compute_cache_key('_search_bookmarks_generic',
                                            query_users, query_words)
        _log.debug("computing bookmarks for query '%s'" % query_key)
        if not query_users and not query_words:
            _log.warning("couldn't compute bookmarks - no query")
            raise errors.SearchError(error_message='no query')
        if query_words:
            query_stems = self._query_words_to_stems(query_words)
            if not query_stems:
                _log.warning("couldn't compute bookmarks - generic query")
                raise errors.SearchError(error_message='generic query')
            bookmark_keys = self._query_stems_to_bookmark_keys(query_stems)
            bookmarks = db.get(bookmark_keys)
        else:
            bookmarks = models.Bookmark.all()
            bookmarks = bookmarks.order('-updated')
        bookmarks = self._query_to_list(bookmarks)
        if query_users:
            bookmarks = self._filter_query_users(query_users, bookmarks)
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
        situation - only return the bookmarks that should appear on the
        requested results page, etc.

        This method's results can't be cached, so please keep this method
        efficient.
        """
        query_key = self._compute_cache_key('_search_bookmarks_specific',
                                            query_users, query_words)
        _log.debug("computing bookmarks for query '%s'" % query_key)
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

    def _query_words_to_stems(self, query_words):
        """Convert words into stems, throwing away dupes and common words."""
        stop_words, stop_words_hash = auto_tag.read_stop_words()
        query_words = [w for w in query_words if not w in stop_words]
        query_words = list(set(query_words))
        query_stems = [auto_tag.stemmer.stem(w) for w in query_words]
        query_stems = list(set(query_stems))
        return query_stems

    def _query_stems_to_bookmark_keys(self, query_stems):
        """Convert a list of stems into a list of relevant bookmark keys."""
        bookmark_keys = []
        for stem in query_stems:
            keychain_key_name = models.Keychain.key_name(stem)
            keychain = models.Keychain.get_by_key_name(keychain_key_name)
            if keychain is not None:
                bookmark_keys.extend(keychain.keys)
        bookmark_keys = list(set(bookmark_keys))
        return bookmark_keys

    def _compute_cache_key(self, prefix, query_users, query_words):
        """Compute a string for a computation for use as a cache key."""
        cache_key = prefix
        if query_users:
            cache_key += ' users: ' + ' '.join([u.email() for u in query_users])
        if query_words:
            cache_key += ' words: ' + ' '.join(query_words)
        return cache_key

    def _query_to_list(self, query):
        """Convert a query object into a list of entity objects."""
        _log.debug('reading entities from query into list')
        l = []
        try:
            for entity in query:
                if entity is not None:
                    l.append(entity)
        except (MemoryError, db.Timeout,):
            _log.warning('reading entities from query into list timed out :-(')
        else:
            _log.debug('read entities from query into list')
        return l

    def _filter_query_users(self, query_users, bookmarks):
        """Sift out only the bookmarks saved by the specified users."""
        references = models.Reference.all().filter('user IN', query_users)
        references = self._query_to_list(references)
        urls = set([r.bookmark.url for r in references])
        bookmarks = [b for b in bookmarks if b.url in urls]
        return bookmarks

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

        # Pick the bookmark relevant to more of the given stems.
        x_val = len(set(stems) & set(x.stems))
        y_val = len(set(stems) & set(y.stems))
        if x_val == y_val:
            # Both bookmarks are relevant to the same number of the given stems,
            # so pick the one more relevant to the given stems.
            x_val = sum(map(lambda stem: get_count(stem, x), stems))
            y_val = sum(map(lambda stem: get_count(stem, y), stems))
            if x_val == y_val:
                # Both bookmarks are equally relevant to the given stems, so
                # pick the more popular one.
                x_val, y_val = x.popularity, y.popularity
                if x_val == y_val:
                    # Both bookmarks are equally popular, so pick the one
                    # updated more recently.
                    x_val, y_val = x.updated, y.updated
        return 1 if x_val <= y_val else -1

    def _filter_before(self, bookmarks, before):
        """Return only the bookmarks updated before the specified date/time."""
        bookmarks = [b for b in bookmarks if b.updated < before]
        return bookmarks
