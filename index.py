#------------------------------------------------------------------------------#
#   index.py                                                                   #
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

"""Bookmark saving and indexing logic."""


import datetime
import logging

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp

import decorators
import models
import utils


_log = logging.getLogger(__name__)


class RequestHandler(webapp.RequestHandler):
    """Base request handler, from which other request handlers inherit."""

    def _create_bookmark(self, url):
        """Create a reference for the current user and the specified URL."""
        email = users.get_current_user().email()
        url, mime_type, title, words, html_hash = utils.tokenize_url(url)
        _log.info('%s creating reference %s' % (email, url))
        reference_key = models.Reference.key_name(email, url)
        reference = models.Reference.get_by_key_name(reference_key)
        if reference is not None:
            _log.warning("%s couldn't create reference %s (already exists)" %
                         (email, url))
        else:
            bookmark_key = models.Bookmark.key_name(url)
            bookmark = models.Bookmark.get_or_insert(bookmark_key)
            reference = models.Reference(parent=bookmark,
                                         key_name=reference_key)
            reference.bookmark = bookmark
            reference = self._common(url, mime_type, title, words, html_hash,
                                     reference, True)
            _log.info('%s created reference %s' % (email, url))
        return reference

    def _update_bookmark(self, reference):
        """Update the reference corresponding to the specified reference key."""
        email = users.get_current_user().email()
        url = reference.bookmark.url
        _log.info('%s updating reference %s' % (email, url))
        url, mime_type, title, words, html_hash = utils.tokenize_url(url)
        reference = self._common(url, mime_type, title, words, html_hash,
                                 reference, False)
        _log.info('%s updated reference %s' % (email, url))
        return reference

    def _delete_bookmark(self, reference):
        """Delete the reference corresponding to the specified reference key."""
        email = users.get_current_user().email()
        url = reference.bookmark.url
        _log.info('%s deleting reference %s' % (email, url))
        unindex = self._unsave_bookmark(reference)
        if unindex:
            self._unindex_bookmark(reference.bookmark)
        _log.info('%s deleted reference %s' % (email, url))

    def _common(self, url, mime_type, title, words, html_hash, reference,
                increment_popularity):
        """Perform the operations common to creating / updating references."""
        reindex = reference.bookmark.html_hash != html_hash
        if reindex:
            _log.debug('re-tagging and re-indexing bookmark %s '
                       '(HTML has changed since last)' % url)
            self._unindex_bookmark(reference.bookmark)
            stop_words, stop_words_hash = utils.read_stop_words()
            tags = utils.auto_tag(words, stop_words)
        else:
            _log.debug("not re-tagging and re-indexing bookmark %s "
                       "(HTML hasn't changed since last)" % url)
            tags = []
        reference = self._save_bookmark(url, mime_type, title, tags, html_hash,
                                        reference, increment_popularity)
        if reindex:
            self._index_bookmark(reference.bookmark)
            _log.debug('re-tagged and re-indexed bookmark %s' % url)
        return reference

    def _save_bookmark(self, url, mime_type, title, tags, html_hash, reference,
                       increment_popularity):
        """Save the reference for the current user and the specified URL."""
        current_user, bookmark = users.get_current_user(), reference.bookmark
        verb = 'creating' if not bookmark.is_saved() else 'updating'
        _log.info('%s %s bookmark %s' % (current_user.email(), verb, url))
        if increment_popularity:
            bookmark.popularity += 1
        if bookmark.html_hash != html_hash:
            bookmark.url, bookmark.mime_type = url, mime_type
            bookmark.title = title
            bookmark.stems, bookmark.words, bookmark.counts = [], [], []
            for tag in tags:
                bookmark.stems.append(tag['stem'])
                bookmark.words.append(tag['word'])
                bookmark.counts.append(tag['count'])
            bookmark.html_hash = html_hash

        # Subtle:  We want to update references and bookmarks transactionally,
        # so ordinarily, we'd wrap this method in our run_in_transaction
        # decorator.  However, in this case, we know that we're saving exactly
        # two objects - a bookmark and a reference - and we know that the
        # bookmark object is the parent of the reference object.  Therefore, we
        # know that both objects belong in the same entity group.  And whenever
        # we batch save multiple objects in the same entity group, Google App
        # Engine treats the batch save as a single transaction.
        #
        # For more information, see:
        #   http://code.google.com/appengine/docs/python/datastore/functions.html#put
        db.put([bookmark, reference])
        verb = 'created' if verb == 'creating' else 'updated'
        _log.info('%s %s bookmark %s' % (current_user.email(), verb, url))
        return reference

    @decorators.run_in_transaction
    @decorators.batch_put_and_delete
    def _unsave_bookmark(self, reference):
        """Delete the reference for the current user and the specified URL."""
        bookmark, to_put, to_delete = reference.bookmark, [], []
        to_delete.append(reference)
        if bookmark is not None:
            bookmark.popularity -= 1
            (to_put if bookmark.popularity else to_delete).append(bookmark)
        return to_put, to_delete, not bookmark.popularity

    @decorators.batch_put_and_delete
    def _index_bookmark(self, bookmark):
        """Index a bookmark so that it appears in search results.

        For each stem in the bookmark, make sure a corresponding keychain
        exists.  If it doesn't exist, create it.  Then add the bookmark's key to
        that keychain.
        """
        email, url = users.get_current_user().email(), bookmark.url
        _log.debug('%s indexing bookmark %s' % (email, url))
        bookmark_key, to_put = bookmark.key(), []
        for stem, word in zip(bookmark.stems, bookmark.words):
            keychain_key = models.Keychain.key_name(stem)
            keychain = models.Keychain.get_or_insert(keychain_key)
            keychain.stem, keychain.word = stem, word
            if not bookmark_key in keychain.keys:
                keychain.keys.append(bookmark_key)
            keychain.popularity = len(keychain.keys)
            to_put.append(keychain)
        _log.debug('%s indexed bookmark %s' % (email, url))
        return to_put, [], None

    @decorators.batch_put_and_delete
    def _unindex_bookmark(self, bookmark):
        """Unindex a bookmark so that it no longer appears in search results.

        For each stem in the bookmark, remove the bookmark's key from the
        keychain corresponding to the stem.  Then if the keychain no longer
        contains any keys at all, delete the keychain itself.
        """
        email, url = users.get_current_user().email(), bookmark.url
        _log.debug('%s unindexing bookmark %s' % (email, url))
        bookmark_key, to_put, to_delete = bookmark.key(), [], []
        for stem in bookmark.stems:
            keychain_key = models.Keychain.key_name(stem)
            keychain = models.Keychain.get_by_key_name(keychain_key)
            if keychain is not None:
                try:
                    keychain.keys.remove(bookmark_key)
                except ValueError:
                    msg = "bookmark %s has stem %s, "
                    msg += "but keychain %s doesn't have bookmark %s"
                    msg = msg % (bookmark_key, stem, keychain_key, bookmark_key)
                    _log.critical(msg)
                keychain.popularity = len(keychain.keys)
                (to_put if keychain.keys else to_delete).append(keychain)
        _log.debug('%s unindexed bookmark %s' % (email, url))
        return to_put, to_delete, None
