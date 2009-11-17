#------------------------------------------------------------------------------#
#   index.py                                                                   #
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
        """Process a URL - compute its MIME type, title, and tags."""
        mime_type, title, words, html_hash = utils.tokenize_url(url=url)
        if not words:
            tags = []
        else:
            stop_words, stop_words_hash = utils.read_stop_words()
            tags = utils.auto_tag(words=words, stop_words=stop_words)
        return mime_type, title, tags

    def _create_bookmark(self, url):
        """Create a bookmark corresponding to the specified URL."""
        current_user = users.get_current_user()
        _log.info('%s creating bookmark %s' % (current_user.email(), url))
        dupe_bookmark = models.Bookmark.all().filter('user =', current_user)
        if dupe_bookmark.filter('url =', url).count() == 0:
            new_bookmark = self._save_bookmark(url, bookmark=None)
            _log.info('%s created bookmark %s' % (current_user.email(), url))
            return new_bookmark
        else:
            _log.warning("%s couldn't create bookmark %s (already exists?)" %
                         (current_user.email(), url))

    def _update_bookmark(self, key_id):
        """Update the bookmark corresponding to the specified URL."""
        current_user = users.get_current_user()
        _log.info('%s updating bookmark %s' % (current_user.email(), key_id))
        stale_bookmark = models.Bookmark.get_by_id(key_id)
        if stale_bookmark:
            url = stale_bookmark.url
            fresh_bookmark = self._save_bookmark(url, bookmark=stale_bookmark)
            fresh_bookmark.updated = datetime.datetime.now()
            _log.info('%s updated bookmark %s' % (current_user.email(), url))
            return fresh_bookmark
        else:
            _log.warning("%s couldn't update bookmark %s (doesn't exist?)" %
                         (current_user.email(), key_id))

    def _save_bookmark(self, url, bookmark=None):
        """Save a bookmark corresponding to the specified URL."""
        if bookmark is None:
            bookmark = models.Bookmark()
        else:
            self._unindex_bookmark(bookmark)
        bookmark.url = url
        bookmark.mime_type, bookmark.title, tags = self._process_url(url)
        bookmark.stems, bookmark.words, bookmark.counts = [], [], []
        for tag in tags:
            bookmark.stems.append(tag['stem'])
            bookmark.words.append(tag['word'])
            bookmark.counts.append(tag['count'])
        bookmark.put()
        self._index_bookmark(bookmark)
        return bookmark

    def _delete_bookmark(self, key_id):
        """Delete the bookmark corresponding to the specified URL."""
        current_user = users.get_current_user()
        _log.info('%s deleting bookmark %s' % (current_user.email(), key_id))
        old_bookmark = models.Bookmark.get_by_id(key_id)
        if old_bookmark:
            url = old_bookmark.url
            self._unindex_bookmark(old_bookmark)
            db.delete(old_bookmark)
            _log.info('%s deleted bookmark %s' % (current_user.email(), url))
        else:
            _log.warning("%s couldn't delete bookmark %s (doesn't exist?)" %
                         (current_user.email(), key_id))

    @decorators.batch_put_and_delete
    def _index_bookmark(self, bookmark):
        """Index a bookmark so that it appears in search results.

        For each stem in the bookmark, make sure a corresponding keychain
        exists.  If it doesn't exist, create it.  Then add the bookmark's key to
        that keychain.
        """
        current_user, url = users.get_current_user(), bookmark.url
        _log.info('%s indexing bookmark %s' % (current_user.email(), url))
        key, to_put = bookmark.key(), []
        for stem, word in zip(bookmark.stems, bookmark.words):
            key_name = models.Keychain.stem_to_key_name(stem)
            keychain = models.Keychain.get_by_key_name(key_name)
            if keychain is None:
                keychain = models.Keychain(key_name=key_name)
                keychain.stem = stem
                keychain.word = word
            if not key in keychain.keys:
                keychain.keys.append(key)
                to_put.append(keychain)
        _log.info('%s indexed bookmark %s' % (current_user.email(), url))
        return to_put, [], None

    @decorators.batch_put_and_delete
    def _unindex_bookmark(self, bookmark):
        """Unindex a bookmark so that it no longer appears in search results.

        For each stem in the bookmark, remove the bookmark's key from the
        keychain corresponding to the stem.  Then if the keychain no longer
        contains any keys at all, delete the keychain itself.
        """
        current_user, url = users.get_current_user(), bookmark.url
        _log.info('%s unindexing bookmark %s' % (current_user.email(), url))
        key, to_put, to_delete = bookmark.key(), [], []
        for stem in bookmark.stems:
            key_name = models.Keychain.stem_to_key_name(stem)
            error_message = "bookmark (%s, %s) has stem %s, " % (current_user, url, stem)
            error_message += "but keychain %s doesn't have bookmark (%s, %s)" % (key_name, current_user, url)
            keychain = models.Keychain.get_by_key_name(key_name)
            if keychain is not None:
                try:
                    keychain.keys.remove(key)
                except ValueError:
                    _log.critical(error_message)
                if not keychain.keys:
                    to_delete.append(keychain)
                else:
                    to_put.append(keychain)
        _log.info('%s unindexed bookmark %s' % (current_user.email(), url))
        return to_put, to_delete, None
