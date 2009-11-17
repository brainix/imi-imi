#------------------------------------------------------------------------------#
#   models.py                                                                  #
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

"""Google App Engine datastore models."""


from google.appengine.ext import db
from google.appengine.ext.db import polymodel


class _BaseModel(polymodel.PolyModel):
    """Base class with common attributes from which other models inherit."""
    user = db.UserProperty(auto_current_user_add=True)
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    public = db.BooleanProperty(default=True)


class Bookmark(_BaseModel):
    """Model describing a bookmark."""
    url = db.LinkProperty()
    mime_type = db.StringProperty(default='')
    title = db.StringProperty(multiline=True)
    stems = db.ListProperty(str, default=[])
    words = db.ListProperty(str, default=[])
    counts = db.ListProperty(float, default=[])


class Keychain(_BaseModel):
    """Model describing which bookmarks should match a query for a stem."""
    stem = db.StringProperty()
    word = db.StringProperty()
    keys = db.ListProperty(db.Key, default=[])

    @staticmethod
    def stem_to_key_name(stem):
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
