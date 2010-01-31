#!/usr/bin/env python

#------------------------------------------------------------------------------#
#   errors.py                                                                  #
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
"""Custom imi-imi exception classes.

Example throwing:
    >>> try:
    ...     1 / 0
    ... except ZeroDivisionError:
    ...     raise SearchError(error_message='divided by 0')
    ... 
    Traceback (most recent call last):
      ...
    SearchError: divided by 0

Example throwing and catching:
    >>> def search():
    ...     raise SearchError(error_message='search error')
    ... 
    >>> try:
    ...     search()
    ... except SearchError, e:
    ...     error_message = e.error_message
    ...
"""


class _Error(Exception):
    """Base class from which exception classes in this module inherit."""

    _default_values = {}

    def __init__(self, *args, **kwds):
        """Initialize a custom exception object.

        If the error_message keyword argument wasn't specified during the
        IndexError exception object instantiation, add it in here and give it a
        default value for consistency.

        Example with keyword argument:
            >>> e = IndexError(error_message='Hello, World!')
            >>> e.error_message
            'Hello, World!'

        Example without keyword argument:
            >>> e = IndexError()
            >>> e.error_message
            'IndexError exception thrown'
        """
        for key in self._default_values:
            if not key in kwds:
                kwds[key] = self._default_values[key]
        self.__dict__.update(kwds)

    def __str__(self):
        """Return the string representation of a custom exception object.

        Example string representation:
            >>> e = IndexError()
            >>> print e
            IndexError exception thrown
        """
        return self.error_message


class IndexError(_Error):
    """Exception class to encapsulate errors while indexing bookmarks."""

    _default_values = {
        'error_message': 'IndexError exception thrown',
    }


class SearchError(_Error):
    """Exception class to encapsulate errors while searching bookmarks."""

    _default_values = {
        'error_message': 'SearchError exception thrown',
    }


if __name__ == '__main__':
    import doctest
    doctest.testmod()
