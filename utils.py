#------------------------------------------------------------------------------#
#   utils.py                                                                   #
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
"""Utility functions."""


from google.appengine.ext import db


def prefetch(entities, *properties):
    """Prefetch.

    For more information, see:
    http://blog.notdot.net/2010/01/ReferenceProperty-prefetching-in-App-Engine
    """
    fields = [(e, p) for e in entities for p in properties]
    keys = [p.get_value_for_datastore(e) for e, p in fields]
    keys = set(keys)
    references = db.get(keys)
    references = dict((r.key(), r) for r in references)
    for (e, p), k in zip(fields, keys):
        p.__set__(e, references[k])
    return entities
