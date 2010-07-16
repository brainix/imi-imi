#------------------------------------------------------------------------------#
#   index.py                                                                   #
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
"""Bookmark saving and indexing logic."""


import logging

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp

import auto_tag
import decorators
import fetch
import models


_log = logging.getLogger(__name__)


class RequestHandler(webapp.RequestHandler):
    """Index request handler, from which other request handlers inherit."""

    def _create_bookmark(self, url):
        """Create a reference for the current user and the specified URL."""
        email, args, bookmark, reference, exists = self._get_bookmark(url)
        _log.info('%s creating reference %s' % (email, args[0]))
        if exists['reference']:
            reference = None
            message = "%s couldn't create reference %s (already exists)"
            _log.warning(message % (email, args[0]))
        else:
            reference.bookmark = bookmark
            if exists['bookmark']:
                reference = self._save_bookmark(reference)
            else:
                args = list(args) + [reference]
                reference = self._common(*args)
            _log.info('%s created reference %s' % (email, args[0]))
        return reference

    def _update_bookmark(self, reference):
        """Update the reference corresponding to the specified reference key."""
        email, url = users.get_current_user().email(), reference.bookmark.url
        _log.info('%s updating reference %s' % (email, url))
        url, mime_type, title, words, html_hash = auto_tag.tokenize_url(url)
        reference = self._common(url, mime_type, title, words, html_hash,
                                 reference)
        _log.info('%s updated reference %s' % (email, url))
        return reference

    def _delete_bookmark(self, reference):
        """Delete the reference corresponding to the specified reference key."""
        email, url = users.get_current_user().email(), reference.bookmark.url
        _log.info('%s deleting reference %s' % (email, url))
        unindex = self._unsave_bookmark(reference)
        if unindex:
            self._unindex_bookmark(reference.bookmark)
        _log.info('%s deleted reference %s' % (email, url))

    def _get_bookmark(self, url):
        """Get/create the bookmark/reference for the current user and URL."""
        email = users.get_current_user().email()
        url = fetch.Factory().normalize(url)
        exists = {'bookmark': True, 'reference': True,}
        _log.debug('%s getting/creating bookmark/reference %s' % (email, url))
        bookmark_key = models.Bookmark.key_name(url)
        bookmark = models.Bookmark.get_by_key_name(bookmark_key)
        if bookmark is None:
            args = auto_tag.tokenize_url(url)
            bookmark_key = models.Bookmark.key_name(args[0])
            bookmark = models.Bookmark.get_by_key_name(bookmark_key)
            if bookmark is None:
                bookmark = models.Bookmark(key_name=bookmark_key)
                exists['bookmark'] = False
        else:
            args = [bookmark.url, bookmark.mime_type, bookmark.title,
                bookmark.words, bookmark.html_hash,]
        reference_key = models.Reference.key_name(email, args[0])
        reference = models.Reference.get_by_key_name(reference_key,
                                                     parent=bookmark)
        if reference is None:
            reference = models.Reference(parent=bookmark,
                                         key_name=reference_key)
            exists['reference'] = False
        _log.debug('%s got/created bookmark/reference %s' % (email, args[0]))
        return email, args, bookmark, reference, exists

    def _common(self, url, mime_type, title, words, html_hash, reference):
        """Perform the operations common to creating / updating references."""
        reindex = reference.bookmark.html_hash != html_hash
        if reindex:
            _log.debug('re-tagging and re-indexing bookmark %s '
                       '(HTML has changed since last)' % url)
            self._unindex_bookmark(reference.bookmark)
            stop_words, stop_words_hash = auto_tag.read_stop_words()
            tags = auto_tag.auto_tag(words, stop_words)
        else:
            _log.debug("not re-tagging and re-indexing bookmark %s "
                       "(HTML hasn't changed since last)" % url)
            tags = []
        reference = self._populate_bookmark(url, mime_type, title, tags,
                                            html_hash, reference)
        if reindex:
            self._index_bookmark(reference.bookmark)
            _log.debug('re-tagged and re-indexed bookmark %s' % url)
        return reference

    def _populate_bookmark(self, url, mime_type, title, tags, html_hash,
                           reference):
        """Update all of a referenced bookmark's attributes."""
        current_user, bookmark = users.get_current_user(), reference.bookmark
        _log.debug('%s populating bookmark %s' % (current_user.email(), url))
        if bookmark.html_hash != html_hash:
            bookmark.url, bookmark.mime_type = url, mime_type
            bookmark.title = title
            bookmark.stems, bookmark.words, bookmark.counts = [], [], []
            for tag in tags:
                bookmark.stems.append(tag['stem'])
                bookmark.words.append(tag['word'])
                bookmark.counts.append(tag['count'])
            bookmark.html_hash = html_hash
        reference = self._save_bookmark(reference)
        _log.debug('%s populated bookmark %s' % (current_user.email(), url))
        return reference

    @decorators.run_in_transaction
    def _save_bookmark(self, reference):
        """Update only a referenced bookmark's user list and popularity."""
        current_user, bookmark = users.get_current_user(), reference.bookmark
        url, to_put = bookmark.url, [bookmark, reference]
        _log.debug('%s saving bookmark %s' % (current_user.email(), url))
        if current_user not in bookmark.users:
            bookmark.users.append(current_user)
        bookmark.popularity = len(bookmark.users)
        _log.debug('%s saved bookmark %s' % (current_user.email(), url))
        db.put(to_put)
        return reference

    @decorators.run_in_transaction
    def _unsave_bookmark(self, reference):
        """Delete the reference for the current user and the specified URL."""
        current_user, bookmark = users.get_current_user(), reference.bookmark
        to_put, to_delete = [], [reference]
        if bookmark is not None:
            while current_user in bookmark.users:
                bookmark.users.remove(current_user)
            bookmark.popularity = len(bookmark.users)
            (to_put if bookmark.popularity else to_delete).append(bookmark)
        db.put(to_put)
        db.delete(to_delete)
        return not bookmark.popularity

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
        db.put(to_put)

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
        db.put(to_put)
        db.delete(to_delete)
