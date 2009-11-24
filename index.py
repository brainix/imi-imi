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

    def _process_url(self, url):
        """Normalize a URL, and compute its MIME type, title, and tags."""
        url, mime_type, title, words, html_hash = utils.tokenize_url(url)
        if not words:
            tags = []
        else:
            stop_words, stop_words_hash = utils.read_stop_words()
            tags = utils.auto_tag(words, stop_words)
        return url, mime_type, title, tags

    def _create_bookmark(self, url, public):
        """Create a bookmark corresponding to the specified URL."""
        return self._save_bookmark(url, public)

    def _update_bookmark(self, reference_id, public):
        """Update the bookmark corresponding to the specified reference key."""
        reference = models.Reference.get_by_id(reference_id)
        if reference:
            url = reference.bookmark.url
            return self._save_bookmark(url, public, reference=reference)

    def _save_bookmark(self, url, public, reference=None):
        """Save a bookmark and reference corresponding to the specified URL."""
        current_user = users.get_current_user()
        _log.info('%s saving reference %s' % (current_user.email(), url))
        url, mime_type, title, tags = self._process_url(url)
        bookmark = models.Bookmark.all().filter('url =', url).get()
        creating_bookmark = bookmark is None
        if reference is None:
            reference = models.Reference.all().filter('user =', current_user)
            reference = reference.filter('bookmark =', bookmark).get()
            if reference is not None:
                return
        verb = 'creating' if creating_bookmark else 'updating'
        _log.debug('%s %s bookmark %s' % (current_user.email(), verb, url))
        if creating_bookmark:
            bookmark = models.Bookmark()
        else:
            self._unindex_bookmark(bookmark)
        if not bookmark.public and public:
            bookmark.user = current_user
            bookmark.created = bookmark.updated = datetime.datetime.now()
            bookmark.public = True
        bookmark.url, bookmark.mime_type, bookmark.title = url, mime_type, title
        bookmark.stems, bookmark.words, bookmark.counts = [], [], []
        for tag in tags:
            bookmark.stems.append(tag['stem'])
            bookmark.words.append(tag['word'])
            bookmark.counts.append(tag['count'])
        if not creating_bookmark:
            bookmark.popularity += 1
        bookmark.put()
        verb = 'created' if creating_bookmark else 'updated'
        _log.debug('%s %s bookmark %s' % (current_user.email(), verb, url))
        if reference is None:
            reference = models.Reference()
        reference.public, reference.bookmark = public, bookmark
        reference.put()
        self._index_bookmark(bookmark)
        _log.info('%s saved reference %s' % (current_user.email(), url))
        return reference

    def _delete_bookmark(self, reference_id):
        """Delete the bookmark corresponding to the specified URL."""
        email = users.get_current_user().email()
        _log.info('%s deleting reference %s' % (email, reference_id))
        reference = models.Reference.get_by_id(reference_id)
        if reference is None:
            _log.warning("%s couldn't delete reference %s (doesn't exist)" %
                         (email, reference_id))
        else:
            bookmark = reference.bookmark
            db.delete(reference)
            if bookmark is None:
                _log.critical("%s couldn't resolve reference %s to bookmark" %
                              (email, reference_id))
            else:
                url = bookmark.url
                _log.debug('%s resolved reference %s to bookmark %s' %
                           (email, reference_id, url))
                bookmark.popularity -= 1
                if bookmark.popularity:
                    bookmark.put()
                    msg = '%s not deleting bookmark %s (still other references)'
                    msg = msg % (email, url)
                    _log.debug(msg)
                else:
                    self._unindex_bookmark(bookmark)
                    db.delete(bookmark)
                    _log.debug('%s deleted bookmark %s (no other references)' %
                               (email, url))
                _log.info('%s deleted reference %s' % (email, reference_id))

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
                (to_put if keychain.keys else to_delete).append(keychain)
        _log.debug('%s unindexed bookmark %s' % (email, url))
        return to_put, to_delete, None
