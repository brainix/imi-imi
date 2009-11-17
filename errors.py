#!/usr/bin/env python

#------------------------------------------------------------------------------#
#   errors.py                                                                  #
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

"""Custom grab-it exception classes.

Example throwing:
    >>> try:
    ...     1 / 0
    ... except ZeroDivisionError:
    ...     raise SearchError(msg='divided by 0')
    ... 
    Traceback (most recent call last):
      ...
    SearchError: divided by 0

Example throwing and catching:
    >>> def search():
    ...     raise SearchError(msg='search error')
    ... 
    >>> try:
    ...     search()
    ... except SearchError, e:
    ...     msg = e.msg
    ...
"""


class _Error(Exception):
    """Base class from which exception classes in this module inherit."""
    pass


class IndexError(_Error):
    """Exception class to encapsulate errors while indexing bookmarks."""

    def __init__(self, *args, **kwds):
        """Initialize a IndexError exception object.

        If the msg keyword argument wasn't specified during the IndexError
        exception object instantiation, add it in here and give it a default
        value for consistency.

        Example with keyword argument:
            >>> e = IndexError(msg='Hello, World!')
            >>> e.msg
            'Hello, World!'

        Example without keyword argument:
            >>> e = IndexError()
            >>> e.msg
            'IndexError exception thrown'
        """
        default_values = {
            'msg': 'IndexError exception thrown',
        }

        for key in default_values:
            if not key in kwds:
                kwds[key] = default_values[key]
        self.__dict__.update(kwds)

    def __str__(self):
        """Return the string representation of a IndexError exception object.

        Example string representation:
            >>> e = IndexError()
            >>> print e
            IndexError exception thrown
        """
        return self.msg


class SearchError(_Error):
    """Exception class to encapsulate errors while searching bookmarks."""

    def __init__(self, *args, **kwds):
        """Initialize a SearchError exception object."""
        default_values = {
            'msg': 'SearchError exception thrown',
        }

        for key in default_values:
            if not key in kwds:
                kwds[key] = default_values[key]
        self.__dict__.update(kwds)

    def __str__(self):
        """Return the string representation of a SearchError exception obj."""
        return self.msg


if __name__ == '__main__':
    import doctest
    doctest.testmod()
