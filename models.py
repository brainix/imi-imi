#------------------------------------------------------------------------------#
#   models.py                                                                  #
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
"""Google App Engine datastore models."""


import functools
import hashlib

from google.appengine.api.users import User
from google.appengine.ext import db
from google.appengine.ext.db import polymodel

from config import MAINTENANCE


class _BaseModel(polymodel.PolyModel):
    """Base class with common attributes from which other models inherit."""
    # Typically, when the webapp creates/updates a persistent object, we want
    # the datastore to automatically set that object's metadata.  (On creation,
    # the object's user to the currently logged in user, and created and
    # updated times to the current time.  On update, the object's updated time
    # to the current time.)
    #
    # However, when we're performing maintenance on the datastore (such as
    # adding an attribute to all persistent objects), we don't want the
    # datastore to auto set this metadata.  (In fact, this auto set behavior
    # has caused us to lose users' live data before.)
    #
    # Therefore, we specify for the datastore to auto set this metadata only
    # when we're running in normal (non-maintenance) mode.
    user = db.UserProperty(auto_current_user_add=not MAINTENANCE)
    created = db.DateTimeProperty(auto_now_add=not MAINTENANCE)
    updated = db.DateTimeProperty(auto_now=not MAINTENANCE)
    popularity = db.IntegerProperty(default=0)


class Bookmark(_BaseModel):
    """Model describing a bookmark.

    This model contains the various metadata and data that describe a bookmark.
    But it also acts as a forward index describing which search queries should
    match the particular bookmark.
    """
    users = db.ListProperty(User, default=[])
    url = db.LinkProperty()
    mime_type = db.StringProperty(default='', indexed=False)
    title = db.StringProperty(multiline=True, indexed=False)
    stems = db.ListProperty(str, default=[], indexed=False)
    words = db.ListProperty(str, default=[], indexed=False)
    counts = db.ListProperty(float, default=[], indexed=False)
    html_hash = db.StringProperty(default='', indexed=False)

    @staticmethod
    def key_name(url):
        """Convert a URL to a bookmark key."""
        return 'bookmark_' + url


class Reference(_BaseModel):
    """Model describing a reference to a bookmark."""
    bookmark = db.ReferenceProperty(Bookmark)

    @staticmethod
    def key_name(email, url):
        """Convert an email address and a URL to a reference key."""
        return 'reference_' + email + '_' + url


class Keychain(_BaseModel):
    """Model describing which bookmarks should match a query for a stem.
    
    This model acts as a reverse index describing which bookmarks should match
    a particular search query.
    """
    stem = db.StringProperty()
    word = db.StringProperty()
    keys = db.ListProperty(db.Key, default=[])

    @staticmethod
    def key_name(stem):
        """Convert a word stem to a keychain key.

        We have to resolve a stem to a keychain for every tag whenever we index
        or unindex a bookmark.  That's why it's important that resolving a stem
        to a keychain is fast.  In Google App Engine's datastore, it's
        significantly faster to look up an object by key than to retrieve an
        object using a query.  Therefore, we use this method consistently for
        naming a new keychain as well as looking up an existing keychain by stem
        (rather than querying over the stem property).
        """
        return 'keychain_' + stem
